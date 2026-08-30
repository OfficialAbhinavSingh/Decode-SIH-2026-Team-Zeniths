# Demo script — 4 minutes

**Owner:** R6 · **Everyone rehearses.** Final run-through by **3 Sep**.

Every number, zone name and behaviour on this page was read out of a running instance on
**28 Aug 2026** — real Postgres, the real Sentinel-2 export, the current billing generator.
Nothing here is written from memory. If the data changes, re-run
[Verify before you present](#verify-before-you-present) and update this file. A figure on
this page that no longer matches the screen is worse than no figure at all.

> **The ranks below assume PR #11 (fusion coverage discount) is merged.** Before it, the top
> of the repair list was a single-signal zone whose own explanation read *"treat as a lead,
> not a finding"*. Every figure on this page was re-verified against `main` with #11 merged.

---

## ✅ Resolved — the deployment is serving our real data

This section was a blocker until 29 Aug 2026: production was serving `seed.py`'s invented
satellite scores and pre-replant billing, and its top zone claimed *"all three signals
agree"* at high confidence. R6 ran the real load sequence against it.

Re-verified against the hosted API on **30 Aug 2026** — anyone can repeat this, no clone needed:

```bash
curl -s https://neerdrishti-api.onrender.com/api/scores | head
curl -s https://neerdrishti-api.onrender.com/api/zones/Z-005/signals
```

| Check | Expected | Live on 30 Aug |
|---|---|---|
| Satellite provenance | `sentinel2-gee`, not `seed` | ✅ `"source": "sentinel2-gee"` |
| Cloud-masked zones | no satellite signal at all | ✅ `Z-016` returns `"satellite_score": null`, `"signals_used": 2` |
| Z-016 confidence | `medium` — two of three | ✅ `"two of three signals available"`, 44% NRW |
| Z-005 (main beat) | rank 3, all three signals | ✅ rank 3, `signals_used: 3`, score 93.1 |
| Billing honesty | every row flagged | ✅ `"is_synthetic": true` |

The old figure in this file was *high confidence, 46% NRW*. It is now *medium, 44%* — which
is the correct answer, because `Z-016` was one of the nine cloud-masked zones and never had
a satellite observation to be confident about.

`./scripts/verify-demo.sh` runs this and twelve more checks in one command.

---

### Why nine zones have no satellite score at all

The Sentinel-2 export has an **empty `ndvi_mean`** for nine zones — they were fully
cloud-masked on 25 Aug 2026, so there was no usable observation:

```
Z-006  Z-011  Z-012  Z-016  Z-017  Z-021  Z-022  Z-023  Z-026
```

That is correct behaviour, and `seed.py --skip satellite` is what keeps it correct: those
zones honestly run on two signals instead of being handed a fabricated one. **Say this
before a judge finds it.** It is a much better answer than being caught.

---

## The 4-minute script

| Time | Who | Screen | Beat |
|---|---|---|---|
| 0:00–0:30 | Pitch | Slide 1 | India loses a large share of treated water before it reaches a tap. Finding the leak normally means burying acoustic sensors — which most municipal budgets cannot carry. |
| 0:30–1:00 | Pitch | Slide 2 | We use three things a city already has for free: satellite imagery, its own billing records, and its residents. No new hardware. |
| 1:00–1:40 | Demo | Dashboard | 30 zones across Jaipur, ranked. Red is inspect-first. Every row says how many of the three signals it actually had. |
| 1:40–2:40 | Demo | **Ward 1 - Sector 5** | The main beat — [below](#1402240--main-beat--ward-1---sector-5-z-005-rank-3). |
| 2:40–3:05 | Demo | **Ward 5 - Sector 1** | The honest conflict — [below](#2403305--the-honest-conflict--ward-5---sector-1-z-025-rank-6). |
| 3:05–3:35 | Demo | Telegram / `/report` | A resident reports a leak, it lands in a zone, the score moves. |
| 3:35–4:00 | Close | Slide 3 | Zero new hardware, public data, explainable score. Next: rainfall adjustment, live refresh, repair-outcome feedback. |

---

### 1:40–2:40 · Main beat · Ward 1 - Sector 5 (`Z-005`, rank #3)

Open **this** zone, not the #1. It is the highest-ranked zone that carries all three signals
*and* a real Sentinel-2 observation. The #1 and #2 zones are two-signal zones — perfectly
honest, but they cannot carry the "three independent sources" line.

> "Ward 1 - Sector 5. Priority 93 out of 100, rank 3 of 30.
>
> **Satellite.** Sentinel-2 measured NDVI 0.265 over this polygon on 25 August. Its own
> three-year baseline for the same calendar window is 0.191 — this ground is 0.07 greener
> than it has any business being. After we subtract the city-wide median anomaly, it scores
> 57.
>
> **Billing.** 52% of the water supplied to this zone was never billed.
>
> **Residents.** Two reports in the last 30 days.
>
> Now read what the system says about itself — **medium** confidence: *'all three signals
> present but they disagree, verify before digging.'* It is not claiming certainty. The
> three numbers are 57, 93 and 40. They point the same direction, not the same distance.
> That sentence is the difference between a tool an engineer trusts and one they stop
> opening after the first wasted dig."

**The confidence contrast**, if you have the seconds. Search `Ward 5 - Sector 4` (`Z-028`,
rank #27):

> "This one is **high** confidence — all three signals agree. And it is 27th of 30. High
> confidence does not mean high priority. It means the sources told the same story. Here
> they agreed that nothing is wrong."

**The coverage contrast**, if a judge is already leaning in. Scroll to `Ward 4 - Sector 5`
(`Z-023`, rank #4):

> "This is our fourth priority and it is **low** confidence — one signal, billing only, no
> satellite observation and nobody has reported it. The system says *'treat as a lead, not
> a finding.'* It is discounted for that, so it sits below the corroborated zones — but we
> do not delete it, because 51% unbilled water is still worth a look."

### 2:40–3:05 · The honest conflict · Ward 5 - Sector 1 (`Z-025`, rank #6)

> "Ward 5 - Sector 1 is 6th, and its satellite score is **zero**. Sentinel-2 says this
> ground is 0.18 NDVI *drier* than its own baseline. But 57% of the water supplied here is
> unbilled — the worst in the city.
>
> So it ranks on billing alone, and that is the point. A leak under tarmac will never green
> anything, and a metering fault looks identical from orbit. If we had shipped satellite
> alone, we would have missed the worst-billing zone in Jaipur."

### 3:05–3:35 · The citizen loop

Send a message to the Telegram bot **@zeniths_neerdrishti_bot**, or open `/report` in the
dashboard and submit with coordinates. Then `POST /api/fusion/run` and reload.

> "Any resident, any Indian language — Sarvam AI translates it, we hash the phone number so
> we never store it, the report lands in the right zone by its coordinates, and the score
> moves."

**Rehearse the channel you will actually use.** Telegram is the one wired to a live
credential today. WhatsApp Business API approval is not something to gamble a demo on. The
web form at `/report` depends on nobody's approval and was verified end to end — a
submission at `26.9124, 75.7873` returns *"Logged against zone Z-022"*.

---

## Rehearse the hard questions

| Question | Answer |
|---|---|
| **"Is the billing data real?"** | No. Synthetic, generated from published CPHEEO / AMRUT / Jal Jeevan Mission non-revenue-water benchmarks. Every row carries `is_synthetic = true`, the dashboard says so on screen unprompted, and the generator is at `backend/pipelines/billing/generate.py`. Offer to open it. |
| **"Is the satellite data real?"** | Yes — a real Sentinel-2 L2A export via Google Earth Engine, for **21 of our 30 zones**, observed 25 Aug 2026. The other nine were fully cloud-masked that day and carry no satellite signal at all. Volunteer this. |
| **"What if it just rained?"** | `city_relative_anomaly()` subtracts the city-wide median anomaly from every zone. A city that greens up together cancels out; what survives is a zone wet for a reason its neighbours are not. Explicit rainfall data is the next build, not a claim we make today. |
| **"How do you know it's a leak and not a park?"** | The baseline is not a city average — it is *that same polygon*, same calendar window, median of the previous three years (`gee_ndvi.js`). A park that is always green has an anomaly near zero. |
| **"Why not machine learning?"** | No labelled leak dataset exists at this scale, and a model we cannot explain is one a municipal engineer will not dig on. The rule is three weights — satellite 0.40, billing 0.35, citizen 0.25, in `fusion.py` — auditable and tunable. |
| **"Can you change the weights right now?"** | Yes: edit `WEIGHTS` in `backend/app/services/fusion.py`, then `POST /api/fusion/run`. About 15 seconds. **Rehearse it or do not offer it.** Never improvise this on stage. |
| **"What if a city has no billing data?"** | Weights renormalise over whatever signals exist, so a missing signal is *absent*, not zero — a zone is never punished to 40% of its score for data nobody collected. The score is then discounted for coverage (0.70 on one signal, 0.90 on two) so a lone reading cannot outrank corroboration. Show `Z-023` at rank #4: `1/3 signals · low confidence`. |
| **"What does 'confidence' mean?"** | Three signals present and within 25 points of each other = high. Two or more = medium. One = low. It describes agreement between sources, not probability of a leak. `Z-028` is high confidence *and* rank 27. |
| **"Why is your #1 only two signals?"** | Because the third does not exist for that zone — it was under cloud on the observation date. We show two real signals rather than inventing a third. It still outranks the one-signal leads below it, which is exactly what the coverage discount is for. |
| **"Only 30 zones?"** | The grid is a demonstration boundary set, not a claim about Jaipur's real ward geometry. The pipeline takes any polygon set — swap the GeoJSON and re-run. |

---

## Verify before you present

Run this and check the output against what you are about to say.

```bash
docker compose up -d db
cd backend
python -m app.init_db
uvicorn app.main:app --reload &                    # loaders POST to the API — start it FIRST
python seed.py --skip satellite                    # keep real NDVI, drop the placeholder rows
python -m pipelines.satellite.load ../data/samples/ndvi_export.csv
python -m pipelines.billing.load  ../data/samples/billing.csv
curl -s -X POST localhost:8000/api/fusion/run
curl -s "localhost:8000/api/scores?limit=6" | python -m json.tool
```

> The loaders use relative imports — they must be run with `python -m`, not
> `python pipelines/satellite/load.py`. The latter fails with `ImportError`.

> **Check port 8000 is free before you start.** If anything else on the demo laptop
> already owns it (Docker desktop tooling, a local proxy), both `uvicorn` and
> `docker compose up` fail to bind and the API never comes up. Stop the other process,
> or run the API elsewhere and set `API_PROXY_TARGET` for the frontend.

Confirm before you walk on:

- [ ] `Z-005` (Ward 1 - Sector 5) is rank #3 with `3/3 signals`, and its satellite row's `source` is `sentinel2-gee`
- [ ] `Z-025` (Ward 5 - Sector 1) still shows satellite 0 and the highest NRW in the city
- [ ] `Z-028` (Ward 5 - Sector 4) still reads `high` confidence at a low rank
- [ ] `Z-023` (Ward 4 - Sector 5) still reads `1/3 signals · low confidence` **below** the corroborated zones
- [ ] The explanation sentence on your demo zone matches what you plan to read aloud
- [ ] The deployed URL tells the same story as your local instance

---

## Offline fallback — the venue wifi will fail

- [ ] Screen-recorded 4-minute run-through, on a phone **and** a laptop
- [x] Local stack runs with no internet: `docker compose up` plus the block above
      — verified 29 Aug with the wifi radio off: cold `down` + `up` in 6s, API healthy,
      30 zones scored, and a citizen report POSTed against the local API
- [ ] Google Fonts is the remaining live dependency — `index.html` pulls Outfit from
      fonts.googleapis.com. With no network the page falls back to the system sans stack, so
      it stays readable but does not look like the screenshots. Confirmed 29 Aug with wifi
      off: layout holds, nothing overflows, but the type is visibly not Outfit. Check you
      are happy with that
- [x] ~~**Map tiles are the weak point.**~~ **Handled in code.** The map counts failed tile
      requests and swaps to a bundled georeferenced basemap of the demo area, with a badge
      saying so. No warm-cache ritual to remember. Verified by aborting every OSM tile
      request: polygons, pins, fly-to and the detail panel all keep working.
      Re-confirmed 29 Aug with wifi genuinely off: badge shown, bundled basemap rendered,
      all 30 zone polygons drawn, 0 live tiles loaded.
- [ ] Slides exported to PDF and stored locally, not on Google Slides
- [ ] The Telegram bot needs internet. If wifi is down, demo `/report` against the local
      backend — rehearse that path too
- [ ] **Hit the API once before the judges reach you.** `neerdrishti-api` is a free Render
      web service and those spin down after ~15 minutes idle. Measured 28 Aug: after 19
      minutes of no traffic the first request still came back in **0.77s**, so it had not
      slept — but nothing in this repo explains why, and `render.yaml` claims a keep-alive
      that does not exist (see below). Treat the fast number as luck, not a guarantee, and
      warm it yourself. The frontend is a static site and is never affected.

---

## Rehearsal log

| Date | Run | Time | What broke |
|---|---|---|---|
| 29 Aug | Offline stack test — wifi radio off, cold `docker compose up`, API + dashboard + report POST | 06:49 UTC | Nothing at run time. Two problems found in prep: the API image had never been built, so `docker compose up` offline would have hit PyPI and failed — built and cached it. Port 8000 was already taken on the demo laptop, so the API could not bind. |
