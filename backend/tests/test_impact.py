"""Tests for the kilolitres/rupees/households impact ledger.
See app/services/impact.py for the CPHEEO/AMRUT figures each constant is drawn from.
"""

import pytest

from app.services import impact


def test_daily_supply_scales_with_population_and_norm():
    assert impact.daily_supply_kl(0) == 0.0
    assert impact.daily_supply_kl(None) == 0.0
    assert impact.daily_supply_kl(10_000) == pytest.approx(10_000 * 135 / 1000)


def test_recoverable_kld_uses_metered_supply_over_the_population_norm():
    """A billing row should win over the CPHEEO norm -- a measurement beats an assumption."""
    from_norm = impact.recoverable_kld(10_000, 40.0)
    from_meter = impact.recoverable_kld(10_000, 40.0, supplied_kl=300_000, period_days=30)
    assert from_norm != from_meter
    assert from_meter == pytest.approx((300_000 / 30) * 0.40 * impact.PHYSICAL_LOSS_SHARE * impact.RECOVERY_RATE)


def test_recoverable_kld_falls_back_to_national_nrw_when_missing():
    with_default = impact.recoverable_kld(10_000, None)
    explicit = impact.recoverable_kld(10_000, impact.NATIONAL_NRW_PCT)
    assert with_default == explicit


def test_recoverable_kld_zero_population_is_zero_not_an_error():
    assert impact.recoverable_kld(0, 40.0) == 0.0
    assert impact.recoverable_kld(None, 40.0) == 0.0


def test_annual_value_and_households_are_nonnegative_and_scale():
    kld = 100.0
    assert impact.annual_value_inr(kld) == pytest.approx(kld * 365 * impact.COST_PER_KL_INR)
    assert impact.households_served(kld) > 0
    assert impact.households_served(0.0) == 0


def test_ledger_reports_its_basis():
    metered = impact.ledger(10_000, 40.0, supplied_kl=300_000, period_days=30)
    estimated = impact.ledger(10_000, 40.0)
    assert metered["basis"] == "metered"
    assert estimated["basis"] == "population-norm"
    assert metered["water_at_risk_kld"] >= 0
