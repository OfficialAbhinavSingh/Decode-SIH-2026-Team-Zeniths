# Role 3: Automation Engineer (n8n, WhatsApp, Sarvam AI & Alerts)

NeerDrishti AI automation subsystem: citizen intake, Sarvam AI Indic language translation, satellite refresh scheduling, and field repair alert dispatch.

---

## 🌐 Live Cloud Instance
- **n8n Cloud Workspace**: `https://laterabhi.app.n8n.cloud`
- **Workflow Link**: [NeerDrishti Intake Workflow](https://laterabhi.app.n8n.cloud/workflow/tjvnHuhgr7lOqzFH?projectId=4K2NjOBEA1OSpzQ2)
- **Production Webhook URL**: `https://laterabhi.app.n8n.cloud/webhook/whatsapp-leak-intake`
- **Test Webhook URL**: `https://laterabhi.app.n8n.cloud/webhook-test/whatsapp-leak-intake`
- **Telegram Bot**: `@zeniths_neerdrishti_bot`

---

## 📁 Subsystem Structure

```
automation/n8n/
├── leak-intake.workflow.json        ← Official n8n WhatsApp/Telegram intake workflow (with Sarvam AI)
├── satellite-trigger.workflow.json  ← 12-day NISAR / Sentinel-2 satellite cadence trigger
├── alert-dispatch.workflow.json     ← Crew alert dispatch workflow (Telegram/Email)
├── simulate_whatsapp.py             ← Interactive CLI tool to simulate citizen reports
├── services/
│   ├── sarvam.py                    ← Sarvam AI Indic NLP service (Hindi, Tamil, Kannada, etc.)
│   └── alerts.py                    ← Field crew alert card formatter & dispatcher
├── utils/
│   ├── hasher.py                    ← Salted SHA-256 phone anonymizer (citizen privacy)
│   └── dedupe.py                    ← Spatial-temporal deduplicator (200m / 6hr clustering)
└── tests/
    └── test_automation.py           ← Unit & integration test suite (12 tests passing)
```

---

## 🔄 1. Citizen Leak Intake Flow (`leak-intake.workflow.json`)

```
Citizen sends WhatsApp/Telegram message (any Indian language)
        ↓
1. Webhook Trigger Node (`/webhook/whatsapp-leak-intake`)
        ↓
2. Privacy Hasher Node: sha256(phone + SALT)
        ↓ (Raw phone numbers NEVER enter DB or logs)
3. Sarvam AI Translation Node: Detects Indic script → Calls https://api.sarvam.ai/translate (Mayura:v1)
        ↓
4. Ingestion Node: POST /api/reports
        ↓
5. Confirmation Reply Node: Auto-generates localized receipt with Zone ID & Ref #
```

### Privacy & Salt Hashing
- Formula: `reporter_hash = sha256(normalize_phone(phone) + ":" + SALT)[:32]`
- Complies strictly with municipal privacy guidelines and `docs/DATA-CONTRACT.md`.

### Sarvam AI Mayura Translation
- Direct integration with **Sarvam AI Mayura Translation API** (`model: mayura:v1`).
- High-accuracy translation for 10+ Indian languages (Hindi `hi-IN`, Tamil `ta-IN`, Kannada `kn-IN`, Telugu `te-IN`, Marathi `mr-IN`, Bengali `bn-IN`, Gujarati `gu-IN`, Malayalam `ml-IN`, Punjabi `pa-IN`, Odia `od-IN`).
- Built-in heuristic offline fallback for zero-dependency local tests and offline judge demonstrations.

---

## 🛰️ 2. 12-Day Satellite Cadence Trigger (`satellite-trigger.workflow.json`)

- Triggered on a **12-day schedule** matching the exact NISAR L-band SAR repeat orbit cycle and Sentinel-2 composite cadence.
- Triggers `/api/fusion/run?city=Jaipur` to recompute multi-signal fusion scores across all zones.

---

## 🚨 3. Field Crew Alert Dispatcher (`alert-dispatch.workflow.json`)

- Runs every 30 minutes or post-fusion.
- Filters zones where `fusion_score >= 75` and `confidence` is `high` or `medium`.
- Generates rich, actionable dispatch cards:
  ```
  🔴 CRITICAL: WATER LEAK DISPATCH
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  📍 Zone: Z-014 (Ward 7 - Sector 3)
  🏆 City Priority Rank: #1 | Score: 87.4/100
  🎯 Confidence: HIGH (3/3 signals agree)

  📊 Signal Breakdown:
    • 🛰️ Satellite Wetness Anomaly: 91.2/100
    • 💧 Non-Revenue Water Gap: 84.0/100
    • 📱 Citizen Incident Density: 78.5/100

  💡 Diagnostic Summary:
    "NDVI +0.18 anomaly, 41% NRW gap, and 4 citizen reports -- all three signals agree."

  🛠️ Action Recommended: Deploy acoustic/ground team to pipeline corridor in Z-014.
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ```
- Dispatches immediately to Telegram & Webhook for ward repair leads.

---

## 🧪 Testing & Simulation Commands

### 1. Run the Unit Test Suite
```powershell
python tests/test_automation.py
```

### 2. Test Against Live Cloud Webhook
```powershell
python simulate_whatsapp.py --api-url "https://laterabhi.app.n8n.cloud/webhook/whatsapp-leak-intake" --text "स्कूल के पास सड़क पर पानी बह रहा है"
```

### 3. Run Deduplication & Spatial Clustering Test
```powershell
python simulate_whatsapp.py --test-dedupe
```

### 4. Send Multilingual Citizen Reports Batch
```powershell
python simulate_whatsapp.py --batch
```
