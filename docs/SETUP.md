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
| `npm run dev` proxy 502 | backend isn't running on 8000 |
| Port 5432 already used | you have a local postgres; change the host port in `docker-compose.yml` |

## Git workflow

```bash
git checkout -b feat/r3-fusion-weights
# work
git commit -S -m "fusion: renormalise weights when a signal is missing"
git push -u origin feat/r3-fusion-weights
gh pr create --fill
```

- One branch per task, PR into `main`, **no direct pushes to `main`**.
- Commits are GPG-signed (`-S`).
- Tag the folder owner as reviewer if your PR touches someone else's lane.
