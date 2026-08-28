# Scope — what we build, what we don't

Mentor's guidance (23 Aug 2026):

> "Focus on building a working MVP first. Don't try to implement everything at once.
> Prioritise the core problem, build what you are confident you can deliver, and keep
> the rest as future enhancements."

We are following this literally. Below is the line.

---

## ✅ MVP — must be working and demoable on 5 Sep

This is the **only** list that counts. If something here is not done, nothing below it matters.

| # | Thing | Owner role | Definition of done |
|---|---|---|---|
| M1 | One city, ~30 zones, loaded in DB with polygons | R1 Satellite/Geo | `GET /api/zones` returns 30 zones with geojson |
| M2 | Satellite NDVI anomaly score per zone | R1 Satellite/Geo | Every zone **with a cloud-free observation** has a `satellite_signals` row with `score` 0–100. Zones without one carry **no satellite signal** rather than a placeholder — 21 of 30 on the 25 Aug 2026 export. See the cloud-cover note below. |
| M3 | Billing/NRW gap score per zone | R2 Data | Every zone has a `billing_signals` row with `nrw_pct` + `score` |
| M4 | Citizen report intake → DB | R5 Automation | A WhatsApp message (or web form fallback) creates a `citizen_reports` row |
| M5 | Fusion engine → one priority score + rank | R3 Backend/Fusion | `POST /api/fusion/run` fills `zone_scores`; `GET /api/scores` returns ranked list |
| M6 | Map dashboard: heatmap + ranked list + zone detail | R4 Frontend | Open browser, see coloured map, click zone, see the 3 sub-scores + why |
| M7 | Deployed and reachable on a public URL | R6 DevOps | Judge opens a link on their phone, it works |
| M8 | 4-minute demo script that survives no-internet | R6 DevOps/Demo | Recorded video + seeded local fallback |

**Satellite is the differentiator — it does not get cut.** But see the shortcut in M2 below.

### Cloud cover is a real limit, and we state it rather than paper over it

M2 originally read *"every zone has a `satellite_signals` row"*. That is not achievable and
was never going to be. On the 25 Aug 2026 export, **9 of 30 zones** came back with an empty
`ndvi_mean` — monsoon cloud, masked per-pixel by Sentinel-2's scene classification layer
across the whole 30-day composite window:

```
Z-006  Z-011  Z-012  Z-016  Z-017  Z-021  Z-022  Z-023  Z-026
```

Those zones now show **no satellite signal at all**, and the fusion engine treats the signal
as absent rather than zero. `python seed.py --skip satellite` is what keeps that honest:
seeding a placeholder row for every zone invented readings for zones that had none, and the
top-ranked zone in the demo was one of them.

Widening the window past 30 days would trade "current condition" for coverage, and
Sentinel-1 SAR sees through cloud but is Phase 2. **A zone running on two signals with a
label saying so is a better answer than a zone running on three where one is fabricated.**

### MVP shortcuts we are taking on purpose

These are engineering decisions, not laziness. Write them on the slide.

| Shortcut | Instead of | Why |
|---|---|---|
| **Pre-computed** NDVI exported from Google Earth Engine to CSV, then imported | Live GEE API call on every request | GEE auth + quota is the #1 thing that can eat 3 days. Export once, import, done. Live fetch is Phase 2. |
| **Synthetic billing data**, generated from published CPHEEO/AMRUT NRW benchmarks (~30–40% national avg) | Real municipal billing data | No city will hand us billing data in 2 weeks. We label it clearly as synthetic and show the generator. |
| **`geojson` stored as JSONB**, no PostGIS | PostGIS spatial queries | Fusion is per-`zone_id`, not spatial. Skipping PostGIS removes an entire class of setup pain on Render. |
| **Rule-based fusion** (weighted score) | ML model | Explainable, tunable live in front of a judge, zero training data needed. This is a feature, not a compromise. |
| **No auth** | Login/roles | Public demo dashboard. Auth adds zero judge points. |

---

## 🔜 Phase 2 — build only after every M above is green

Do not start these early. Seriously.

- **P1** Live scheduled satellite refresh (n8n cron → GEE → `/api/ingest/satellite`)
- **P2** Lyzr AI triage agent — turns a zone's raw scores into a plain-language crew brief
- **P3** Alert dispatch — auto-notify a ward engineer on WhatsApp when a zone crosses a threshold
- **P4** Rain-adjustment: pull IMD/open rainfall data and suppress NDVI spikes right after rain (this directly answers our own risk R1)
- **P5** Water-quality module (the second half of PS3) — turbidity/pH from any open state-board dataset

## ❌ Not doing — say this out loud if a judge asks

- Physical IoT sensors / flow meters — that's exactly the expensive approach we're arguing against
- Training an ML leak-classifier — no labelled leak dataset exists at our scale
- Mobile app — WhatsApp *is* the mobile app
- Multi-city / multi-tenant — one city, done well

---

## Milestone dates

| Date | Gate |
|---|---|
| **26 Aug** | Contract frozen, everyone's local env runs, seeded map visible |
| **30 Aug** | All 3 signals writing real (not seeded) rows for at least 10 zones |
| **2 Sep** | Fusion + dashboard end-to-end on the deployed URL |
| **3 Sep** | Feature freeze. Only bugfixes + demo polish after this. |
| **4 Sep** | Demo rehearsed 3×, video recorded, offline fallback tested |
| **5 Sep** | Finale |
