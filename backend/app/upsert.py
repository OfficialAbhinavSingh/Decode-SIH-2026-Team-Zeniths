"""One dialect-aware upsert, so the same pipelines run on Postgres and on SQLite.

Owner: R3 (Backend & Fusion).

WHY: every loader in this repo imported `sqlalchemy.dialects.postgresql.insert` directly,
which is correct in production and unrunnable anywhere else. Two things need the other
path:

  - The offline demo fallback (SCOPE.md M8, "survives no-internet"). A judge's table with
    no Docker, no Postgres and no network still has to show a working map. Point
    DATABASE_URL at `sqlite:///neerdrishti.db` and the whole national pipeline -- registry,
    zones, groundwater, rainfall, fusion -- runs unchanged.
  - Tests. Standing up Postgres in CI to prove an upsert is idempotent is a lot of
    machinery for a property SQLite can demonstrate in milliseconds.

Both dialects implement `ON CONFLICT DO UPDATE` with the same SQLAlchemy surface, so this
is a dispatch, not an abstraction layer. Any other dialect raises rather than silently
falling back to plain INSERT, which would turn a re-run from "idempotent" into "duplicate
key" at the worst possible moment.
"""

from sqlalchemy import Table, UniqueConstraint
from sqlalchemy.orm import Session

# Bound-parameter ceiling per statement, by dialect. Postgres's hard limit is 65535;
# SQLite's is 32766 on current builds but only 999 on ones compiled before 3.32, and the
# team is on mixed machines, so we stay under the old limit rather than discovering which
# SQLite a judge's laptop has during a demo.
MAX_PARAMS = {"postgresql": 30_000, "sqlite": 900}
MAX_PARAMS_DEFAULT = 900


def _insert_for(db: Session):
    name = db.get_bind().dialect.name
    if name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert

        return insert
    if name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert

        return insert
    raise RuntimeError(
        f"upsert is not implemented for the {name!r} dialect -- add it here rather than "
        "letting a loader fall back to a plain INSERT and break idempotency"
    )


def _constraint_columns(table: Table, name: str) -> list[str]:
    """Column names behind a named unique constraint.

    SQLite's ON CONFLICT clause names columns, not constraints -- only Postgres accepts a
    constraint name. Resolving the name against the model's own metadata keeps the caller
    writing the constraint name (which the database validates on Postgres, so a typo is
    caught rather than silently matching the wrong index) while still working on SQLite.
    """
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint) and constraint.name == name:
            return [column.name for column in constraint.columns]
    raise ValueError(
        f"{table.name} has no unique constraint named {name!r} -- check the "
        "__table_args__ on the model, or pass index_elements instead"
    )


def upsert(
    db: Session,
    model,
    rows: list[dict],
    *,
    index_elements: list[str] | None = None,
    constraint: str | None = None,
    update: bool = True,
) -> int:
    """Insert `rows`, updating on conflict. Returns the number of rows sent.

    Exactly one of `index_elements` (column names) or `constraint` (a named unique
    constraint) identifies the conflict target. Named constraints are preferred for
    composite keys because the name is checked by the database, whereas a column list can
    silently match a different index.

    `update=False` makes it DO NOTHING -- for append-only tables where the first write
    wins.
    """
    if not rows:
        return 0
    if bool(index_elements) == bool(constraint):
        raise ValueError("pass exactly one of index_elements or constraint")

    insert = _insert_for(db)
    table: Table = getattr(model, "__table__", model)
    dialect = db.get_bind().dialect.name

    if constraint and dialect != "postgresql":
        index_elements = _constraint_columns(table, constraint)
        constraint = None

    key_columns = set(index_elements or [])
    if constraint:
        key_columns = set(_constraint_columns(table, constraint))

    # Count the table's columns, not the dict's keys: SQLAlchemy fills server- and
    # client-side defaults (`id`, `created_at`) into the same statement, and sizing the
    # chunk on the caller's keys alone overshoots the parameter limit by exactly those.
    params_per_row = max(len(table.columns), len(rows[0]), 1)
    budget = MAX_PARAMS.get(dialect, MAX_PARAMS_DEFAULT)
    chunk_size = max(1, budget // params_per_row)

    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        stmt = insert(table).values(chunk)
        if update:
            setters = {
                column: getattr(stmt.excluded, column)
                for column in chunk[0]
                if column not in key_columns
            }
            if constraint:
                stmt = stmt.on_conflict_do_update(constraint=constraint, set_=setters)
            else:
                stmt = stmt.on_conflict_do_update(index_elements=index_elements, set_=setters)
        else:
            stmt = (
                stmt.on_conflict_do_nothing(constraint=constraint)
                if constraint
                else stmt.on_conflict_do_nothing(index_elements=index_elements)
            )
        db.execute(stmt)
    return len(rows)


def dedupe(rows: list[dict], key_columns: list[str]) -> list[dict]:
    """Collapse rows sharing a conflict key, last one wins.

    Both dialects refuse a single statement that hits the same conflict key twice
    ("ON CONFLICT DO UPDATE command cannot affect row a second time"), which a
    concatenated or re-exported CSV does routinely. Collapsing here turns a 500 into the
    same answer a second load would have given.
    """
    collapsed: dict[tuple, dict] = {}
    for row in rows:
        collapsed[tuple(row[column] for column in key_columns)] = row
    return list(collapsed.values())
