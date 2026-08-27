# Billing / NRW pipeline — R2

Turn "water supplied vs water billed" into a `0–100` "water is going missing here" score per zone.

## The concept, plainly

**Non-Revenue Water (NRW)** = water a utility puts into the network but never gets paid for.
Some of it is theft and metering error; a large share is physical leakage.

```
nrw_pct = (supplied_kl − billed_kl) / supplied_kl × 100
```

A zone at 50% NRW when the city average is 32% is losing water somewhere. That's the signal.

## Where the numbers come from — read this before a judge asks

We do **not** have a real municipal billing feed, and no city will hand one over in two weeks.
So `generate.py` produces a **synthetic** dataset that is *calibrated to published benchmarks*,
not invented:

- India's national NRW average sits roughly in the **30–40%** band (CPHEEO manual on water
  supply; AMRUT / Jal Jeevan Mission programme documents; individual city utility annual reports).
- Loss correlates with **pipe age**, **network pressure**, and **mains length per connection** —
  so we model it from those, not from `random()`.

Every generated row is stored with `is_synthetic = true`. **Say this on the slide.** A clearly
labelled synthetic dataset with a cited generator scores better than a bluff that gets caught in Q&A.

Put your actual source URLs in the header of `generate.py`. That file is the answer to
"where did this data come from."

## Deliverables

1. `data/samples/billing.csv`
2. `generate.py` — the generator, with sources cited
3. `load.py` — scores it and POSTs to `/api/ingest/billing`

## CSV columns

```
zone_id,period_start,period_end,supplied_kl,billed_kl,connections,pipe_age_years
Z-001,2026-07-01,2026-07-31,18400,11200,1420,31
```

## Run

All commands are run from the `backend/` directory.

```bash
# Step 1: generate billing.csv from zones.geojson
# --hotspots: comma-separated zone IDs to force into 45-58% NRW band.
# Coordinate with R1 (@OfficialAbhinavSingh) to get the satellite hotspot zone IDs.
python -m pipelines.billing.generate \
    --zones ../data/samples/zones.geojson \
    --hotspots Z-014,Z-025,Z-019,Z-012,Z-005 \
    --out ../data/samples/billing.csv

# Step 2: score and verify locally (no API needed)
python -m pipelines.billing.load ../data/samples/billing.csv --dry-run

# Step 3: ingest to the running API (seed.py must have run first so zone FKs exist)
python seed.py
python -m pipelines.billing.load ../data/samples/billing.csv
```

Expected dry-run output: 30 zones scored, worst-first table, top 5 zones showing `[HOTSPOT]`.

## Two things that make or break this lane

1. **Plant the leaks.** Give 3–5 zones genuinely high NRW, and make **at least 2 of them overlap
   with R1's satellite hotspots**. That overlap is the entire demo — it's what "all three signals
   agree" means on screen. **Current hotspots: Z-014, Z-025, Z-019, Z-012, Z-005** (chosen from
   R1's `ndvi_export.csv` highest anomaly zones — confirm with @OfficialAbhinavSingh).
2. **Don't use flat noise.** If every zone is 30±3%, fusion has nothing to rank and the map is one
   colour. Model old-pipe zones as genuinely worse. Scoring uses percentile-rank (`nrw.py`) so
   the map always has full colour spread regardless of the absolute NRW values.
