"""Background worker: recompute fusion scores on a loop.

Deployed as the Render Background Worker service (see render.yaml).

    python worker.py
"""

import os
import time

from app.config import settings
from app.db import SessionLocal
from app.services.fusion import run_fusion

INTERVAL_SECONDS = int(os.environ.get("FUSION_INTERVAL_SECONDS", 1800))


def main() -> None:
    print(f"fusion worker started, city={settings.city_default}, every {INTERVAL_SECONDS}s")
    while True:
        db = SessionLocal()
        try:
            count = run_fusion(db, settings.city_default)
            print(f"fusion run complete: {count} zones scored", flush=True)
        except Exception as exc:  # keep the worker alive across a transient DB blip
            print(f"fusion run failed: {exc}", flush=True)
        finally:
            db.close()
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
