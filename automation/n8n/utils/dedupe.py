"""Spatial-temporal deduplication engine for citizen leak reports.

Rules:
1. Same reporter submitting multiple times within 6 hours -> Duplicate/Update (filtered).
2. Multiple distinct reporters within ~200m radius within 6 hours -> Corroborating cluster.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timezone


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in meters."""
    r = 6371000.0  # Earth's mean radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


@dataclass
class ReportRecord:
    reporter_hash: str
    lat: float | None
    lon: float | None
    zone_id: str | None
    timestamp: datetime
    description: str


class ReportDeduplicator:
    """In-memory spatial-temporal deduplicator with time-window eviction."""

    def __init__(self, window_hours: float = 6.0, radius_meters: float = 200.0) -> None:
        self.window_hours = window_hours
        self.radius_meters = radius_meters
        self._recent_reports: list[ReportRecord] = []

    def _cleanup_old(self, current_time: datetime) -> None:
        """Evict reports older than window_hours."""
        cutoff_seconds = self.window_hours * 3600
        self._recent_reports = [
            r for r in self._recent_reports
            if (current_time - r.timestamp).total_seconds() <= cutoff_seconds
        ]

    def check_and_record(
        self,
        reporter_hash: str,
        lat: float | None,
        lon: float | None,
        zone_id: str | None,
        description: str,
        timestamp: datetime | None = None,
    ) -> tuple[bool, str, int]:
        """Check if incoming report is a duplicate or part of an active cluster.

        Returns:
            (is_duplicate: bool, reason: str, cluster_count: int)
        """
        now = timestamp or datetime.now(timezone.utc)
        self._cleanup_old(now)

        # 1. Check exact same reporter within window
        for past in self._recent_reports:
            if past.reporter_hash == reporter_hash:
                return True, "duplicate_same_reporter_within_window", 1

        # 2. Check spatial proximity if GPS coordinates exist
        cluster_count = 1
        if lat is not None and lon is not None:
            for past in self._recent_reports:
                if past.lat is not None and past.lon is not None:
                    dist = haversine_distance_meters(lat, lon, past.lat, past.lon)
                    if dist <= self.radius_meters:
                        cluster_count += 1

        # Record this valid report
        self._recent_reports.append(
            ReportRecord(
                reporter_hash=reporter_hash,
                lat=lat,
                lon=lon,
                zone_id=zone_id,
                timestamp=now,
                description=description,
            )
        )

        return False, "new_report_accepted", cluster_count
