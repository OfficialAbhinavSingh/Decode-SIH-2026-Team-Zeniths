# NeerDrishti AI — Team Zeniths

**Decode SIH 2026 · Bharat Nirman · PS3 — Smart Water Intelligence System**

[![CI](https://github.com/OfficialAbhinavSingh/Decode-SIH-2026-Team-Zeniths/actions/workflows/ci.yml/badge.svg)](https://github.com/OfficialAbhinavSingh/Decode-SIH-2026-Team-Zeniths/actions/workflows/ci.yml)
[![PR checks](https://github.com/OfficialAbhinavSingh/Decode-SIH-2026-Team-Zeniths/actions/workflows/pr-checks.yml/badge.svg)](https://github.com/OfficialAbhinavSingh/Decode-SIH-2026-Team-Zeniths/actions/workflows/pr-checks.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

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
CONTRIBUTING.md      ← how work lands here. Compulsory. Read before your first PR.
docs/                ← read these first (5 docs, that's it)
backend/             ← FastAPI API + fusion engine
backend/pipelines/   ← satellite & billing signal producers
frontend/            ← React + Leaflet map dashboard
automation/n8n/      ← WhatsApp intake + scheduled jobs
data/samples/        ← sample CSVs so nobody is blocked on real data
.github/             ← CI, PR template, CODEOWNERS, issue templates
```

## Start here

1. **[docs/SCOPE.md](docs/SCOPE.md)** — what we ship by 5 Sep and what we deliberately do NOT build.
2. **[docs/ROLES.md](docs/ROLES.md)** — who owns which folder. Find your name, read only your section.
3. **[docs/SETUP.md](docs/SETUP.md)** — get it running locally in ~10 minutes.
4. **[docs/DATA-CONTRACT.md](docs/DATA-CONTRACT.md)** — the frozen DB tables + API shapes. **This is the only thing all 6 of us must agree on.**
5. **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — how the pieces fit together.

## Working agreement

**Full rules: [`CONTRIBUTING.md`](CONTRIBUTING.md). Compulsory for everyone, every change.**

- **`main` is protected — no direct pushes.** Everything lands through a reviewed PR.
- Branch `<type>/<lane>-<thing>`, e.g. `feat/r1-ndvi-baseline-composite`.
- **@OfficialAbhinavSingh reviews and merges every PR.** Nobody self-merges.
- Fill in **every** section of the PR template. CI rejects a half-filled one.
- **If an AI agent wrote it, declare it in the PR** ([§7](CONTRIBUTING.md#7-ai-agent-disclosure--compulsory)).
  Undeclared agent work gets closed unmerged.
- Do **not** change files outside your lane without the owner's approval ([CODEOWNERS](.github/CODEOWNERS)).
- `docs/DATA-CONTRACT.md` changes require a heads-up to the whole team first — everything depends on it.
- Never commit a secret ([`SECURITY.md`](SECURITY.md)).
- Seed data (`backend/seed.py`) exists so you can build your part before anyone else's part is done.

| | |
|---|---|
| Contribution rules | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Who owns what | [docs/ROLES.md](docs/ROLES.md) · [.github/CODEOWNERS](.github/CODEOWNERS) |
| Security & privacy | [SECURITY.md](SECURITY.md) |
| Team conduct | [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) |
| License | [MIT](LICENSE) |
