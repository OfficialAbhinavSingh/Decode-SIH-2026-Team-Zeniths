from pipelines.satellite.load_zones import centroid

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
