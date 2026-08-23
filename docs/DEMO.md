# Demo — R6 owns, everyone rehearses

Fill this in properly by **3 Sep**. The structure below is the target; the content is yours.

## The 4-minute script

| Time | Who | Screen | Line |
|---|---|---|---|
| 0:00–0:30 | Pitch | Slide 1 | India loses a huge share of treated water before it reaches a tap. Finding the leak normally means burying sensors — which most cities cannot afford. |
| 0:30–1:00 | Pitch | Slide 2 | We use three things a city already has for free: satellite imagery, its own billing records, and its residents. |
| 1:00–2:00 | Demo | Dashboard | Here's the city. Red = inspect first. This ranking came from fusing three signals. |
| 2:00–3:00 | Demo | Zone detail | Click the top zone: NDVI is 0.2 above its own 3-year baseline, 46% of water in this zone is unbilled, and 5 residents reported it. **All three agree.** That's a crew dispatch. |
| 3:00–3:30 | Demo | WhatsApp/form | A resident reports a leak, it lands in the zone, the score moves. |
| 3:30–4:00 | Close | Slide 3 | Zero new hardware. Free data. What we'd build next: rain adjustment, live refresh, water quality. |

## Rehearse the hard questions

| Question | Answer |
|---|---|
| "Is the billing data real?" | No — it's synthetic, generated from published CPHEEO/AMRUT NRW benchmarks, and every row is flagged `is_synthetic`. The generator is in the repo. Point at it. |
| "What if it rained?" | Scores are computed relative to the city median that same day, so a city-wide green-up cancels out. Explicit rainfall adjustment is our next build. |
| "How do you know it's a leak and not a park?" | The baseline is the same calendar window in prior years. A park that's always green has near-zero anomaly. |
| "Why not ML?" | No labelled leak dataset exists at this scale. A weighted rule is explainable and tunable live — watch. (Then tune a weight on stage.) |
| "What if a city has no billing data?" | The weights renormalise over whatever signals exist. Show a zone with `1/3 signals` and `low confidence`. |

## Offline fallback — set this up, the venue wifi will fail

- [ ] Screen-recorded 4-minute run-through on a phone and a laptop
- [ ] Local stack runnable with no internet: `docker compose up` + `python seed.py`
- [ ] Map tiles cached, or a static screenshot fallback if OSM tiles won't load
- [ ] Slides exported to PDF locally, not on Google Slides

## Rehearsal log

| Date | Run | Time | What broke |
|---|---|---|---|
| | | | |
