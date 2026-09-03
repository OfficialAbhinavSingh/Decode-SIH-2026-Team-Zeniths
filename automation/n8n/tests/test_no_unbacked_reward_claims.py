"""The Water Warrior reward workflow must stay switched off.

It tells a resident that "our NeerDrishti field crew has successfully fixed it" and that
they "helped save approximately N liters" of water. Neither is true: no crew has ever been
dispatched and no litre has ever been measured. docs/SCOPE.md records that limit and the
finals deck states it out loud, so shipping this message would have the product contradict
its own honesty claim in the one place a judge can screenshot.

Nothing in backend/ posts to the webhook, so the flow is already unreachable. This test is
here so that stays a decision rather than an accident -- flipping `active` back to true in
the committed JSON, or wiring a caller, fails here first.
"""

import json
import re
import unittest
from pathlib import Path

N8N_DIR = Path(__file__).resolve().parents[1]
REWARD = N8N_DIR / "citizen-reward.workflow.json"
BACKEND = N8N_DIR.parents[1] / "backend"

# The two claims we cannot back. Kept as patterns rather than exact strings so a reworded
# version of the same promise is caught too.
LITRES_CLAIM = re.compile(r"liters?|litres?", re.IGNORECASE)
CREW_CLAIM = re.compile(r"field crew|successfully fixed", re.IGNORECASE)


class TestRewardWorkflowStaysDisabled(unittest.TestCase):
    def setUp(self):
        self.workflow = json.loads(REWARD.read_text(encoding="utf-8"))

    def test_workflow_is_not_active(self):
        self.assertFalse(
            self.workflow["active"],
            "citizen-reward claims a repair and a litres-saved figure we cannot evidence. "
            "See automation/n8n/README.md before re-enabling it.",
        )

    def test_the_claims_this_guard_exists_for_are_still_the_ones_in_the_file(self):
        # If someone rewrites the message to drop both claims, this test is measuring
        # nothing and should be revisited rather than left passing by accident.
        body = json.dumps(self.workflow, ensure_ascii=False)
        self.assertTrue(LITRES_CLAIM.search(body))
        self.assertTrue(CREW_CLAIM.search(body))

    def test_nothing_in_the_backend_triggers_it(self):
        callers = [
            path.relative_to(BACKEND.parent)
            for path in BACKEND.rglob("*.py")
            if ".venv" not in path.parts and "citizen-reward" in path.read_text(
                encoding="utf-8", errors="ignore"
            )
        ]
        self.assertEqual(callers, [], f"the disabled reward flow has a caller: {callers}")


if __name__ == "__main__":
    unittest.main()
