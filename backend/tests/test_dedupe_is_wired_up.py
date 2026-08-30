"""The cross-package dedupe import must actually resolve, in every environment we deploy to.

`routers/reports.py` reaches out of `backend/` into `automation/n8n/` to share one
deduplication rule with the n8n workflow, and wraps it in `try/except ImportError` so a
broken path degrades instead of crashing. That fallback is the right behaviour and also
the danger: if the path ever breaks, `ReportDeduplicator` becomes `None`, every duplicate
silently scores as an independent report, and nothing anywhere says so.

That is not hypothetical. A comment in that module claimed for several days that the
import "always fails" on Render -- so anyone investigating duplicate reports in production
would have read it and stopped. Production row 39 carries status "duplicate", which only
this deduplicator writes, so the import plainly does resolve on Render. This test pins
the fact down so the next person does not have to take a comment's word for it.
"""

from app.routers import reports


def test_deduplicator_actually_loaded():
    """`None` here means every duplicate report is scoring as a real one."""
    assert reports.deduplicator is not None, (
        "ReportDeduplicator failed to import -- automation/n8n/utils/dedupe.py was not "
        "reachable from backend/app/routers/reports.py. Duplicate citizen reports are "
        "silently counting toward zone scores."
    )


def test_deduplicator_flags_a_repeat_from_the_same_reporter():
    """A second report from one person, same place, inside the window, is a duplicate."""
    deduper = type(reports.deduplicator)()
    common = dict(
        reporter_hash="a" * 64,
        lat=26.9124,
        lon=75.7873,
        zone_id="Z-001",
        description="Water flowing on the road",
    )

    is_dup_first, _, _ = deduper.check_and_record(**common)
    is_dup_second, reason, _ = deduper.check_and_record(**common)

    assert is_dup_first is False, "the first report from a reporter is never a duplicate"
    assert is_dup_second is True, f"the repeat was not caught (reason: {reason!r})"


def test_a_different_reporter_at_the_same_spot_is_not_a_duplicate():
    """Two neighbours reporting one leak is corroboration, not noise. Never drop this."""
    deduper = type(reports.deduplicator)()
    common = dict(
        lat=26.9124,
        lon=75.7873,
        zone_id="Z-001",
        description="Water flowing on the road",
    )

    deduper.check_and_record(reporter_hash="a" * 64, **common)
    is_dup, reason, _ = deduper.check_and_record(reporter_hash="b" * 64, **common)

    assert is_dup is False, (
        f"a second resident's report was dropped as a duplicate (reason: {reason!r}) -- "
        "this is the path docs/SCOPE.md calls must never break"
    )
