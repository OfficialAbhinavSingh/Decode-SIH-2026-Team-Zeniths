"""Create every table. Run once after starting Postgres: `python -m app.init_db`.

No migration tool on purpose -- the schema is frozen in docs/DATA-CONTRACT.md and a
two-week build does not need Alembic. If the schema changes in a way that isn't a new
table or a new nullable column, drop and re-seed.

`create_all()` alone is not the whole story, and this is not a hypothetical: on
2026-09-05 PR #24 added three columns to `Zone` and eight to `ZoneScore` -- tables that
already existed in production. `create_all()` only creates tables that are missing
entirely; it never alters one that is already there. Render's start command runs this
script before every deploy, so the deploy "succeeded" and the live tables were left
exactly as they were, one column short of what the ORM model now declares. The result
was every request to `/api/zones`, `/api/scores` and `/api/scores/geojson` -- anything
that touched `Zone` or `ZoneScore` -- failing with `UndefinedColumn`, a bare 500, on the
day of the demo. `add_missing_columns()` closes that gap: after `create_all()` has built
any brand-new tables, it diffs each existing table's real columns against what the model
declares and adds whatever is missing.

This deliberately only ever ADDs a column. It refuses (raises, does not silently skip)
if the missing column is `NOT NULL` with no server default, because there is no value to
backfill into the rows that already exist -- that case is exactly the "drop and re-seed"
situation the paragraph above still describes. Every column PR #24 added was nullable,
which is exactly the "new table or a new nullable column" contract §8 of CONTRIBUTING.md
holds a data-contract change to, so that refusal has not fired in practice.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import MetaData

from .db import Base, engine
from . import models  # noqa: F401  -- import registers the tables on Base.metadata


def add_missing_columns(target_engine: Engine, metadata: MetaData = Base.metadata) -> list[str]:
    """Add any column a model declares that its live table does not yet have.

    Returns the list of "table.column" names it added, so a deploy log shows exactly
    what changed instead of this running invisibly.
    """
    inspector = inspect(target_engine)
    added: list[str] = []
    with target_engine.begin() as conn:
        for table in metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue  # brand-new table -- create_all() already built it in full
            live_columns = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in live_columns:
                    continue
                if not column.nullable and column.server_default is None:
                    raise RuntimeError(
                        f"{table.name}.{column.name} is NOT NULL with no default -- "
                        "cannot ADD COLUMN to a table that may already have rows. "
                        "Make it nullable, give it a server_default, or drop and re-seed."
                    )
                ddl_type = column.type.compile(dialect=target_engine.dialect)
                ddl = f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {ddl_type}'
                if column.server_default is not None:
                    # Compile the model's server_default the same way create_all() would,
                    # so a NOT NULL column with a server_default (e.g. ZoneScore.rain_flagged)
                    # backfills every existing row instead of leaving nothing to satisfy
                    # the NOT NULL constraint the ADD COLUMN itself is about to impose.
                    default_sql = column.server_default.arg.compile(dialect=target_engine.dialect)
                    ddl += f" DEFAULT {default_sql}"
                if not column.nullable:
                    ddl += " NOT NULL"
                conn.execute(text(ddl))
                added.append(f"{table.name}.{column.name}")
    return added


def main() -> None:
    Base.metadata.create_all(engine)
    added = add_missing_columns(engine)
    if added:
        print("added missing columns:", ", ".join(added))
    print("tables created:", ", ".join(sorted(Base.metadata.tables)))


if __name__ == "__main__":
    main()
