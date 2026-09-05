"""Regression test for the 2026-09-05 production incident: create_all() does not alter a
table that already exists, so a model gaining a column left a live table one column
short and every endpoint touching it 500'd. add_missing_columns() closes that gap.

Uses its own throwaway MetaData/Table objects rather than the app's real models -- this
must keep testing the mechanism after the real schema has moved on from this incident.
"""

from sqlalchemy import Boolean, Column, Float, Integer, MetaData, String, Table, create_engine, inspect, text as sql_text

from app.init_db import add_missing_columns


def _engine(tmp_path):
    return create_engine(f"sqlite:///{tmp_path}/migration.db")


def test_adds_a_missing_nullable_column(tmp_path):
    engine = _engine(tmp_path)
    old = MetaData()
    Table("widgets", old, Column("id", Integer, primary_key=True), Column("name", String(40)))
    old.create_all(engine)

    new = MetaData()
    Table(
        "widgets", new,
        Column("id", Integer, primary_key=True),
        Column("name", String(40)),
        Column("area_km2", Float, nullable=True),  # the new column, like Zone.area_km2
    )

    added = add_missing_columns(engine, metadata=new)

    assert added == ["widgets.area_km2"]
    live_columns = {c["name"] for c in inspect(engine).get_columns("widgets")}
    assert "area_km2" in live_columns


def test_is_idempotent(tmp_path):
    """Render runs this on every deploy. The second and every later run must be a no-op,
    not an error, not a duplicate ALTER."""
    engine = _engine(tmp_path)
    old = MetaData()
    Table("widgets", old, Column("id", Integer, primary_key=True))
    old.create_all(engine)

    new = MetaData()
    Table("widgets", new, Column("id", Integer, primary_key=True), Column("flag", Boolean, nullable=True))

    first = add_missing_columns(engine, metadata=new)
    second = add_missing_columns(engine, metadata=new)

    assert first == ["widgets.flag"]
    assert second == []


def test_brand_new_table_is_left_to_create_all(tmp_path):
    """A table that does not exist yet at all is create_all()'s job, not this function's --
    this must not try to ALTER a table it never created."""
    engine = _engine(tmp_path)
    MetaData().create_all(engine)  # nothing exists yet

    new = MetaData()
    Table("cities", new, Column("code", String(8), primary_key=True))

    added = add_missing_columns(engine, metadata=new)

    assert added == []
    assert not inspect(engine).has_table("cities")


def test_refuses_a_not_null_column_with_no_default(tmp_path):
    """This is the case the module's docstring says to 'drop and re-seed' instead of
    silently guessing a backfill value for rows that already exist."""
    engine = _engine(tmp_path)
    old = MetaData()
    Table("widgets", old, Column("id", Integer, primary_key=True))
    old.create_all(engine)
    with engine.begin() as conn:
        conn.execute(sql_text("INSERT INTO widgets (id) VALUES (1)"))

    new = MetaData()
    Table(
        "widgets", new,
        Column("id", Integer, primary_key=True),
        Column("required_field", String(40), nullable=False),
    )

    try:
        add_missing_columns(engine, metadata=new)
        assert False, "expected a RuntimeError"
    except RuntimeError as exc:
        assert "widgets.required_field" in str(exc)

    # and it must not have partially applied the ALTER before raising
    assert "required_field" not in {c["name"] for c in inspect(engine).get_columns("widgets")}


def test_not_null_column_with_a_server_default_backfills_existing_rows(tmp_path):
    """The real bug this incident hit: ZoneScore.rain_flagged was NOT NULL with only a
    Python-side `default=False`, not a `server_default` -- there was no value Postgres
    could put in the existing rows, so this correctly refused (see the test above). Once
    it has a real server_default, adding it must succeed AND backfill old rows, not just
    add the column as silently nullable and diverge from the model.
    """
    engine = _engine(tmp_path)
    old = MetaData()
    Table("widgets", old, Column("id", Integer, primary_key=True))
    old.create_all(engine)
    with engine.begin() as conn:
        conn.execute(sql_text("INSERT INTO widgets (id) VALUES (1)"))

    new = MetaData()
    Table(
        "widgets", new,
        Column("id", Integer, primary_key=True),
        Column("flag", Boolean, nullable=False, server_default=sql_text("0")),
    )

    added = add_missing_columns(engine, metadata=new)
    assert added == ["widgets.flag"]

    with engine.begin() as conn:
        row = conn.execute(sql_text("SELECT flag FROM widgets WHERE id=1")).fetchone()
    assert row[0] == 0, "the pre-existing row must be backfilled, not left NULL"
