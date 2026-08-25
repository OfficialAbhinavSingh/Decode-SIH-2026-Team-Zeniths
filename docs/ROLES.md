# Roles — who owns what

6 people, 6 lanes. Lanes are drawn so that **you can finish your lane without waiting for anyone else**,
because `backend/seed.py` fakes every other lane's output.

Rule: you own your folder. You may *read* anything. You may *write* outside your folder only after
telling the owner.

**Roles are final as of 25 Aug 2026.** If your availability changes, say so in the group the same
day — a lane can be reassigned on 26 Aug, not on 3 Sep.

| Role | Person | GitHub | Owns (write access) | Depends on |
|---|---|---|---|---|
| **R1 · Satellite & Geo** | Abhinav | @OfficialAbhinavSingh | `backend/pipelines/satellite/`, `data/samples/zones*.geojson` | nothing |
| **R2 · Data (Billing/NRW)** | Sayali · Saksham | @sayali-rathod-07 · @Saksham0423 | `backend/pipelines/billing/`, `data/samples/billing*.csv` | R1's zone IDs |
| **R3 · Backend & Fusion** | Abhinav · Krishna | @OfficialAbhinavSingh · @Kr0issant | `backend/app/` (models, routers, services/fusion.py) | nothing (owns the contract) |
| **R4 · Frontend & Dashboard** | Abhishek | @Abhi1818Singh | `frontend/` | API contract only |
| **R5 · Automation & Integrations** | Pranjay | @PranjaySrivastava | `automation/n8n/`, `backend/app/routers/reports.py` | `POST /api/reports` |
| **R6 · AI Agent, DevOps & Deploy** | Krishna | @Kr0issant | `render.yaml`, `docker-compose.yml`, `.github/`, Lyzr agent | everyone, at the end |
| **Pitch & Deck** | Sayali · Pranjay | @sayali-rathod-07 · @PranjaySrivastava | `docs/DEMO.md`, slide deck, GTM slide | R6's demo, at the end |

### Split-lane rules (two people on one lane)

R2 and R3 have two owners each. Split by **file**, not by "we'll figure it out":

| Lane | Person A | Person B |
|---|---|---|
| **R2 · Data** | Sayali — `generate.py` (the benchmarked generator + source citations) | Saksham — `nrw.py` + `load.py` (scoring and ingest) |
| **R3 · Backend** | Abhinav — `models.py`, `schemas.py`, routers, DB schema | Krishna — `services/fusion.py` + `backend/tests/` |

Two people editing one file on one afternoon is how you lose an evening to a merge conflict.
Agree the split before you start, and put it in the issue.

Ownership is enforced by [`.github/CODEOWNERS`](../.github/CODEOWNERS) — GitHub requests the right
reviewer automatically.

---

## R1 · Satellite & Geo Data — *Abhinav · hardest + most important; this is the differentiator*

**Your job in one line:** turn free satellite imagery into a number 0–100 per zone that says
"soil here looks abnormally wet/green for this time of year."

Deliver:
1. `data/samples/zones.geojson` — ~30 zone polygons for the chosen city + a pipeline-corridor buffer.
2. A Google Earth Engine script that, for each zone, computes:
   - `ndvi_mean` for the target date window
   - `ndvi_baseline` = median NDVI for the same window across the previous 2–3 years
   - `ndvi_anomaly` = `ndvi_mean - ndvi_baseline`
3. Export → CSV → `backend/pipelines/satellite/load.py` → `POST /api/ingest/satellite`.
4. Normalise anomaly to a 0–100 `score` (see `pipelines/satellite/ndvi.py` stub).

Gotchas you will hit (planned for, see risks R1/R5 in the mentor brief):
- **Rain.** A city-wide green-up right after rain is not a leak. Mitigation for MVP: pick a date
  window with no heavy rain, and score *relative to the city median that same day* so a city-wide
  bump cancels out. Real rain-adjustment is Phase 2 (P4).
- **Clouds.** Use Sentinel-2 SCL band or `CLOUDY_PIXEL_PERCENTAGE < 20` and take a median composite
  over ~15 days, not a single scene.
- **GEE signup takes time.** Do this on day 1, not day 5.

Start: `backend/pipelines/satellite/README.md`

---

## R2 · Data Engineer (Billing / NRW) — *Sayali + Saksham*

**Your job in one line:** produce a believable per-zone "how much water went missing" number.

Deliver:
1. `data/samples/billing.csv` — per zone, per month: `supplied_kl`, `billed_kl`, `connections`, `pipe_length_km`.
2. A **generator** (`backend/pipelines/billing/generate.py`) that creates it from real published
   benchmarks — national NRW ~30–40% (CPHEEO / AMRUT / city water utility annual reports). Cite your
   sources in the file header. A judge *will* ask "where did this data come from."
3. `nrw_pct = (supplied - billed) / supplied * 100`, then normalised to `score` 0–100.
4. Plant 3–5 zones with genuinely high NRW so the demo has something to find — and make sure at
   least 2 of them overlap with R1's satellite hotspots so fusion has a story.

Gotchas:
- Don't make it random noise. Model it: older pipes + higher pressure + longer mains ⇒ higher loss.
- Label the dataset **synthetic** everywhere. Honesty scores better than a bluff that gets caught.

Start: `backend/pipelines/billing/README.md`

---

## R3 · Backend & Fusion — *Abhinav + Krishna · hardest logic*

**Your job in one line:** own the database, own the API, and turn 3 messy scores into 1 defensible number.

Deliver:
1. Freeze `backend/app/models.py` + `schemas.py` against `docs/DATA-CONTRACT.md` by **26 Aug**.
2. All endpoints in the contract, working against seeded data.
3. `backend/app/services/fusion.py` — the core:
   - Weighted average over **only the signals that exist** (missing signal ⇒ renormalise weights,
     never treat missing as zero).
   - Default weights: satellite `0.40`, billing `0.35`, citizen `0.25`.
   - `confidence` = how many signals present + whether they agree.
   - `explanation` = a short human string. This is what the dashboard shows the judge.
4. Tests in `backend/tests/` for the missing-signal and all-agree cases. These are the two the
   judges' questions will land on.

Gotcha: if every zone scores 55–65, the demo is dead. Spread the scores — percentile-rank within
the city rather than using raw values.

Start: `backend/app/services/fusion.py`

---

## R4 · Frontend & Dashboard — *Abhishek*

**Your job in one line:** make the map that wins the demo.

Deliver:
1. Leaflet map, zones coloured by `fusion_score` (green → red).
2. Ranked side list "Top 10 zones to inspect."
3. Click a zone → panel with the 3 sub-scores as bars, the `explanation` string, and the citizen
   reports for that zone.
4. A "why this zone?" view — this single screen is the whole pitch.
5. Mobile-readable. A judge will open it on a phone.

You are **never blocked**: run `python backend/seed.py` and the API returns full fake data on day 1.

Start: `frontend/src/pages/Dashboard.jsx`

---

## R5 · Automation & Integrations (n8n + WhatsApp) — *Pranjay*

**Your job in one line:** let a citizen report a leak from WhatsApp and have it land in our DB.

Deliver:
1. n8n workflow: WhatsApp/Telegram webhook → parse message → geocode or ward-match → `POST /api/reports`.
2. Duplicate handling: 5 people reporting one leak = 1 zone signal with weight, not 5 separate leaks.
3. Fallback web form (`frontend/src/pages/Report.jsx`) — WhatsApp Business API approval can be slow,
   the form must exist so the demo never depends on Meta.
4. Export the workflow JSON to `automation/n8n/` and commit it. Sponsor award ("Best Use of n8n")
   needs it visible in the repo.
5. Phase 2, only if MVP is green: scheduled satellite refresh + alert dispatch.

Start: `automation/n8n/README.md`

---

## R6 · AI Agent, DevOps & Deploy — *Krishna*

**Your job in one line:** it must be live on a URL, and the story must land in 4 minutes.

Deliver:
1. `docker-compose.yml` working for everyone locally by **26 Aug** (unblocks all 5 others).
2. Render deploy: Web Service (API) + Postgres + Static Site (frontend) + Background Worker (fusion
   cron). 3+ services = qualifies for "Best Use of Render."
3. GitHub Actions: lint + tests on PR.
4. `docs/DEMO.md` — 4-minute script, who speaks when, plus a recorded video and a fully seeded local
   fallback for when the venue wifi dies. **It will die.**
5. Slide deck.

Start: `docker-compose.yml`, then `docs/DEMO.md`.

---

## Sync cadence

- **Daily, 15 min, async in the group:** what I finished / what I'm blocked on. Nothing else.
- **Contract change?** Post in the group before pushing. Everything downstream breaks otherwise.
- **Blocked more than 2 hours? Say it.** Two weeks is short.

## How work actually lands

Read [`CONTRIBUTING.md`](../CONTRIBUTING.md) once, properly, before your first PR. Short version:

- Branch `<type>/<lane>-<thing>` off fresh `main` — e.g. `feat/r1-ndvi-baseline-composite`
- **No direct pushes to `main`.** `main` is protected; the push will be rejected.
- PR uses the template. Every section filled. **AI-agent use must be declared** (§7).
- @OfficialAbhinavSingh reviews and is the **only** person who merges.
