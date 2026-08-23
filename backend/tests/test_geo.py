from app.services.geo import point_in_geojson

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
}

SQUARE_WITH_HOLE = {
    "type": "Polygon",
    "coordinates": [
        [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
        [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]],
    ],
}


def test_point_inside():
    assert point_in_geojson(5, 5, SQUARE)


def test_point_outside():
    assert not point_in_geojson(15, 5, SQUARE)


def test_point_in_hole_is_outside():
    assert not point_in_geojson(5, 5, SQUARE_WITH_HOLE)
    assert point_in_geojson(2, 2, SQUARE_WITH_HOLE)


def test_multipolygon():
    multi = {"type": "MultiPolygon", "coordinates": [SQUARE["coordinates"]]}
    assert point_in_geojson(5, 5, multi)
    assert not point_in_geojson(50, 50, multi)


def test_unsupported_geometry_is_false():
    assert not point_in_geojson(1, 1, {"type": "Point", "coordinates": [1, 1]})
    assert not point_in_geojson(1, 1, {})
