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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Zone(Base):
    """A municipal water zone / ward sector. Owned by R1 (Satellite & Geo)."""

    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100), index=True)
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

    zone: Mapped[Zone] = relationship(back_populates="scores")
