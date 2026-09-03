"""The citizen receipt must report what the API actually returned.

The receipt node once invented its ticket number with `Math.random()` and hardcoded
`Z-001 (Ward 1)` for every report, so every resident was told the same untrue thing and
the zone in the Telegram reply contradicted the zone on the dashboard.

These tests read the committed workflow, not a copy of the logic. That matters because
the live n8n Cloud workflow has diverged from this file before: if someone re-exports
their Cloud version over it, the fabrication comes back silently and this fails.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / "leak-intake.workflow.json"
RECEIPT_NODE = "7. Citizen Receipt Generator"
INGEST_NODE = "6. Ingest into NeerDrishti API"


def receipt_code() -> str:
    nodes = json.loads(WORKFLOW.read_text(encoding="utf-8"))["nodes"]
    for node in nodes:
        if node["name"] == RECEIPT_NODE:
            return node["parameters"]["jsCode"]
    raise AssertionError(f"{RECEIPT_NODE!r} is missing from the workflow")


class TestReceiptIsNotFabricated(unittest.TestCase):
    def setUp(self):
        self.code = receipt_code()

    def test_ticket_number_is_not_random(self):
        self.assertNotIn("Math.random", self.code)

    def test_zone_is_not_hardcoded(self):
        self.assertNotIn("Z-001", self.code)

    def test_reads_the_ingest_response(self):
        self.assertIn(INGEST_NODE, self.code)

    def test_ticket_and_zone_come_from_the_api(self):
        self.assertIn("api.id", self.code)
        self.assertIn("api.zone_id", self.code)

    def test_does_not_claim_a_crew_was_dispatched(self):
        # Nothing dispatches a crew, so the receipt must not say one was.
        self.assertNotIn("Dispatched to Ward Repair Crew", self.code)

    def test_distinguishes_a_dismissed_report(self):
        # The API stores off-topic messages as 'dismissed' and scoring ones as 'new'.
        # Telling a dismissed sender their leak was "logged successfully" is the same lie
        # as the fake ticket number, so the receipt must consult the stored status.
        self.assertIn("api.status", self.code)

    def test_does_not_claim_success_when_nothing_was_stored(self):
        # Node 6 runs with onError: continueRegularOutput, so a rejected POST still reaches
        # node 7. The receipt must check that an id came back before claiming anything.
        self.assertIn("Number.isInteger(api.id)", self.code)



# The assertions above read the node as text. That catches a fabrication being pasted back
# in, but it cannot tell whether the receipt says the right thing for a given API response.
# These run the committed jsCode under node with a stubbed n8n `$()` and read the message
# it actually produces.

NODE = shutil.which("node")


def run_receipt(api_response, *, lang="en", lat=26.91, lon=75.79, desc="Water flowing on the road"):
    """Execute the committed receipt node against one fake API response, return its output."""
    driver = f"""
const nodes = {{
  "1. WhatsApp / Telegram Webhook": {{ message: {{ chat: {{ id: 12345 }} }} }},
  "2. Extract & Hash Phone (SHA-256)": {{ detected_language: {json.dumps(lang)} }},
  "5. Format Standardized Description": {{
    description: {json.dumps(desc)}, lat: {json.dumps(lat)}, lon: {json.dumps(lon)}
  }},
  "6. Ingest into NeerDrishti API": {json.dumps(api_response)}
}};
const $ = (name) => ({{ first: () => ({{ json: nodes[name] }}) }});
const code = {json.dumps(receipt_code())};
const out = new Function("$", code)($);
process.stdout.write(JSON.stringify(out[0].json));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as fh:
        fh.write(driver)
        path = fh.name
    try:
        proc = subprocess.run([NODE, path], capture_output=True, text=True, timeout=30)
    finally:
        os.unlink(path)
    if proc.returncode != 0:
        raise AssertionError(f"receipt node threw: {proc.stderr.strip()}")
    return json.loads(proc.stdout)


@unittest.skipUnless(NODE, "node is not installed; behavioural receipt tests skipped")
class TestReceiptBehaviour(unittest.TestCase):
    def test_in_coverage_leak_is_queued_for_review(self):
        out = run_receipt({"id": 41, "zone_id": "Z-005", "status": "new"})
        self.assertIn("Queued for ward review", out["receipt_message"])
        self.assertIn("Z-005", out["receipt_message"])
        self.assertEqual(out["ticket_id"], 41)
        self.assertTrue(out["in_coverage"])

    def test_report_outside_every_zone_is_not_promised_a_ward_review(self):
        # match_zone() returns None for a point outside all polygons, so the report is
        # stored with zone_id=None and fusion.py can never join it to a zone. It will not
        # be dispatched and it cannot move a score, so the receipt must not say otherwise.
        # Relevance and zone matching are independent: this arrives as status "new".
        out = run_receipt({"id": 42, "zone_id": None, "status": "new"})
        msg = out["receipt_message"]
        self.assertNotIn("Queued for ward review", msg)
        self.assertIn("Outside Coverage Area", msg)
        self.assertIn("does not change any zone score", msg)
        self.assertIn("#42", msg)                       # the ticket is real and still given
        self.assertEqual(out["status"], "success")      # it *was* stored
        self.assertFalse(out["in_coverage"])

    def test_hindi_out_of_coverage_receipt_also_avoids_the_queue_promise(self):
        out = run_receipt({"id": 43, "zone_id": None, "status": "new"}, lang="hi")
        msg = out["receipt_message"]
        self.assertNotIn("वार्ड समीक्षा के लिए दर्ज", msg)
        self.assertIn("कवरेज क्षेत्र से बाहर", msg)
        self.assertIn("#43", msg)

    def test_dismissed_report_is_still_told_it_was_not_read_as_a_leak(self):
        out = run_receipt({"id": 44, "zone_id": "Z-005", "status": "dismissed"})
        self.assertIn("Not read as a leak report", out["receipt_message"])
        self.assertNotIn("Queued for ward review", out["receipt_message"])

    def test_dismissed_report_outside_coverage_is_not_called_a_leak_report(self):
        out = run_receipt({"id": 45, "zone_id": None, "status": "dismissed"})
        msg = out["receipt_message"]
        self.assertNotIn("Queued for ward review", msg)
        self.assertNotIn("Water Leak Report Logged", msg)

    def test_rejected_post_still_produces_an_honest_failure(self):
        out = run_receipt(
            {"detail": "provide zone_id, or both lat and lon"}, lat=None, lon=None
        )
        self.assertIn("Not logged", out["receipt_message"])
        self.assertEqual(out["status"], "not_stored")
        self.assertIsNone(out["ticket_id"])
        self.assertFalse(out["in_coverage"])


if __name__ == "__main__":
    unittest.main()
