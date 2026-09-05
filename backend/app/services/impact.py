"""What a repair is actually worth: kilolitres, rupees, households.

Owner: R2 (Data). Pure functions, no I/O.

WHY THIS EXISTS: "Zone 14 scores 87" does not move a municipal commissioner. "Zone 14 is
losing 310 kl a day, about 20 lakh rupees a year, enough for 1,100 households" does. The
numbers below are the bridge from our score to a budget line, and every constant is a
published figure rather than a guess.

SOURCES:
  1. Non-revenue water splits into *real* (physical leakage) and *apparent* (metering
     error, unbilled authorised use, theft) losses. IWA/AWWA standard water balance, as
     adopted in the CPHEEO Manual on Water Supply and Treatment Part-3 §5.3; Indian
     utility audits put real losses at roughly 60-70% of total NRW.
     https://cpheeo.gov.in/upload/uploadfiles/files/Part3.pdf

  2. Not all real loss is recoverable. Active leakage control programmes in Indian ULBs
     typically recover 25-35% of physical losses in the first cycle; the remainder is
     background leakage at joints that only pipe replacement addresses.
     (AMRUT 2.0 Reforms Compendium, Reform AUA-1 "Reduction of NRW", target trajectory.)
     https://amrut.gov.in/

  3. Cost of producing and delivering one kilolitre in Indian urban systems: Rs 15-25.
     We use Rs 18 -- mid-band, and conservative for the pitch.
     (NIUA / MoHUA Service Level Benchmarking, "cost recovery in water supply services".)

  4. Per-capita supply norm 135 lpcd for cities with sewerage; the Jal Jeevan Mission
     minimum service level is 55 lpcd. CPHEEO Manual Part-1 §3.2.
     Household size 4.9 persons, Census 2011 -- rounded to 5.

Every figure produced here is an *estimate from a model*, and the API returns it beside
the assumptions rather than as a bare number.
"""

# Share of non-revenue water that is physical leakage rather than commercial loss.
PHYSICAL_LOSS_SHARE = 0.65

# Share of that physical leakage a repair programme actually recovers.
RECOVERY_RATE = 0.30

# Rupees per kilolitre produced and delivered.
COST_PER_KL_INR = 18.0

# CPHEEO supply norm and JJM service floor, litres per capita per day.
SUPPLY_NORM_LPCD = 135.0
SERVICE_FLOOR_LPCD = 55.0

# Census 2011 average urban household size, rounded.
PERSONS_PER_HOUSEHOLD = 5.0

# Fallback NRW when a zone has no billing row: the CPHEEO national band midpoint.
NATIONAL_NRW_PCT = 35.0


def daily_supply_kl(population: int | None, lpcd: float = SUPPLY_NORM_LPCD) -> float:
    """Kilolitres per day a zone of this population should be receiving."""
    if not population or population <= 0:
        return 0.0
    return round(population * lpcd / 1000.0, 2)


def recoverable_kld(
    population: int | None,
    nrw_pct: float | None,
    supplied_kl: float | None = None,
    period_days: int | None = None,
) -> float:
    """Kilolitres per day this zone could get back if its leaks were repaired.

    Prefers the metered `supplied_kl` over the population norm when a billing row exists,
    because measured throughput beats a design assumption. Falls back to population x
    CPHEEO norm so a zone with only a satellite signal still carries an impact figure --
    flagged as an estimate by the caller, not silently equated with a metered one.
    """
    if nrw_pct is None:
        nrw_pct = NATIONAL_NRW_PCT

    if supplied_kl and period_days and period_days > 0:
        supply_per_day = supplied_kl / period_days
    else:
        supply_per_day = daily_supply_kl(population)

    if supply_per_day <= 0:
        return 0.0

    loss_per_day = supply_per_day * max(0.0, min(100.0, nrw_pct)) / 100.0
    return round(loss_per_day * PHYSICAL_LOSS_SHARE * RECOVERY_RATE, 2)


def annual_value_inr(kld: float) -> float:
    """Rupees a year that much daily recovery is worth."""
    return round(kld * 365 * COST_PER_KL_INR, 2)


def households_served(kld: float, lpcd: float = SERVICE_FLOOR_LPCD) -> int:
    """How many households that recovered water would supply at the JJM service floor."""
    per_household_kld = lpcd * PERSONS_PER_HOUSEHOLD / 1000.0
    if per_household_kld <= 0:
        return 0
    return int(kld / per_household_kld)


def ledger(
    population: int | None,
    nrw_pct: float | None,
    supplied_kl: float | None = None,
    period_days: int | None = None,
) -> dict:
    """The whole impact record for one zone, ready to serialise."""
    kld = recoverable_kld(population, nrw_pct, supplied_kl, period_days)
    return {
        "water_at_risk_kld": kld,
        "annual_value_inr": annual_value_inr(kld),
        "households_served": households_served(kld),
        "basis": "metered" if (supplied_kl and period_days) else "population-norm",
    }


ASSUMPTIONS = {
    "physical_loss_share": PHYSICAL_LOSS_SHARE,
    "recovery_rate": RECOVERY_RATE,
    "cost_per_kl_inr": COST_PER_KL_INR,
    "supply_norm_lpcd": SUPPLY_NORM_LPCD,
    "service_floor_lpcd": SERVICE_FLOOR_LPCD,
    "persons_per_household": PERSONS_PER_HOUSEHOLD,
    "fallback_nrw_pct": NATIONAL_NRW_PCT,
    "sources": [
        "CPHEEO Manual on Water Supply and Treatment, Part-3 §5.3 (IWA water balance)",
        "AMRUT 2.0 Reforms Compendium, Reform AUA-1 (NRW reduction trajectory)",
        "NIUA/MoHUA Service Level Benchmarking (cost recovery, Rs/kl)",
        "CPHEEO Manual Part-1 §3.2 (135 lpcd norm); Jal Jeevan Mission (55 lpcd floor)",
        "Census of India 2011 (urban household size)",
    ],
}
