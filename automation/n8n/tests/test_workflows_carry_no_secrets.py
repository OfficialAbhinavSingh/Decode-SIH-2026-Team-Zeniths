"""The committed workflows must never carry a credential or a fabrication.

These files are re-exported from n8n Cloud by hand, and Cloud has repeatedly held things
git did not: a Telegram bot token pasted straight into three URLs, a 32-bit hash dressed up
as SHA-256, and a hardcoded city-centre coordinate standing in for a location the resident
never sent. A re-export that reintroduces any of them fails here rather than in production.
"""

import json
import re
import unittest
from pathlib import Path

N8N_DIR = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted(N8N_DIR.glob("*.workflow.json"))

TELEGRAM_TOKEN = re.compile(r"bot\d{6,}:[A-Za-z0-9_-]{20,}")
# sk-…, sk_…, and long opaque keys pasted where an expression belongs
API_KEY = re.compile(r"\bsk[-_][A-Za-z0-9_-]{16,}")


class TestNoSecrets(unittest.TestCase):
    def test_there_are_workflows_to_check(self):
        self.assertTrue(WORKFLOWS, "no *.workflow.json found -- this test would pass vacuously")

    def test_no_telegram_bot_token(self):
        for wf in WORKFLOWS:
            with self.subTest(wf.name):
                self.assertIsNone(TELEGRAM_TOKEN.search(wf.read_text(encoding="utf-8")))

    def test_no_api_key_literal(self):
        for wf in WORKFLOWS:
            with self.subTest(wf.name):
                self.assertIsNone(API_KEY.search(wf.read_text(encoding="utf-8")))

    def test_no_httpbin_fallback(self):
        # A silent fallback to a public request bin sends citizen reports to a stranger.
        for wf in WORKFLOWS:
            with self.subTest(wf.name):
                self.assertNotIn("httpbin", wf.read_text(encoding="utf-8"))

    def test_no_localhost_fallback(self):
        # $env is blocked on n8n Cloud, so `$env.API_URL || 'http://localhost:8000'`
        # silently resolves to localhost and the call goes nowhere.
        for wf in WORKFLOWS:
            with self.subTest(wf.name):
                self.assertNotIn("localhost", wf.read_text(encoding="utf-8"))


class TestIntakeIsNotFabricated(unittest.TestCase):
    """Node 2 of leak-intake: the hash must be real and the location must not be invented."""

    def setUp(self):
        wf = json.loads((N8N_DIR / "leak-intake.workflow.json").read_text(encoding="utf-8"))
        self.code = next(
            n["parameters"]["jsCode"] for n in wf["nodes"]
            if n["name"].startswith("2.")
        )

    def test_hash_is_really_sha256(self):
        self.assertIn("sha256", self.code.lower())
        self.assertTrue("createHash" in self.code or "sha256Hex" in self.code)

    def test_the_fake_digest_tail_is_gone(self):
        # The old hash was 8 real hex chars plus this 24-char constant, so every reporter
        # in the database shared the same tail.
        self.assertNotIn("f44501f1c43cdee531bfc875", self.code)

    def test_no_hardcoded_city_centre_coordinates(self):
        # Substituting Jaipur's centre reports a position the citizen never gave and pins
        # every locationless message to one zone.
        self.assertNotIn("26.9124", self.code)
        self.assertNotIn("75.7873", self.code)

    def test_missing_location_stays_null(self):
        self.assertIn("let lat = null", self.code)
        self.assertIn("let lon = null", self.code)

    def test_salt_is_read_from_vars(self):
        self.assertIn("PHONE_SALT", self.code)


if __name__ == "__main__":
    unittest.main()


class TestExpressionsAreWellFormed(unittest.TestCase):
    """A doubled '=' silently breaks an n8n expression field.

    n8n strips one leading '=' as the expression marker. A value stored as '==...' therefore
    renders to a string that still starts with '=', so a JSON body becomes invalid JSON and
    the request is never sent -- n8n reports "The value in the 'JSON Body' field is not valid
    JSON" and, with onError: continueRegularOutput, the workflow carries on as if it had
    worked. This shipped in two places at once: the ingest body and the Sarvam auth header.
    """

    def _expression_fields(self, workflow):
        for node in workflow["nodes"]:
            params = node.get("parameters", {})
            for key in ("jsonBody", "url"):
                if isinstance(params.get(key), str):
                    yield node["name"], key, params[key]
            headers = params.get("headerParameters", {}).get("parameters", [])
            for header in headers:
                if isinstance(header.get("value"), str):
                    yield node["name"], f"header {header.get('name')}", header["value"]

    def test_no_doubled_equals_prefix(self):
        for wf in WORKFLOWS:
            workflow = json.loads(wf.read_text(encoding="utf-8"))
            for name, key, value in self._expression_fields(workflow):
                with self.subTest(f"{wf.name}:{name}:{key}"):
                    self.assertFalse(value.startswith("=="), f"{value[:40]!r} starts with '=='")

    def test_ingest_body_is_valid_json_once_expressions_are_stripped(self):
        wf = json.loads((N8N_DIR / "leak-intake.workflow.json").read_text(encoding="utf-8"))
        body = next(n["parameters"]["jsonBody"] for n in wf["nodes"] if n["name"].startswith("6."))
        self.assertTrue(body.startswith("={"), f"body should start with a single '=': {body[:5]!r}")
        # Substitute every {{ ... }} with a placeholder literal and the rest must parse.
        skeleton = re.sub(r"\{\{.*?\}\}", "0", body[1:])
        skeleton = re.sub(r'"0"', '"x"', skeleton)
        json.loads(skeleton)
