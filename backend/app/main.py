from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .db import engine
from .routers import fusion, ingest, reports, scores, zones

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

app.include_router(zones.router)
app.include_router(scores.router)
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
