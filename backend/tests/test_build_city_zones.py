"""Geometry tests for the pan-India zone generator.

Every test here is offline. The network paths (Overpass, Nominatim) are deliberately not
exercised -- CI must not depend on a rate-limited public service, and both were returning
429/504 while this was written.
"""

import pytest

from pipelines.satellite.build_city_zones import (
    MAX_ZONES,
    bbox,
    exterior_rings,
    fishnet,
    point_in_rings,
    square,
)

# A 0.06 x 0.06 degree square -- 5 x 5 cells at the default 0.012 cell size. Sized as
# 12 * 0.005 rather than a literal 75.06 so 0.06 / 0.012 lands exactly on 5.0 rather than
# drifting to 5.000000000000189 and having ceil() round up to a phantom 6th column --
# real OSM boundary coordinates never land on that exact a knife-edge, but a test literal
# can, and a flaky assertion here would be worse than no test.
_SIDE = 0.012 * 5
BOX = {
    "type": "Polygon",
    "coordinates": [[
        [75.00, 26.00], [75.00 + _SIDE, 26.00], [75.00 + _SIDE, 26.00 + _SIDE],
        [75.00, 26.00 + _SIDE], [75.00, 26.00],
    ]],
}


def test_fishnet_tiles_a_square_exactly():
    cells, rows, cols = fishnet(BOX, 0.012)
    assert (rows, cols) == (5, 5)
    assert len(cells) == 25


def test_every_cell_centre_is_inside_the_boundary():
    cells, _, _ = fishnet(BOX, 0.012)
    rings = exterior_rings(BOX)
    for _, _, lat, lon, _ in cells:
        assert point_in_rings(lon, lat, rings)


def test_cells_are_the_requested_size():
    cells, _, _ = fishnet(BOX, 0.012)
    ring = cells[0][4]["coordinates"][0]
    width = max(p[0] for p in ring) - min(p[0] for p in ring)
    height = max(p[1] for p in ring) - min(p[1] for p in ring)
    assert width == pytest.approx(0.012)
    assert height == pytest.approx(0.012)


def test_concave_boundary_drops_cells_outside_it():
    """Centre-in-polygon, not bbox. An L-shaped city must not get a rectangular grid.

    This is the whole point of clipping to a real boundary: Jaipur Municipal Corporation
    is nothing like a rectangle, and tiling its bounding box would score farmland outside
    the corporation limit as if it were a monitored ward.
    """
    side = 0.012 * 5
    notch = 0.012 * 2
    l_shape = {
        "type": "Polygon",
        "coordinates": [[
            [75.00, 26.00], [75.00 + side, 26.00], [75.00 + side, 26.00 + notch],
            [75.00 + notch, 26.00 + notch], [75.00 + notch, 26.00 + side],
            [75.00, 26.00 + side], [75.00, 26.00],
        ]],
    }
    cells, rows, cols = fishnet(l_shape, 0.012)
    assert (rows, cols) == (5, 5)          # bounding box is still 5x5
    assert len(cells) == 16                 # the 3x3 corner notch removes 9 cells
    assert len(cells) < rows * cols


def test_multipolygon_is_supported():
    """Real ward and corporation boundaries split around rivers and railway lines."""
    two_islands = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[75.00, 26.00], [75.024, 26.00], [75.024, 26.024], [75.00, 26.024],
              [75.00, 26.00]]],
            [[[75.10, 26.00], [75.124, 26.00], [75.124, 26.024], [75.10, 26.024],
              [75.10, 26.00]]],
        ],
    }
    assert len(exterior_rings(two_islands)) == 2
    cells, _, _ = fishnet(two_islands, 0.012)
    # 2x2 cells per island, and nothing in the ~0.076 degree gap between them.
    assert len(cells) == 8


def test_bbox_spans_every_part_of_a_multipolygon():
    two_islands = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[75.00, 26.00], [75.02, 26.00], [75.02, 26.02], [75.00, 26.02],
              [75.00, 26.00]]],
            [[[75.10, 26.05], [75.12, 26.05], [75.12, 26.07], [75.10, 26.07],
              [75.10, 26.05]]],
        ],
    }
    assert bbox(two_islands) == (75.00, 26.00, 75.12, 26.07)


def test_unsupported_geometry_is_rejected_by_name():
    with pytest.raises(ValueError, match="LineString"):
        exterior_rings({"type": "LineString", "coordinates": [[75, 26], [76, 27]]})


def test_square_is_centred_on_the_point():
    ring = square(75.0, 26.0, 0.006)["coordinates"][0]
    assert ring[0] == ring[-1]                       # closed
    assert min(p[0] for p in ring) == pytest.approx(74.994)
    assert max(p[1] for p in ring) == pytest.approx(26.006)


def test_max_zones_guard_is_smaller_than_a_district():
    """A district boundary at the default cell size runs to tens of thousands of cells.

    The guard exists so that tiling the wrong boundary fails loudly instead of quietly
    handing the loader and the GEE export a workload neither was sized for.
    """
    district = {
        "type": "Polygon",
        "coordinates": [[
            [75.0, 26.0], [76.0, 26.0], [76.0, 27.0], [75.0, 27.0], [75.0, 26.0],
        ]],
    }
    cells, _, _ = fishnet(district, 0.012)
    assert len(cells) > MAX_ZONES


def test_generated_indore_file_matches_the_loader_contract():
    """The committed sample must stay loadable by load_zones.py without edits."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "data" / "samples" / "zones.indore.geojson"
    data = json.loads(path.read_text())
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 70
    ids = set()
    for feature in data["features"]:
        props = feature["properties"]
        for key in ("zone_id", "name", "city"):
            assert key in props, f"load_zones.py requires {key}"
        assert props["city"] == "Indore"
        assert feature["geometry"]["type"] in ("Polygon", "MultiPolygon")
        ids.add(props["zone_id"])
    assert len(ids) == 70, "duplicate zone_id would be collapsed by dedupe_by_id"
