# Setup — running locally in ~10 minutes

Prereqs: **Docker**, **Python 3.11+**, **Node 20+**.

## 1. Database

```bash
docker compose up -d db
```
Postgres on `localhost:5432`, db `neerdrishti`, user/pass `neer`/`neer`.

## 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.init_db      # create tables
python seed.py             # fill fake zones + all 3 signals + scores
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs  ← use this to poke every endpoint
- Sanity check: `curl localhost:8000/api/scores | head`

`seed.py` is what makes parallel work possible — after running it every endpoint returns
realistic data even though no real pipeline has run yet. Re-run it any time to reset.

## 3. Frontend

```bash
cd frontend
npm install
npm run dev
```
http://localhost:5173 — proxies `/api` to `localhost:8000`, no CORS config needed.

## 4. Everything at once (optional)

```bash
docker compose up
```

---

## Common problems

| Symptom | Fix |
|---|---|
| `connection refused` on 5432 | `docker compose up -d db`, wait ~5s for healthcheck |
| Tables missing | `python -m app.init_db` |
| Empty map | you skipped `python seed.py` |
| Ingest fails: `no unique or exclusion constraint matching the ON CONFLICT specification` | your DB predates the natural-key constraints. No migration tool by design — `docker exec neerdrishti-db psql -U neer -d neerdrishti -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"` then `python -m app.init_db && python seed.py` |
| `npm run dev` proxy 502 | backend isn't running on 8000 |
| Port 5432 already used | you have a local postgres; change the host port in `docker-compose.yml` |

## Git workflow

```bash
git checkout -b feat/r3-fusion-weights
# work
git commit -m "fusion: renormalise weights when a signal is missing"
git push -u origin feat/r3-fusion-weights
gh pr create --fill
```

- One branch per task, PR into `main`, **no direct pushes to `main`**.
- Tag the folder owner as reviewer if your PR touches someone else's lane.

### Signing commits (optional)

Not required, and nothing blocks on it. Skip this section unless you already know you want it.

```bash
ssh-keygen -t ed25519 -C "your-github-email" -f ~/.ssh/id_ed25519_signing
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/id_ed25519_signing.pub
git config --global commit.gpgsign true
gh ssh-key add ~/.ssh/id_ed25519_signing.pub --type signing --title "$(hostname) signing"
```

The last line is the one people get wrong: `--type signing` matters. GitHub stores authentication
keys and signing keys in **two separate lists**, and a key in the wrong list produces no error —
your commits just keep showing "Unverified".
