# Synthetic national data

Owner: R1 (Satellite & Geo). Status: shipped.

How the dashboard shows every Indian city without waiting on data that does not exist yet,
and — more importantly — how to say out loud what that data is.

---

## The short version

`docs/PAN-INDIA.md` is the honest account of scaling on **real** data, and its conclusion
has not changed: zone geometry and the satellite signal are solvable for any city, and
**per-zone billing / NRW data is not publicly available for any Indian city**. That is a
data-availability wall, not an engineering one, and no amount of work here goes through it.

So the country is generated instead. `pipelines/synthetic/` produces the Jaipur grid format
for 234 cities across all 28 states and 8 union territories — the same square cells, the
same `Ward N - Sector M` naming, the same three signals, the same fusion scores and
confidence levels. Everything the single-city dashboard already knows how to draw.

**Every number it produces is fabricated.** Say that first, not when asked.

---

## What is real and what is not

| | Real | Synthetic |
|---|---|---|
| City names, states, coordinates | ✅ | |
| Zone boundaries | | ❌ a square grid centred on the city, not administrative wards |
| Zone population, pipe length | | ❌ drawn from a plausible range |
| NDVI / satellite signal | | ❌ generated; real Sentinel-2 covers every city and can replace it |
| NRW / billing signal | | ❌ generated; **not obtainable for real, for any Indian city** |
| Citizen reports | | ❌ generated; the intake channel itself is real and works anywhere |
| Fusion rule, scores, ranking, confidence | ✅ the engine is the real one | it is running over synthetic inputs |

The last row is the one worth being precise about. The fusion engine, the coverage
discount, the percentile ranking and the confidence rule are all the production code paths,
unmodified — what is synthetic is what goes *into* them. A judge asking "does this work?"
is asking about the engine; a judge asking "is this data?" is asking about the inputs. Give
them different answers.

Two things in the schema already carry the label, so it survives even if this file is not
read: `billing_signals.is_synthetic` is `True` on every generated row, and every generated
satellite row is written with `source = "seed"`, which fusion ranks *below* a real
`sentinel2-gee` row. A genuine ingest for a city overwrites the fake one with no code change.

---

## Running it

```bash
cd backend
python -m pipelines.synthetic.seed_india --dry-run     # what would be written
python -m pipelines.synthetic.seed_india               # all 234 cities, ~6,100 zones
python -m pipelines.synthetic.seed_india --cities Jaipur,Pune
python -m pipelines.synthetic.seed_india --states Kerala,Sikkim
python -m pipelines.synthetic.seed_india --limit 20    # the 20 largest
```

It **wipes and rebuilds** by default, exactly like `seed.py`. It writes only to the five
tables already in `DATA-CONTRACT.md` and adds no column to any of them.

That constraint is deliberate and worth keeping. `app/init_db.py` runs `create_all()`,
which creates missing *tables* and never alters existing ones — so a new column on `zones`
appears locally, never appears in the deployed Postgres, and every endpoint that selects a
Zone starts returning 500. That is not hypothetical; it is what happened, and it is why
this generator lives entirely inside the frozen schema.

`seed.py` is untouched and still the offline demo fallback. CI still runs it.

---

## Why the seed matters

Each city draws from its own `random.Random`, seeded from **SHA-256 of the city name**.

* **Reproducible.** Jaipur produces the same 30 zones and the same numbers on every machine
  and every run. A screenshot taken today still matches the map next week, and two people
  on the team see the same top-ranked zone.
* **Independent.** Adding a city to the registry, or reordering it, cannot move a single
  number in any other city. `seed.py` shares one `Random(2026)` across everything it does
  and documents the trap that creates; per-city streams remove it.

`hash()` cannot be used for this. Python salts string hashing per process, so a
`hash()`-derived seed gives a *different* city on every run — reproducible within one
process and worthless across two. `tests/test_synthetic_grid.py` pins the expected seed
value precisely so that swap cannot creep back in.

---

## Jaipur is pinned

Jaipur keeps the zone-id prefix `Z` and its 30-zone, 6-column grid, so the generator
reproduces `Z-001..Z-030` at their existing coordinates, byte for byte.

This is not sentiment. Jaipur is the city the live dashboard has always shown and the one
the demo is built around; regenerating it under a different prefix or zone count would
quietly replace the one view everything else is judged against.
`test_jaipur_reproduces_the_original_seed_grid_exactly` checks the generated grid against
`seed.py`'s original `build_zones()` field by field, so this cannot drift unnoticed.

---

## Zone ids

`zones.id` is one global primary key, not one per city. Every city therefore carries a
unique prefix from the registry (`BOM-001`, `GTK-014`, `IXZ-007`), and Jaipur keeps the
bare `Z-001`.

This matters more than it looks. A bare `Z-{n:03d}` scheme in a second city collides on
every overlapping id, and the loader's upsert-on-conflict *silently overwrites* the first
city's rows — name, geometry, everything, with no error. That was a real bug (fixed in
`656781c`). `test_zone_ids_are_unique_across_the_whole_registry` generates all 234 cities
and asserts no id is produced twice.

---

## What the frontend does with it

`GET /api/cities` lists every city that actually has zones — derived from the `zones` table,
so it is correct for a database holding one city and for one holding all 234, with no code
change between them.

The dashboard's city picker renders **only when more than one city is loaded**. On a
database with just the seeded Jaipur grid, the dashboard is exactly what it has always
been: no picker, no `?city=` on the first request, same default, same map.

---

## Replacing it with real data

Nothing here has to be undone. Point R1's and R2's pipelines at a city and POST to the
ingest endpoints; the natural-key upserts overwrite the synthetic rows in place, and the
satellite ordering already prefers real data. Delete a city's rows and re-run fusion to
drop it entirely.

The real blocker remains the one `PAN-INDIA.md` names: for the billing signal there is
nothing to ingest, because per-zone NRW is not published. Until a utility hands over a
file, that column stays synthetic — and stays labelled.
