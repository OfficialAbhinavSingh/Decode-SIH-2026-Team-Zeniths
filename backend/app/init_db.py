"""Create every table. Run once after starting Postgres: `python -m app.init_db`.

No migration tool on purpose -- the schema is frozen in docs/DATA-CONTRACT.md and a
two-week build does not need Alembic. If the schema changes, drop and re-seed.
"""

from .db import Base, engine
from . import models  # noqa: F401  -- import registers the tables on Base.metadata


def main() -> None:
    Base.metadata.create_all(engine)
    print("tables created:", ", ".join(sorted(Base.metadata.tables)))


if __name__ == "__main__":
    main()
