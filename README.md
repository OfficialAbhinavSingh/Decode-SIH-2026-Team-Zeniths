# NeerDrishti AI — Team Zeniths

**Decode SIH 2026 · Bharat Nirman · PS3 — Smart Water Intelligence System**

Find underground water leaks in Indian cities **without installing any new hardware**, by
fusing three signals a municipality can already get for free:

| Signal | Where it comes from | What it tells us |
|---|---|---|
| 🛰️ Satellite | Sentinel-2 NDVI / soil wetness over pipeline corridors | Soil above a leaking pipe stays wetter & greener |
| 💧 Billing (NRW) | Water supplied vs water billed, per zone | A big gap = water is being lost somewhere in that zone |
| 📱 Citizen | WhatsApp / web reports from residents | Ground truth: someone actually saw water |

Each signal is scored `0–100` per zone. A fusion engine combines them into one
**priority score** and a ranked repair list, shown on a map dashboard.

> **Output of the product:** *"Zone 14, Ward 7 — priority 87/100, all three signals agree. Send a crew here first."*

---

## Repo map

```
docs/            ← read these first (5 docs, that's it)
backend/         ← FastAPI API + fusion engine
backend/pipelines/  ← satellite & billing signal producers
frontend/        ← React + Leaflet map dashboard
automation/n8n/  ← WhatsApp intake + scheduled jobs
data/samples/    ← sample CSVs so nobody is blocked on real data
```

## Start here

1. **[docs/SCOPE.md](docs/SCOPE.md)** — what we ship by 5 Sep and what we deliberately do NOT build.
2. **[docs/ROLES.md](docs/ROLES.md)** — who owns which folder. Find your name, read only your section.
3. **[docs/SETUP.md](docs/SETUP.md)** — get it running locally in ~10 minutes.
4. **[docs/DATA-CONTRACT.md](docs/DATA-CONTRACT.md)** — the frozen DB tables + API shapes. **This is the only thing all 6 of us must agree on.**
5. **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — how the pieces fit together.

## Working agreement

- Branch per person: `feat/<role>-<thing>` → PR into `main`. No direct pushes to `main`.
- Do **not** change files outside your folder without telling the owner.
- `docs/DATA-CONTRACT.md` changes require a heads-up to the whole team — everything else depends on it.
- Seed data (`backend/seed.py`) exists so you can build your part before anyone else's part is done.
