from wildlife_water_stress_atlas.ingest.gbif import fetch_occurrences


def test_fetch_elephant_occurrences_returns_data():
    records = fetch_occurrences("Loxodonta africana", limit=10)

    assert isinstance(records, list)
    assert len(records) > 0


def test_fetch_elephant_occurrences_has_coordinates():
    records = fetch_occurrences("Loxodonta africana", limit=10)

    first = records[0]

    assert "decimalLatitude" in first
    assert "decimalLongitude" in first
