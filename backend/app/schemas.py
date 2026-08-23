"""Request/response shapes. Mirrors the API section of docs/DATA-CONTRACT.md."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    city: str
    ward: str | None = None
    centroid_lat: float
    centroid_lon: float
    geojson: dict
    pipe_length_km: float | None = None
    population: int | None = None


class SatelliteSignalIn(BaseModel):
    zone_id: str
    observed_on: date
    ndvi_mean: float
    ndvi_baseline: float
    ndvi_anomaly: float | None = None
    wetness_index: float | None = None
    cloud_pct: float | None = None
    score: float = Field(ge=0, le=100)
    source: str = "sentinel2-gee"

    @model_validator(mode="after")
    def fill_anomaly(self) -> "SatelliteSignalIn":
        if self.ndvi_anomaly is None:
            self.ndvi_anomaly = self.ndvi_mean - self.ndvi_baseline
        return self


class BillingSignalIn(BaseModel):
    zone_id: str
    period_start: date
    period_end: date
    supplied_kl: float
    billed_kl: float
    nrw_pct: float | None = None
    score: float = Field(ge=0, le=100)
    is_synthetic: bool = True

    @model_validator(mode="after")
    def fill_nrw(self) -> "BillingSignalIn":
        if self.nrw_pct is None and self.supplied_kl > 0:
            self.nrw_pct = (self.supplied_kl - self.billed_kl) / self.supplied_kl * 100
        return self


class SignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    zone_id: str
    score: float


class SatelliteSignalOut(SignalOut):
    observed_on: date
    ndvi_mean: float
    ndvi_baseline: float
    ndvi_anomaly: float
    wetness_index: float | None = None
    source: str


class BillingSignalOut(SignalOut):
    period_start: date
    period_end: date
    supplied_kl: float
    billed_kl: float
    nrw_pct: float
    is_synthetic: bool


class ReportIn(BaseModel):
    """A citizen leak report. Either zone_id, or lat+lon so we can match a zone."""

    channel: str = "web"
    reporter_hash: str | None = None
    description: str | None = None
    lat: float | None = None
    lon: float | None = None
    zone_id: str | None = None
    media_url: str | None = None

    @model_validator(mode="after")
    def need_a_location(self) -> "ReportIn":
        if self.zone_id is None and (self.lat is None or self.lon is None):
            raise ValueError("provide zone_id, or both lat and lon")
        return self


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    zone_id: str | None
    reported_at: datetime
    channel: str
    description: str | None
    status: str


class ZoneSignalsOut(BaseModel):
    satellite: list[SatelliteSignalOut]
    billing: list[BillingSignalOut]
    citizen: list[ReportOut]


class ScoreOut(BaseModel):
    zone_id: str
    name: str
    rank: int
    fusion_score: float
    confidence: str
    signals_used: int
    satellite_score: float | None
    billing_score: float | None
    citizen_score: float | None
    explanation: str
    computed_at: datetime


class IngestResult(BaseModel):
    inserted: int


class FusionResult(BaseModel):
    zones_scored: int
    city: str
