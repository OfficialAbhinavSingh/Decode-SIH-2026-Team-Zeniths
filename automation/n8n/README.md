# Automation — R5 (n8n + WhatsApp)

Two jobs: get citizen leak reports into the DB, and (Phase 2) keep things running on a schedule.

## MVP — the only one that must work

```
WhatsApp/Telegram message
        ↓  webhook trigger
   parse text + location
        ↓
   dedupe (same person + same area within 6h → drop)
        ↓
   POST /api/reports   { channel, reporter_hash, description, lat, lon }
        ↓
   reply to the citizen: "Logged. Zone Z-014. Thanks."
```

### Nodes

| # | Node | Notes |
|---|---|---|
| 1 | **Webhook** | WhatsApp Cloud API webhook, or Telegram Trigger as the no-approval fallback |
| 2 | **Function — hash the sender** | `sha256(phone + SALT)`. **Never send a raw phone number to the API.** |
| 3 | **Function — extract location** | WhatsApp location message → lat/lon. Text-only → try geocoding the ward name; if that fails send `zone_id: null` and let a human triage it. |
| 4 | **Function — dedupe** | Drop if the same `reporter_hash` reported within ~200 m in the last 6 hours. Five neighbours reporting one leak should be one strong signal, not five leaks. |
| 5 | **HTTP Request** | `POST {API_URL}/api/reports`, body per `docs/DATA-CONTRACT.md` |
| 6 | **Respond** | Reply with the matched `zone_id` from the API response |

### Export the workflow

**File → Export → Download**, save as `automation/n8n/leak-intake.workflow.json`, commit it.
The sponsor award ("Best Use of n8n") needs the workflow visible in the repo — a screenshot
is not enough.

## Fallback that must exist regardless

`frontend/src/pages/Report.jsx` is a plain web form hitting the same endpoint.

**Build the WhatsApp path, but never let the demo depend on it.** Meta's WhatsApp Business
API approval is slow and outside our control. Telegram's Bot API needs no approval and looks
identical on stage — it is a legitimate MVP substitute, and worth setting up first.

## Phase 2 — only after every MVP item in docs/SCOPE.md is green

| Workflow | What it does |
|---|---|
| **Satellite refresh** | Cron (weekly) → trigger the GEE export → `POST /api/ingest/satellite` |
| **Fusion cron** | Cron (30 min) → `POST /api/fusion/run` (the Render worker already does this; n8n version is the visible-in-demo one) |
| **Alert dispatch** | On a zone crossing score 85 → WhatsApp the ward engineer with the zone + the explanation |
| **Lyzr triage agent** | Zone scores → plain-language repair brief → attach to the alert |

## Env vars the workflow needs

```
API_URL         https://neerdrishti-api.onrender.com
INGEST_TOKEN    (only for the ingest workflows, not for /api/reports)
PHONE_SALT      any random string; keep it out of the exported JSON
```
