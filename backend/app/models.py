"""Database tables. Mirrors docs/DATA-CONTRACT.md exactly.

Owner: R3 (Backend & Fusion). Changing anything here means telling the whole team --
every other lane reads or writes these columns.
"""

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class City(Base):
    """One urban local body in the national registry. Owned by R2 (Data).

    Added for pan-India coverage: the dashboard's zoomed-out view needs one row per city,
    not one per zone, or the first paint of the national map ships seven thousand
    polygons. Built by `pipelines.geo.registry` from the GeoNames India dump; see that
    module for provenance and the suburb-absorption rule.
    """

    __tablename__ = "cities"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    state: Mapped[str] = mapped_column(String(80), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    population: Mapped[int] = mapped_column(Integer)
    zone_count: Mapped[int] = mapped_column(Integer, default=0)
    service_radius_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_km2: Mapped[float | None] = mapped_column(Float, nullable=True)
    pipe_length_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Zone(Base):
    """A municipal water zone / ward sector. Owned by R1 (Satellite & Geo)."""

    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100), index=True)
    # National coverage fields. `city_code` is the join to `cities`; `state` is
    # denormalised onto the zone so the state choropleth is one GROUP BY, not a join
    # across seven thousand rows on every map pan.
    city_code: Mapped[str | None] = mapped_column(String(8), index=True, nullable=True)
    state: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    area_km2: Mapped[float | None] = mapped_column(Float, nullable=True)
    ward: Mapped[str | None] = mapped_column(String(100), nullable=True)
    centroid_lat: Mapped[float] = mapped_column(Float)
    centroid_lon: Mapped[float] = mapped_column(Float)
    geojson: Mapped[dict] = mapped_column(JSON)
    pipe_length_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    population: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    satellite_signals: Mapped[list["SatelliteSignal"]] = relationship(back_populates="zone")
    billing_signals: Mapped[list["BillingSignal"]] = relationship(back_populates="zone")
    citizen_reports: Mapped[list["CitizenReport"]] = relationship(back_populates="zone")
    scores: Mapped[list["ZoneScore"]] = relationship(back_populates="zone")


class SatelliteSignal(Base):
    """NDVI / wetness anomaly over a zone. Written by R1's pipeline."""

    __tablename__ = "satellite_signals"
    __table_args__ = (UniqueConstraint("zone_id", "observed_on", name="uq_satellite_zone_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"), index=True)
    observed_on: Mapped[date] = mapped_column(Date)
    ndvi_mean: Mapped[float] = mapped_column(Float)
    ndvi_baseline: Mapped[float] = mapped_column(Float)
    ndvi_anomaly: Mapped[float] = mapped_column(Float)
    wetness_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    cloud_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    score: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(50), default="sentinel2-gee")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    zone: Mapped[Zone] = relationship(back_populates="satellite_signals")


class BillingSignal(Base):
    """Non-revenue water gap for a zone over a billing period. Written by R2's pipeline."""

    __tablename__ = "billing_signals"
    __table_args__ = (
        UniqueConstraint("zone_id", "period_start", "period_end", name="uq_billing_zone_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    supplied_kl: Mapped[float] = mapped_column(Float)
    billed_kl: Mapped[float] = mapped_column(Float)
    nrw_pct: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    # Our billing data is generated from published NRW benchmarks, not a real utility feed.
    # Keep this true unless a city actually hands us a file.
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    zone: Mapped[Zone] = relationship(back_populates="billing_signals")


class CitizenReport(Base):
    """A leak reported by a resident. Written by R5's n8n workflow or the web form."""

    __tablename__ = "citizen_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"), nullable=True, index=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    channel: Mapped[str] = mapped_column(String(20), default="web")
    # Hashed phone number only -- raw numbers must never reach the database.
    reporter_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    zone: Mapped[Zone | None] = relationship(back_populates="citizen_reports")


class GroundwaterStress(Base):
    """Groundwater extraction pressure for an administrative area. Owned by R2 (Data).

    Keyed by state (and district where we have it), not by zone, because that is the
    resolution at which CGWB publishes -- fanning one state figure out to four hundred
    zone rows would imply a precision the source does not have. Fusion joins it through
    `Zone.state`.

    This is deliberately NOT a fourth leak signal. Over-extracted groundwater does not
    mean a pipe is leaking; it means a leak in that place costs more. It therefore enters
    fusion as an urgency multiplier on an already-computed leak score, never as evidence
    of a leak. See `services/urgency.py`.
    """

    __tablename__ = "groundwater_stress"
    __table_args__ = (UniqueConstraint("state", "district", name="uq_gw_state_district"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state: Mapped[str] = mapped_column(String(80), index=True)
    district: Mapped[str | None] = mapped_column(String(80), nullable=True)
    assessed_year: Mapped[int] = mapped_column(Integer)
    # Stage of Ground Water Extraction = annual extraction / annual extractable resource.
    # Over 100% means more is taken out each year than comes back in.
    stage_of_extraction_pct: Mapped[float] = mapped_column(Float)
    # CGWB category: Safe / Semi-Critical / Critical / Over-Exploited.
    category: Mapped[str] = mapped_column(String(24))
    source: Mapped[str] = mapped_column(String(80))
    # False until a human has checked the row against the published PDF. The loader
    # ships transcribed figures; nobody should quote them on stage before this flips.
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RainfallObservation(Base):
    """Recent rainfall over a city. Owned by R2 (Data).

    The single biggest false-positive risk in this product: rain greens up a whole city,
    NDVI rises everywhere, and the satellite lane reports leaks that are weather. This
    table is the evidence used to suppress that -- see `pipelines/water/rainfall.py`.
    """

    __tablename__ = "rainfall_observations"
    __table_args__ = (UniqueConstraint("city_code", "observed_on", name="uq_rain_city_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_code: Mapped[str] = mapped_column(String(8), index=True)
    observed_on: Mapped[date] = mapped_column(Date)
    rain_mm_7d: Mapped[float] = mapped_column(Float)
    rain_mm_30d: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(60), default="open-meteo-era5")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ZoneScore(Base):
    """Fusion output: one priority score per zone. Written by R3's fusion engine."""

    __tablename__ = "zone_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    zone_id: Mapped[str] = mapped_column(ForeignKey("zones.id"), index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    satellite_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    billing_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    citizen_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fusion_score: Mapped[float] = mapped_column(Float, index=True)
    confidence: Mapped[str] = mapped_column(String(10))
    signals_used: Mapped[int] = mapped_column(Integer)
    rank: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text)

    # --- pan-India additions, all nullable so existing rows and the MVP contract stand ---
    # `fusion_score` is a percentile *within its own city*, which is what gives each city
    # map its colour spread -- and what makes it meaningless to compare across cities,
    # since every city has a zone at 100. `absolute_score` is the same weighted average
    # before ranking, and is the only one of the two that means the same thing in Kanpur
    # as in Kochi. National ranking uses `priority_score`, which is built from this.
    absolute_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Leak likelihood (`fusion_score`) times a groundwater-urgency multiplier. Ranking by
    # this is what makes a national list defensible: a 70 in over-exploited Punjab
    # outranks a 75 in water-secure Kerala, and the multiplier is shown, not hidden.
    priority_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    urgency_multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)
    groundwater_stress_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    groundwater_category: Mapped[str | None] = mapped_column(String(24), nullable=True)
    # Set when heavy recent rain made the NDVI reading untrustworthy and the satellite
    # signal was down-weighted for it.
    rain_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    rain_mm_7d: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Estimated recoverable water, kilolitres per day, if this zone is repaired.
    water_at_risk_kld: Mapped[float | None] = mapped_column(Float, nullable=True)

    zone: Mapped[Zone] = relationship(back_populates="scores")


class CityScore(Base):
    """National rollup: one row per city per fusion run. Owned by R3 (Backend & Fusion).

    Exists so the zoomed-out national map is a 500-row query instead of a 7,000-polygon
    one. Recomputed by the same `run_fusion` pass that writes `zone_scores`, so the two
    can never drift apart.
    """

    __tablename__ = "city_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_code: Mapped[str] = mapped_column(String(8), index=True)
    city: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(80), index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    zones_scored: Mapped[int] = mapped_column(Integer)
    mean_priority: Mapped[float] = mapped_column(Float)
    max_priority: Mapped[float] = mapped_column(Float, index=True)
    hotspot_zone_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    high_priority_zones: Mapped[int] = mapped_column(Integer, default=0)
    groundwater_stress_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_at_risk_kld: Mapped[float] = mapped_column(Float, default=0.0)
    population_served: Mapped[int] = mapped_column(Integer, default=0)
    rank: Mapped[int] = mapped_column(Integer)
