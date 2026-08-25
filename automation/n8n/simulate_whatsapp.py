"""WhatsApp & Citizen Leak Intake Simulator for NeerDrishti AI.

Simulates incoming WhatsApp / Telegram citizen messages across multiple Indian languages,
tests privacy hashing, Bhashini regional translation, and POSTs directly to the backend API.

Usage:
    # Run full demo batch of multilingual citizen reports
    python simulate_whatsapp.py --batch

    # Test deduplication & spatial clustering
    python simulate_whatsapp.py --test-dedupe

    # Send a single custom report in Hindi
    python simulate_whatsapp.py --phone "+919876543210" --text "स्कूल के पास सड़क पर पानी बह रहा है" --lat 26.9124 --lon 75.7873
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure automation/n8n and project root are on sys.path
CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent.parent

for p in (str(ROOT_DIR), str(CURRENT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import httpx
except ImportError:
    httpx = None

try:
    from automation.n8n.services.sarvam import SarvamService
    from automation.n8n.utils.dedupe import ReportDeduplicator
    from automation.n8n.utils.hasher import hash_phone_number
except ImportError:
    from services.sarvam import SarvamService
    from utils.dedupe import ReportDeduplicator
    from utils.hasher import hash_phone_number

DEFAULT_API_URL = "http://localhost:8000/api/reports"

SAMPLE_REPORTS = [
    {
        "phone": "+91 98290 12345",
        "channel": "whatsapp",
        "text": "स्कूल के पास सड़क पर पानी बह रहा है, 2 दिन से पाइप लीक है",
        "lat": 26.9124,
        "lon": 75.7873,
        "media_url": "https://storage.neerdrishti.in/reports/leak_01.jpg",
    },
    {
        "phone": "+91 94140 54321",
        "channel": "whatsapp",
        "text": "Main water pipeline burst near Ward 2 market, low pressure in homes",
        "lat": 26.9200,
        "lon": 75.7920,
        "media_url": None,
    },
    {
        "phone": "+91 98800 11223",
        "channel": "whatsapp",
        "text": "ರಸ್ತೆಯಲ್ಲಿ ನೀರು ಸೋರುತ್ತಿದೆ ಮತ್ತು ಪೈಪ್ ಒಡೆದಿದೆ",  # Kannada
        "lat": 26.9050,
        "lon": 75.7800,
        "media_url": None,
    },
    {
        "phone": "+91 97900 33445",
        "channel": "telegram",
        "text": "தண்ணீர் கசிகிறது மற்றும் குழாய் உடைந்தது, தயவுசெய்து சரிசெய்யவும்",  # Tamil
        "lat": 26.9180,
        "lon": 75.7750,
        "media_url": "https://storage.neerdrishti.in/reports/leak_tamil_02.jpg",
    },
    {
        "phone": "+91 98200 99887",
        "channel": "whatsapp",
        "text": "पाणी वाहत आहे, मेन रोडवर खड्डा पडला आहे",  # Marathi
        "lat": 26.9100,
        "lon": 75.7950,
        "media_url": None,
    },
    {
        "phone": "+91 99000 44556",
        "channel": "whatsapp",
        "text": "Ground is soggy and green near underground valve box since last week",
        "lat": 26.9250,
        "lon": 75.7850,
        "media_url": None,
    },
]


def process_and_send_report(
    api_url: str,
    phone: str,
    text: str,
    channel: str = "whatsapp",
    lat: float | None = None,
    lon: float | None = None,
    zone_id: str | None = None,
    media_url: str | None = None,
    deduplicator: ReportDeduplicator | None = None,
) -> dict:
    """Simulate the full Role 3 n8n pipeline for a single citizen message."""
    translator = SarvamService()

    # 1. Privacy Hashing (Never store raw phone numbers)
    reporter_hash = hash_phone_number(phone)

    # 2. Regional Language NLP via Sarvam AI
    translation = translator.translate_sync(text, target_lang="en")

    # 3. Spatial-Temporal Deduplication Check
    if deduplicator:
        is_dup, reason, cluster = deduplicator.check_and_record(
            reporter_hash=reporter_hash,
            lat=lat,
            lon=lon,
            zone_id=zone_id,
            description=translation.translated_text,
            timestamp=datetime.now(timezone.utc),
        )
        if is_dup:
            print(f"⚠️  [Deduplicator] Filtered duplicate report from {reporter_hash[:16]}... ({reason})")
            return {"status": "dropped_duplicate", "reason": reason}
        if cluster > 1:
            print(f"🔔 [Deduplicator] Clustered report! Total {cluster} reports in 200m vicinity.")

    # 4. Prepare Payload for NeerDrishti API
    payload = {
        "channel": channel,
        "reporter_hash": reporter_hash,
        "description": translation.translated_text,
        "lat": lat,
        "lon": lon,
        "zone_id": zone_id,
        "media_url": media_url,
    }

    print("\n" + "=" * 60)
    print(f"📱 INCOMING MESSAGE [{channel.upper()}]: {phone}")
    print(f"   Original ({translation.detected_language}): \"{text}\"")
    if translation.is_translated:
        print(f"   🌐 Indic English Translation: \"{translation.translated_text}\" (via {translation.source})")
    print(f"   🔒 Reporter Hash: {reporter_hash}")
    print(f"   📍 Location: ({lat}, {lon})" if lat and lon else f"   📍 Zone: {zone_id}")

    try:
        if httpx is not None:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(api_url, json=payload)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    print(f"   ✅ SUCCESS -> Logged as Report #{data.get('id')} | Matched Zone: {data.get('zone_id')}")
                    return data
                else:
                    print(f"   ❌ API ERROR {resp.status_code}: {resp.text}")
                    return {"error": resp.text, "status_code": resp.status_code}
        else:
            req = urllib.request.Request(
                api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status in (200, 201):
                    data = json.loads(resp.read().decode("utf-8"))
                    print(f"   ✅ SUCCESS -> Logged as Report #{data.get('id')} | Matched Zone: {data.get('zone_id')}")
                    return data
                else:
                    print(f"   ❌ API ERROR {resp.status}")
                    return {"error": "API returned non-200", "status_code": resp.status}
    except Exception as exc:
        print(f"   ❌ CONNECTION FAILED: {exc}")
        print("   (Ensure backend API is running: python -m uvicorn app.main:app --port 8000)")
        return {"error": str(exc)}


def run_batch(api_url: str) -> None:
    """Send a diverse batch of citizen reports across multiple languages."""
    print(f"\n🚀 Running Role 3 Citizen Intake Simulation against {api_url}...\n")
    deduper = ReportDeduplicator(window_hours=6.0, radius_meters=200.0)
    for sample in SAMPLE_REPORTS:
        process_and_send_report(
            api_url=api_url,
            phone=sample["phone"],
            text=sample["text"],
            channel=sample["channel"],
            lat=sample["lat"],
            lon=sample["lon"],
            media_url=sample["media_url"],
            deduplicator=deduper,
        )


def run_dedupe_test(api_url: str) -> None:
    """Demonstrate deduplication when the same citizen or street sends 3 messages."""
    print("\n🧪 Testing Deduplication & Clustering Engine...\n")
    deduper = ReportDeduplicator(window_hours=6.0, radius_meters=200.0)
    same_phone = "+91 99999 88888"

    print("--- 1. First report from citizen ---")
    process_and_send_report(
        api_url=api_url,
        phone=same_phone,
        text="Water leaking near school gate",
        lat=26.9124,
        lon=75.7873,
        deduplicator=deduper,
    )

    print("\n--- 2. Immediate duplicate report from same citizen ---")
    process_and_send_report(
        api_url=api_url,
        phone=same_phone,
        text="Please fix water leak fast near school",
        lat=26.9124,
        lon=75.7873,
        deduplicator=deduper,
    )

    print("\n--- 3. Neighbour reporting same leak 50 meters away ---")
    process_and_send_report(
        api_url=api_url,
        phone="+91 88888 77777",
        text="Road flooded with water near school gate",
        lat=26.9126,
        lon=75.7875,
        deduplicator=deduper,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="NeerDrishti API endpoint for reports")
    parser.add_argument("--batch", action="store_true", help="Send full batch of multilingual reports")
    parser.add_argument("--test-dedupe", action="store_true", help="Run deduplication test scenario")
    parser.add_argument("--phone", default="+91 98765 43210", help="Sender phone number")
    parser.add_argument("--text", help="Leak description text")
    parser.add_argument("--lat", type=float, help="Latitude")
    parser.add_argument("--lon", type=float, help="Longitude")
    parser.add_argument("--zone", help="Zone ID (e.g. Z-001)")
    parser.add_argument("--channel", default="whatsapp", help="Channel (whatsapp/telegram/web)")

    args = parser.parse_args()

    if args.batch:
        run_batch(args.api_url)
    elif args.test_dedupe:
        run_dedupe_test(args.api_url)
    elif args.text:
        process_and_send_report(
            api_url=args.api_url,
            phone=args.phone,
            text=args.text,
            channel=args.channel,
            lat=args.lat,
            lon=args.lon,
            zone_id=args.zone,
        )
    else:
        # Default behavior if run without args: run batch
        run_batch(args.api_url)


if __name__ == "__main__":
    main()
