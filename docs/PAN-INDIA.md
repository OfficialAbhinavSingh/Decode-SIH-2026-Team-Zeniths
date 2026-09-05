# Scaling beyond Jaipur

What it actually takes to run NeerDrishti on any Indian city, what is already solved, and
what is not available at any price. Written so nobody on the team promises a judge
something we cannot deliver.

Owner: R1 (Satellite & Geo). Status: generator shipped, signals partly blocked.

---

## The short version

Going pan-India is **not an architecture change**. It never was. `list_zones(city=)`,
`run_fusion(db, city)` and `GET /api/scores?city=` are already parameterised, and
production returns `[]` for `?city=Pune` rather than erroring. Adding a city is a data
load.

It is a **data** problem, and it splits cleanly in two:

| Layer | Pan-India today? |
|---|---|
| Zone geometry | ✅ Solved — `build_city_zones.py`, OpenStreetMap |
| Satellite signal | ✅ Already global — Sentinel-2 covers every Indian city |
| Citizen signal | ✅ Works anywhere there is an intake channel |
| **Billing / NRW signal** | ❌ **Not publicly available per-zone for any Indian city** |

That last row is the whole story. Read it before promising a national map.

---

## 1. Zone geometry — solved

```bash
cd backend
python -m pipelines.satellite.build_city_zones \
    --city Indore --state "Madhya Pradesh" \
    --out ../data/samples/zones.indore.geojson
python -m pipelines.satellite.load_zones ../data/samples/zones.indore.geojson
```

The generator pulls the real municipal boundary from OpenStreetMap and tiles it with the
same 0.012° (~1.3 km) fishnet `seed.py` uses. Output schema is byte-identical to
`data/samples/zones.geojson`, so `load_zones.py` needs no changes — it already handles
MultiPolygon, which real ward boundaries frequently are.

### What this fixes about Jaipur

The committed demo grid is a hand-placed 5×6 square that is **not tied to any real
boundary**:

| | zones | area | share of JMC |
|---|---|---|---|
| `data/samples/zones.geojson` (current demo) | 30 | ~50 km² | **~11%** |
| Jaipur Municipal Corporation (OSM `rel/7923743`, admin_level 8) | 252 | ~446 km² | 100% |

The 252-zone JMC file is **deliberately not committed**. Generating it is one command, but
loading it renumbers every zone — `Z-005` stops being the zone the demo script names — so
it must not land in the same week as a recorded demo:

```bash
python -m pipelines.satellite.build_city_zones \
    --city Jaipur --state Rajasthan --out ../data/samples/zones.jaipur-mc.geojson
```

`data/samples/zones.indore.geojson` (70 zones, Indore City, OSM `rel/16636427`,
admin_level 9) **is** committed, as a worked example that touches no existing zone id.

So "we monitor Jaipur" currently means "we monitor a 7.5 × 6.7 km square in the middle of
Jaipur". The generator makes that claim true instead of approximately true.

### Coverage is good but NOT universal

Verified against OSM:

| City | Boundary found | Level |
|---|---|---|
| Jaipur | Jaipur Municipal Corporation | 8 |
| Bengaluru | Bengaluru Central City Corporation | 8 |
| Chennai | Chennai Corporation | 8 |
| Indore | Indore City | 9 |
| **Varanasi** | **none** | — |
| **Kochi** | **none** | — |

**Do not claim "works for every Indian city."** It works for many. For the rest the script
falls back to admin_level 7/6 (tehsil/district) with a loud warning, because a district
boundary tiled at 1.3 km is mostly farmland and will produce garbage NDVI anomalies.

### Two traps the script guards against

- **`--state` is not optional in practice.** There is a Jaipur in Rajasthan and another in
  Purulia, West Bengal. Without the filter the generator silently builds the wrong city.
- **`MAX_ZONES = 2000`.** A district boundary at 0.012° yields tens of thousands of cells,
  which would quietly overwhelm the loader and the GEE export. It refuses instead.

### These are still not DMAs

The cells are a fishnet clipped to a real boundary — **DMA proxies**, not District Metered
Areas. A real DMA is bounded by closed valves and fed through one metered inflow; it
follows pipe topology, not a lat/lon grid. Grid cells also inherit the **Modifiable Areal
Unit Problem**: change `--cell` and the scores shift, because the boundaries are arbitrary.

Swapping in a utility's real DMA boundaries needs **no code change** — `load_zones.py`
takes any Polygon/MultiPolygon. That is the honest answer when a judge asks.

---

## 2. Satellite — already global, but the export script must change

Sentinel-2 covers all of India; nothing is blocked. But `gee_ndvi.js` has the 30 Jaipur
polygons **pasted inline**, and its own header says what to do instead:

> *If you switch to real ward boundaries with many more/larger polygons, upload
> `data/samples/zones.geojson` as a Table asset instead.*

252 zones for Jaipur alone will not fit inline. Upload the geojson as an Earth Engine
Table asset and replace the `zones` variable with
`ee.FeatureCollection('users/<you>/neerdrishti_zones')`.

---

## 3. Billing / NRW — the wall

**No Indian city publishes non-revenue water per zone or per ward.** AMRUT publishes
Service Level Benchmarks per *city*; CPHEEO publishes national ranges. Per-DMA inflow
metering is exactly the thing most Indian utilities have not built yet — which is a large
part of why NRW is 30–40% in the first place.

`backend/pipelines/billing/generate.py` is honest about this already: every row is
`is_synthetic=true` and the model is calibrated to published benchmarks with citations.

**What pan-India expansion actually buys you, then, is a satellite-only map.** One signal,
`COVERAGE_FACTOR = 0.70`, `confidence = "low"` on every single zone. That is a defensible
product — it is a screening layer, and a lead is still worth a crew — but say it plainly.

**The one real upgrade available:** AMRUT city-level NRW is real and public. Feeding a
city's *actual* published NRW in as the `city_baseline` argument to `nrw.to_score()`
replaces a national 32% assumption with a measured city figure. The per-zone distribution
stays modelled; the anchor becomes real.

> **Unverified.** The 2026-09-05 research pass into data.gov.in, India-WRIS, CGWB, CPCB and
> ejalshakti did not finish. Nobody should cite a specific AMRUT figure, endpoint or
> dataset ID from this document until it is checked by hand.

---

## 4. Highest-value dataset additions

From a 2026-09-05 review of the Google Earth Engine catalogue. **Not yet implemented** —
this is a shortlist, not a changelog.

### Worth doing

1. **Land-cover masking — fixes the irrigation false positive.**
   `GOOGLE/DYNAMICWORLD/V1` (10 m, per-Sentinel-2-scene) and `ESA/WorldCover/v200`
   (cropland = class 40). Dynamic World is per-scene, not a static annual map, so the
   `crops` probability can be read *for the same date as the NDVI observation* — a
   seasonal flip is a cropping cycle, a persistent anomaly on a `built`/`grass` pixel is a
   leak candidate. This turns land cover from a blunt filter into a temporal discriminator
   and is the single strongest answer to "isn't that just irrigation?".
2. **Rainfall correction.** `NASA/GPM_L3/IMERG_V07` (~11 km, ~1 day latency). CHIRPS is
   better for the historical baseline but runs ~5 weeks behind, which is useless for
   alerting. Regress zone NDVI anomaly against an antecedent-precipitation index and flag
   the *residual*, rather than hard-suppressing after rain — that keeps monsoon data.
3. **Water quality — the unbuilt half of PS3.** NDTI turbidity from Sentinel-2
   (validated on Indian reservoirs at R²≈0.81), masked to permanent water by
   `JRC/GSW1_4/GlobalSurfaceWater` eroded 2–3 pixels inward to kill shoreline
   contamination. **Caveat to disclose:** Sen2Cor is specified for land, not water. Report
   relative indices and trends, never absolute mg/L without in-situ calibration.

### Cheap wins on the existing script

- **Cloud Score+** (`GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED`) instead of SCL masking —
  materially better on thin cirrus and cloud shadow, which are exactly what produce
  spurious NDVI spikes. ~5 lines.
- **NDMI** = (B8A − B11)/(B8A + B11). Responds to water content directly, where NDVI only
  sees the lagged greening. NDMI rising *before* NDVI is itself a leak discriminator.

### Do not use

| Dataset | Why not |
|---|---|
| **ECOSTRESS** (`NASA/ECOSTRESS/L2T_LSTE/V2`) | **Only Los Angeles tiles are ingested into GEE.** Verified on the catalogue page 2026-09-05. For an Indian city this data does not exist. |
| **GRACE / GRACE-FO** | True resolution ~300 km against 1.3 km zones. Regional context only, clearly labelled. |
| **SMAP / ASCAT** | 9 km posting hides a ~36 km footprint. A whole city sits in one or two pixels. Legitimate only as a city-wide antecedent-wetness covariate. |
| **Sentinel-3 OLCI** | GEE hosts top-of-atmosphere radiance only — no L2 water products. 300 m pixels miss most Indian urban tanks. |
| **"ASTERRA-style leak detection with Sentinel-1"** | ASTERRA is **L-band**; Sentinel-1 is **C-band**, sensing only the top few cm. Sentinel-1 is genuinely useful as a cloud-immune near-surface moisture channel — but claiming subsurface detection invites the one question that unravels the whole SAR story. |

---

## 5. Operational limits

- **Public Overpass is not a bulk API.** It returned HTTP 429 and then refused connections
  after ~8 city queries. The generator fails over across three mirrors, but generating
  hundreds of cities needs a Geofabrik India extract processed offline.
- **Licence.** OpenStreetMap data is ODbL. Attribution is required anywhere the derived
  boundaries are displayed — the dashboard already carries OSM attribution on both maps.
