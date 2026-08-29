"""The citizen receipt must report what the API actually returned.

The receipt node once invented its ticket number with `Math.random()` and hardcoded
`Z-001 (Ward 1)` for every report, so every resident was told the same untrue thing and
the zone in the Telegram reply contradicted the zone on the dashboard.

These tests read the committed workflow, not a copy of the logic. That matters because
the live n8n Cloud workflow has diverged from this file before: if someone re-exports
their Cloud version over it, the fabrication comes back silently and this fails.
"""

import json
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
        # The API stores off-topic messages as 'dismissed'. Telling that sender their
        # leak was "logged successfully" is the same lie as the fake ticket number.
        self.assertIn("dismissed", self.code.lower())


if __name__ == "__main__":
    unittest.main()
