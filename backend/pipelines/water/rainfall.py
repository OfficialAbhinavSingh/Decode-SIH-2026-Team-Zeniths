"""Rainfall context -- the de-confounder for the satellite signal.

Owner: R2 (Data).

THE RISK THIS CLOSES: our satellite lane calls a zone suspicious when its NDVI runs above
its own 3-year baseline, on the theory that soil over a leaking main stays wetter and
greener. Rain does exactly the same thing to exactly the same pixels. Run this product
through an Indian monsoon without a rainfall check and every zone in the city lights up
red on the same day -- which is not a leak map, it is a weather map with extra steps.

`ndvi.city_relative_anomaly()` already subtracts the city-wide median anomaly, which
removes rain that fell evenly. That handles the common case and costs nothing. What it
cannot do is tell you *when the whole reading is untrustworthy*: after 60 mm in a week,
the surviving between-zone differences are drainage and soil type, not leaks, and the
honest move is to say so and lean on billing and citizen reports instead.

So this module produces a per-city rainfall record, and fusion uses it to down-weight --
never to delete -- the satellite signal, and to say in the explanation why.

The scoring half of this lane lives in `app/services/rain.py`; this module only fetches.

SOURCE: Open-Meteo Historical Weather API, ERA5 / ERA5-Land reanalysis at ~9 km,
free for non-commercial use, no API key, global coverage including all of India.
  https://open-meteo.com/en/docs/historical-weather-api
  ERA5: Hersbach et al. (2020), Copernicus Climate Change Service.
Chosen over IMD's gridded product because IMD's download portal is neither keyless nor
scriptable, and a demo that cannot refresh its own data is a screenshot. Swap the fetch
for IMD when a real deployment can hold the credentials.

    python -m pipelines.water.rainfall --cities ../data/india/cities.csv \
        --out ../data/india/rainfall.csv
"""

import argparse
import csv
import os
import sys
from datetime import date, timedelta

from app.services.rain import (  # noqa: F401  re-exported for the CLI and n8n
    RAIN_SATURATION_MM_7D,
    RAIN_SUSPECT_MM_7D,
    SATELLITE_WEIGHT_FLOOR,
    is_flagged,
    satellite_confidence,
)

WINDOW_SHORT_DAYS = 7
WINDOW_LONG_DAYS = 30

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

def summarise(daily_mm: list[float], observed_on: date) -> dict:
    """Collapse a daily precipitation series into the two windows fusion cares about."""
    clean = [0.0 if v is None else float(v) for v in daily_mm]
    short = clean[-WINDOW_SHORT_DAYS:] if clean else []
    long = clean[-WINDOW_LONG_DAYS:] if clean else []
    return {
        "observed_on": observed_on.isoformat(),
        "rain_mm_7d": round(sum(short), 2),
        "rain_mm_30d": round(sum(long), 2),
        "source": "open-meteo-era5",
    }


def fetch_city(client, lat: float, lon: float, end: date, days: int = WINDOW_LONG_DAYS) -> list[float]:
    """Daily precipitation for the `days` before `end`.

    ERA5 reanalysis lags real time by about five days, so a window ending today would
    come back with trailing nulls. We ask the archive for what it has and let the
    forecast endpoint's `past_days` fill the recent tail -- between them the last 30 days
    are always complete, which is what the 7-day window depends on.
    """
    start = end - timedelta(days=days - 1)
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "precipitation_sum",
        "timezone": "Asia/Kolkata",
    }
    response = client.get(ARCHIVE_URL, params=params, timeout=60)
    response.raise_for_status()
    series = response.json().get("daily", {}).get("precipitation_sum", []) or []

    if series and series[-1] is not None:
        return series

    # Archive has not caught up: top the tail up from the forecast endpoint, which serves
    # the same variable for the recent past.
    recent = client.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "precipitation_sum",
            "past_days": min(days, 92),
            "forecast_days": 1,
            "timezone": "Asia/Kolkata",
        },
        timeout=60,
    )
    recent.raise_for_status()
    tail = recent.json().get("daily", {}).get("precipitation_sum", []) or []
    return tail[-days:] if tail else series


def main() -> int:
    import httpx

    from ..geo.registry import read_csv

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cities", default="data/india/cities.csv")
    parser.add_argument("--out", default="data/india/rainfall.csv")
    parser.add_argument("--top", type=int, default=None, help="only the N largest cities")
    parser.add_argument("--end", default=None, help="YYYY-MM-DD, defaults to today")
    args = parser.parse_args()

    cities = read_csv(args.cities)
    if args.top:
        cities = cities[: args.top]
    end = date.fromisoformat(args.end) if args.end else date.today()

    rows = []
    failures = 0
    with httpx.Client() as client:
        for index, city in enumerate(cities, start=1):
            try:
                series = fetch_city(client, city["lat"], city["lon"], end)
                row = summarise(series, end)
            except Exception as exc:  # one city's outage must not lose the whole run
                failures += 1
                print(f"  ! {city['city_code']} {city['name']}: {exc}", file=sys.stderr)
                continue
            row["city_code"] = city["city_code"]
            rows.append(row)
            if index % 50 == 0:
                print(f"  ... {index}/{len(cities)}")

    if not rows:
        print("no rainfall rows fetched", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    fields = ["city_code", "observed_on", "rain_mm_7d", "rain_mm_30d", "source"]
    with open(args.out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: r[k] for k in fields} for r in rows)

    wet = [r for r in rows if is_flagged(r["rain_mm_7d"])]
    print(f"wrote {len(rows)} cities to {args.out} ({failures} failed)")
    print(f"{len(wet)} cities over {RAIN_SUSPECT_MM_7D:.0f} mm in 7 days -- satellite down-weighted there")
    for row in sorted(rows, key=lambda r: -r["rain_mm_7d"])[:5]:
        print(f"  {row['city_code']}  {row['rain_mm_7d']:6.1f} mm/7d  conf={satellite_confidence(row['rain_mm_7d'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
