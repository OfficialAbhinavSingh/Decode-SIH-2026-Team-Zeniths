"""Unit and Integration Tests for Role 3: Automation Engineer components."""

import json
import unittest
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root and automation/n8n directory to sys.path
TEST_DIR = Path(__file__).resolve().parent
N8N_DIR = TEST_DIR.parent
ROOT_DIR = N8N_DIR.parent.parent

for p in (str(ROOT_DIR), str(N8N_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from automation.n8n.utils.hasher import hash_phone_number, normalize_phone
    from automation.n8n.utils.dedupe import ReportDeduplicator, haversine_distance_meters
    from automation.n8n.services.sarvam import SarvamService
    from automation.n8n.services.alerts import format_crew_alert_card, dispatch_high_priority_alerts
except ImportError:
    from utils.hasher import hash_phone_number, normalize_phone
    from utils.dedupe import ReportDeduplicator, haversine_distance_meters
    from services.sarvam import SarvamService
    from services.alerts import format_crew_alert_card, dispatch_high_priority_alerts


class TestHasher(unittest.TestCase):
    """Validate citizen privacy hashing."""

    def test_phone_normalization(self):
        self.assertEqual(normalize_phone("+91 98290-12345"), "9829012345")
        self.assertEqual(normalize_phone("09829012345"), "9829012345")
        self.assertEqual(normalize_phone("9829012345"), "9829012345")

    def test_salted_hash_output(self):
        h1 = hash_phone_number("+91 98290 12345", salt="test-salt-1")
        self.assertTrue(h1.startswith("sha256:"))
        self.assertEqual(len(h1), 7 + 32)

        # Same number with different formatting should produce the exact same hash
        h2 = hash_phone_number("98290-12345", salt="test-salt-1")
        self.assertEqual(h1, h2)

        # Different salt produces a different hash
        h3 = hash_phone_number("98290-12345", salt="test-salt-2")
        self.assertNotEqual(h1, h3)

        # Different phone number produces a different hash
        h4 = hash_phone_number("98290-99999", salt="test-salt-1")
        self.assertNotEqual(h1, h4)


class TestDeduplication(unittest.TestCase):
    """Validate spatial-temporal deduplication and clustering."""

    def test_haversine_distance(self):
        # Two points in Jaipur ~130 meters apart
        lat1, lon1 = 26.9124, 75.7873
        lat2, lon2 = 26.9130, 75.7880
        dist = haversine_distance_meters(lat1, lon1, lat2, lon2)
        self.assertTrue(90 < dist < 160)

    def test_duplicate_same_reporter(self):
        deduper = ReportDeduplicator(window_hours=6.0, radius_meters=200.0)
        rep_hash = "sha256:abcd1234efgh"
        now = datetime.now(timezone.utc)

        # 1. First report accepted
        is_dup, reason, cluster = deduper.check_and_record(
            reporter_hash=rep_hash,
            lat=26.9124,
            lon=75.7873,
            zone_id="Z-001",
            description="First leak report",
            timestamp=now,
        )
        self.assertFalse(is_dup)
        self.assertEqual(cluster, 1)

        # 2. Second submission from same reporter 10 minutes later -> caught as duplicate
        is_dup2, reason2, _ = deduper.check_and_record(
            reporter_hash=rep_hash,
            lat=26.9124,
            lon=75.7873,
            zone_id="Z-001",
            description="Followup message: still leaking",
            timestamp=now + timedelta(minutes=10),
        )
        self.assertTrue(is_dup2)
        self.assertIn("duplicate", reason2)

    def test_clustering_different_reporters_nearby(self):
        deduper = ReportDeduplicator(window_hours=6.0, radius_meters=200.0)
        now = datetime.now(timezone.utc)

        # Reporter 1: Reports leak outside shop
        deduper.check_and_record(
            reporter_hash="sha256:user1",
            lat=26.91240,
            lon=75.78730,
            zone_id="Z-001",
            description="Leak outside shop",
            timestamp=now,
        )

        # Reporter 2: 50 meters away reports road wet 15 mins later -> accepted and clustered!
        is_dup, reason, cluster = deduper.check_and_record(
            reporter_hash="sha256:user2",
            lat=26.91270,
            lon=75.78760,
            zone_id="Z-001",
            description="Road wet near shop",
            timestamp=now + timedelta(minutes=15),
        )
        self.assertFalse(is_dup)
        self.assertEqual(cluster, 2)


class TestSarvamNLP(unittest.TestCase):
    """Validate Sarvam AI Indic language detection and translation."""

    def setUp(self):
        self.service = SarvamService()

    def test_language_detection(self):
        self.assertEqual(self.service.detect_language("Water is leaking on the road"), "en")
        self.assertEqual(self.service.detect_language("स्कूल के पास सड़क पर पानी बह रहा है"), "hi")
        self.assertEqual(self.service.detect_language("தண்ணீர் கசிகிறது"), "ta")
        self.assertEqual(self.service.detect_language("ರಸ್ತೆಯಲ್ಲಿ ನೀರು ಸೋರುತ್ತಿದೆ"), "kn")
        self.assertEqual(self.service.detect_language("నీరు లీಕ್ అవుతోంది"), "te")

    def test_offline_translation_hindi(self):
        text = "स्कूल के पास सड़क पर पानी बह रहा है"
        res = self.service.translate_sync(text, target_lang="en")
        self.assertTrue(res.is_translated)
        self.assertEqual(res.detected_language, "hi")
        self.assertIn("water is flowing", res.translated_text)
        self.assertIn("near the school", res.translated_text)

    def test_offline_translation_tamil(self):
        text = "சாலையில் தண்ணீர் கசிகிறது"
        res = self.service.translate_sync(text, target_lang="en")
        self.assertTrue(res.is_translated)
        self.assertEqual(res.detected_language, "ta")
        self.assertIn("water is leaking", res.translated_text)

    def test_english_passthrough(self):
        text = "Major leak near main valve"
        res = self.service.translate_sync(text, target_lang="en")
        self.assertFalse(res.is_translated)
        self.assertEqual(res.detected_language, "en")
        self.assertEqual(res.translated_text, text)


class TestAlertDispatch(unittest.TestCase):
    """Validate crew alert formatting and priority dispatch filtering."""

    def test_alert_card_formatting(self):
        sample_score = {
            "zone_id": "Z-014",
            "name": "Ward 7 - Sector 3",
            "rank": 1,
            "fusion_score": 87.4,
            "confidence": "high",
            "signals_used": 3,
            "satellite_score": 91.2,
            "billing_score": 84.0,
            "citizen_score": 78.5,
            "explanation": "NDVI +0.18 anomaly, 41% NRW gap, and 4 citizen reports.",
        }
        card = format_crew_alert_card(sample_score)
        self.assertIn("Z-014", card)
        self.assertIn("87.4/100", card)
        self.assertIn("CRITICAL", card)
        self.assertIn("🛰️ Satellite Wetness Anomaly: 91.2/100", card)
        self.assertIn("Ward 7 - Sector 3", card)

    def test_dispatch_high_priority_filtering(self):
        scores = [
            {"zone_id": "Z-001", "rank": 1, "fusion_score": 88.0, "confidence": "high"},
            {"zone_id": "Z-002", "rank": 2, "fusion_score": 79.0, "confidence": "medium"},
            {"zone_id": "Z-003", "rank": 3, "fusion_score": 45.0, "confidence": "low"},
        ]
        results = dispatch_high_priority_alerts(scores, min_score=75.0, max_alerts=5)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].zone_id, "Z-001")
        self.assertEqual(results[1].zone_id, "Z-002")


class TestWorkflowJSON(unittest.TestCase):
    """Validate n8n workflow file structures and nodes."""

    def test_all_workflow_structures(self):
        workflows = [
            ("leak-intake.workflow.json", ["1. WhatsApp / Telegram Webhook", "2. Extract & Hash Phone (SHA-256)", "3. Need Sarvam AI Translation?", "4. Call Sarvam AI Mayura Translation", "5. Format Standardized Description", "6. Ingest into NeerDrishti API", "7. Citizen Receipt Generator"]),
            ("satellite-trigger.workflow.json", ["12-Day Satellite Orbit Pass Trigger", "Compute Cadence Window", "Trigger Fusion Recalculation"]),
            ("alert-dispatch.workflow.json", ["Every 30 Minutes Trigger", "Fetch Ranked Zone Scores", "Filter & Format Alert Cards"]),
        ]

        for fname, expected_nodes in workflows:
            wf_path = N8N_DIR / fname
            self.assertTrue(wf_path.exists(), f"{fname} must exist")
            with open(wf_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("nodes", data)
            self.assertIn("connections", data)
            node_names = [n["name"] for n in data["nodes"]]
            for en in expected_nodes:
                self.assertIn(en, node_names)


if __name__ == "__main__":
    unittest.main()
