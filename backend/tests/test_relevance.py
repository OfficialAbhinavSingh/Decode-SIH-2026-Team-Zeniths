"""Only water-leak reports may score as water-leak evidence.

Every string in `test_the_messages_that_actually_got_through` is a real row that was sitting
in the production `citizen_reports` table, scoring. One person testing the Telegram bot put
13 reports on a single zone -- `/help`, `Hello?`, `Pothole damage` among them -- and carried
that zone to rank 6 of 30, ahead of zones with real Sentinel-2 evidence.
"""

import json
import re
from pathlib import Path

import pytest

from app.services.relevance import classify, is_actionable

WORKFLOW = Path(__file__).resolve().parents[2] / "automation" / "n8n" / "leak-intake.workflow.json"


@pytest.mark.parametrize(
    "text",
    ["/help", "Hello?", "Pothole", "Pothole damage", "hi", "/start", "hey!", "  hello  ",
     "garbage not collected", "streetlight not working"],
)
def test_the_messages_that_actually_got_through(text):
    assert not is_actionable(text)


@pytest.mark.parametrize(
    "text",
    ["Water is flowing on the road", "Water pipe burst near city center",
     "Water leaking on road near park", "Pipeline leaking beside the school gate",
     "Low pressure for a week and water on the street",
     "Road is always wet near the corner, no rain here"],
)
def test_real_leak_reports_still_count(text):
    assert is_actionable(text)


def test_water_wins_over_an_off_topic_word():
    """'Water flowing from a pothole' is a leak report that happens to mention a pothole."""
    assert is_actionable("Water flowing from a pothole on the road")
    assert classify("Water flowing from a pothole on the road") == "actionable"


@pytest.mark.parametrize("text", [None, "", "   "])
def test_a_report_with_no_text_still_counts(text):
    """A photo plus coordinates is a report. Absence of words is not evidence of junk."""
    assert is_actionable(text)


@pytest.mark.parametrize(
    "text",
    ["सड़क पर पानी बह रहा है", "தண்ணீர் கசிகிறது", "ನೀರು ಸೋರುತ್ತಿದೆ",
     "kal se pani beh raha hai", "something strange near the corner"],
)
def test_unrecognised_text_fails_open(text):
    """The whole design: never drop a resident's report because we lack their keywords.

    A missed junk message costs noise in one zone. A wrongly rejected report is somebody
    who told us about a real leak and was ignored.
    """
    assert is_actionable(text)


def test_greeting_and_off_topic_are_distinguished():
    assert classify("/help") == "greeting"
    assert classify("Pothole damage") == "off_topic"


def test_the_n8n_greeting_regex_catches_what_it_missed():
    """The workflow's own filter, checked against the messages that escaped it.

    The shipped pattern was `^(hi|hello|/start|hey|help)$` -- it listed `/start` with a
    slash but `help` without one, so `/help` never matched, and being fully anchored it
    also missed `Hello?`. Both reached the database.
    """
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    node = next(n for n in workflow["nodes"] if n["name"] == "Is this a Greeting?")
    pattern = node["parameters"]["conditions"]["conditions"][0]["rightValue"]

    body, _, flags = pattern[1:].rpartition("/")
    regex = re.compile(body, re.IGNORECASE if "i" in flags else 0)

    for greeting in ["/help", "Hello?", "hi", "hello", "/start", "hey", "help", "hi!", "  hey  "]:
        assert regex.match(greeting), f"{greeting!r} should be treated as a greeting"

    for report in ["Water is flowing on the road", "Pipeline leaking beside the school gate",
                   "Pothole damage", "How do I do that"]:
        assert not regex.match(report), f"{report!r} must not be swallowed as a greeting"
