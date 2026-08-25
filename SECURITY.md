# Security & privacy

This project handles citizen-submitted reports containing phone numbers and locations. Two weeks of
hackathon pressure is exactly when people get careless with those. Don't.

## Reporting a problem

Found a leaked credential, an exposed endpoint, or a privacy hole — in our repo or our deployment?

**Do not open a public issue.** Message @OfficialAbhinavSingh directly in the team group.

## Rules we hold ourselves to

### Secrets
- Nothing secret in the repo. Ever. Not in code, config, commit messages, or comments.
- `backend/.env` is gitignored. `backend/.env.example` contains **keys only**, no values.
- Everything real lives in Render environment variables or n8n credentials.
- Covered: `DATABASE_URL`, `INGEST_TOKEN`, GEE service-account JSON, WhatsApp/Meta tokens,
  Lyzr / Gemini API keys, n8n webhook URLs.

**If a secret gets committed:** deleting it in a later commit does *not* remove it — it stays in
git history and in every clone. Tell @OfficialAbhinavSingh immediately and **rotate the credential**.
Rotation is the fix. Deletion is not.

### Personal data
- **Raw phone numbers never enter the database.** WhatsApp intake hashes them into `reporter_hash`
  before the `POST /api/reports` call. This is enforced at the n8n layer (R5) and re-checked in the
  API. See `docs/DATA-CONTRACT.md` → `citizen_reports`.
- Citizen report free-text may contain names and addresses. Do not paste real report text into the
  slide deck, the demo video, or a public issue. Use seeded data for anything public.
- Don't export the production DB to your laptop. Use `python backend/seed.py`.

### n8n workflow exports
n8n JSON exports embed credential references and sometimes live webhook URLs. **Open the file and
read it** before committing anything to `automation/n8n/`.

### Ingest endpoints
`POST /api/ingest/satellite` and `POST /api/ingest/billing` write straight to the scores that drive
the map. They require the `INGEST_TOKEN` header so a stranger who finds the public API cannot poison
the demo. Do not remove that check "just for testing" and forget to put it back.

### Dependencies
Adding a new dependency is a PR like anything else. Say in the PR body why it's needed. Prefer the
standard library and what's already in `requirements.txt` / `package.json`.

## Deliberately out of scope for the MVP

We do not implement authentication or user accounts — the dashboard is read-only public data. This
is a documented scope decision (`docs/SCOPE.md`), not an oversight. If a judge asks, say exactly that.
