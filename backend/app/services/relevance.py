"""Decide whether an inbound citizen report is actually about a water leak.

Owner: R3, called from the R5 intake endpoint.

The n8n workflow has a greeting filter, but it is one regex on one channel, and the web
form at /report has no filter at all. Production proved that is not enough: `/help`,
`Hello?`, `Pothole` and `Pothole damage` all landed in `citizen_reports` and scored as
leak evidence, carrying one zone to rank 6 of 30 ahead of zones with real satellite data.

This is deliberately **conservative and fail-open**. A missed junk message costs a little
noise in one zone's score. A wrongly rejected report is a resident who told us about a real
leak and was ignored -- so anything this module cannot confidently categorise is treated as
a real report. In particular, text in a language we do not have keywords for falls through
to "actionable" rather than being dropped.
"""

import re

# Greetings and bot commands. Anchored, but tolerant of the punctuation and slash prefixes
# that the n8n regex missed: it required an exact `^(hi|hello|/start|hey|help)$`, so `/help`
# and `Hello?` both sailed past it into the database.
_GREETING = re.compile(
    r"^\s*[/!]?(hi|hey|hello|hola|namaste|help|start|menu|test|ok|thanks|thank you)[\s!?.,]*$",
    re.IGNORECASE,
)

# If any of these appear, it is about water. Checked before the off-topic list, so
# "water flowing from a pothole" stays a leak report.
_WATER = (
    "water", "leak", "leaking", "leakage", "pipe", "pipeline", "burst", "bursting",
    "drain", "drainage", "sewage", "sewer", "tap", "supply", "pressure", "flood",
    "flooding", "wet", "damp", "puddle", "overflow", "seepage", "seeping", "spill",
    "boring", "borewell", "tanker", "hydrant", "valve", "meter",
)

# Other civic complaints. Real reports, genuinely worth logging -- just not evidence of a
# water leak, so they must not move a water-leak score.
_OFF_TOPIC = (
    "pothole", "garbage", "trash", "rubbish", "litter", "streetlight", "street light",
    "lamp post", "electricity", "power cut", "load shedding", "traffic", "signal light",
    "encroachment", "stray dog", "noise",
)


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(t)}\b", text) for t in terms)


def classify(description: str | None) -> str:
    """Return 'actionable', 'greeting' or 'off_topic'.

    Only 'actionable' reports contribute to a zone's citizen score.
    """
    # No text at all is not evidence of junk -- a report can arrive as coordinates plus a
    # photo. Counting it is the safe direction.
    if description is None or not description.strip():
        return "actionable"

    text = description.strip().lower()

    if _GREETING.match(text):
        return "greeting"

    if _contains(text, _WATER):
        return "actionable"

    if _contains(text, _OFF_TOPIC):
        return "off_topic"

    # Unrecognised: a real report in a language or phrasing we have no keywords for. Count
    # it. This is the fail-open branch and it is the point of the module.
    return "actionable"


def is_actionable(description: str | None) -> bool:
    return classify(description) == "actionable"
