import json

from pipelines.satellite.load_zones import centroid, dedupe_by_id, read_zones

import pytest

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
}

# A ward cut in two by a river: two disjoint parts, one geometry.
SPLIT_WARD = {
    "type": "MultiPolygon",
    "coordinates": [
        [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
        [[[20, 0], [30, 0], [30, 10], [20, 10], [20, 0]]],
    ],
}


def test_polygon_centroid():
    assert centroid(SQUARE) == (5.0, 5.0)


def test_closing_vertex_is_not_double_counted():
    # Same square without the repeated closing vertex must land on the same point.
    open_ring = {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10]]]}
    assert centroid(open_ring) == centroid(SQUARE)


def test_multipolygon_centroid():
    # Regression: the exterior ring of *every* part counts. This used to divide by zero.
    assert centroid(SPLIT_WARD) == (5.0, 15.0)


def test_unsupported_geometry_raises():
    with pytest.raises(ValueError, match="unsupported geometry type"):
        centroid({"type": "Point", "coordinates": [1, 2]})


def test_empty_geometry_raises():
    with pytest.raises(ValueError, match="no coordinates"):
        centroid({"type": "Polygon", "coordinates": [[]]})


# --- feature parsing ------------------------------------------------------------------


def _write(tmp_path, features):
    path = tmp_path / "wards.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return str(path)


def _feature(props, geometry=SQUARE):
    return {"type": "Feature", "properties": props, "geometry": geometry}


def test_missing_property_names_the_key_and_what_the_file_has(tmp_path):
    # A downloaded JMC ward file, which uses its own property names.
    path = _write(tmp_path, [_feature({"WARD_NO": "1", "WARD_NAME": "Adarsh Nagar"})])
    with pytest.raises(ValueError) as exc:
        read_zones(path)
    assert "zone_id" in str(exc.value)
    assert "WARD_NAME" in str(exc.value)


def test_read_zones_maps_properties_and_centroid(tmp_path):
    path = _write(tmp_path, [_feature({"zone_id": "Z-001", "name": "Sector 1", "city": "Jaipur"})])
    (zone,) = read_zones(path)
    assert (zone["id"], zone["city"], zone["ward"]) == ("Z-001", "Jaipur", None)
    assert (zone["centroid_lat"], zone["centroid_lon"]) == (5.0, 5.0)


def test_dedupe_by_id_keeps_the_last_feature():
    # Postgres raises CardinalityViolation on a batch that repeats a conflict key, so a
    # hand-edited ward file that repeats an id must collapse, not crash.
    zones = dedupe_by_id([{"id": "Z-001", "name": "old"}, {"id": "Z-001", "name": "new"}])
    assert zones == [{"id": "Z-001", "name": "new"}]


def test_dedupe_by_id_keeps_distinct_ids():
    assert len(dedupe_by_id([{"id": "Z-001"}, {"id": "Z-002"}])) == 2
