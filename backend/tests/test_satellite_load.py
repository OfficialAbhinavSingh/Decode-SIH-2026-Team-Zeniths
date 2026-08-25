import csv

from pipelines.satellite.load import read_csv

HEADER = ["zone_id", "observed_on", "ndvi_mean", "ndvi_baseline", "wetness_index"]


def _write(tmp_path, rows):
    path = tmp_path / "export.csv"
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return str(path)


def test_reads_a_normal_row(tmp_path):
    path = _write(tmp_path, [["Z-001", "2026-08-25", "0.41", "0.30", "0.44"]])
    (row,) = read_csv(path)
    assert row["zone_id"] == "Z-001"
    assert row["ndvi_mean"] == 0.41


def test_skips_a_zone_with_no_cloud_free_pixel(tmp_path, capsys):
    # This is the real shape GEE returns for a zone under cloud in every scene that
    # survived the export window -- reduceRegions has nothing to average, so the cell is
    # blank, not zero. float('') would crash the whole file; this must skip just that row.
    path = _write(
        tmp_path,
        [
            ["Z-001", "2026-08-25", "0.41", "0.30", "0.44"],
            ["Z-002", "2026-08-25", "", "0.28", ""],
        ],
    )
    rows = read_csv(path)
    assert [r["zone_id"] for r in rows] == ["Z-001"]
    assert "Z-002" in capsys.readouterr().out


def test_all_zones_blank_returns_empty_list(tmp_path):
    path = _write(tmp_path, [["Z-001", "2026-08-25", "", "0.30", ""]])
    assert read_csv(path) == []
