from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

from .config import settings
from .db import engine
from .routers import cities, fusion, ingest, national, reports, scores, zones

app = FastAPI(
    title="NeerDrishti AI",
    description="Hardware-free water leak detection: satellite + billing + citizen signals, fused.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /api/national/geojson is ~2.5 MB of JSON: every scored polygon in the country, which is
# the point of it. Uncompressed that is a slow first paint on a phone and a visibly slow
# one on Render's free tier; gzipped it is around a tenth of that. Only responses over
# `minimum_size` are touched, so every existing endpoint is byte-identical as far as any
# client can tell -- and a client that does not send Accept-Encoding: gzip still gets plain
# JSON, because that is the header the middleware keys off.
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(zones.router)
app.include_router(cities.router)
app.include_router(scores.router)
app.include_router(national.router)
app.include_router(reports.router)
app.include_router(ingest.router)
app.include_router(fusion.router)


@app.get("/health", tags=["ops"])
def health() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "db": db_ok}
