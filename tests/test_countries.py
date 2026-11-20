import pytest

from skypoints.countries import normalize_country


@pytest.mark.parametrize(
    "source_code, expected",
    [
        ("USA", "USA"),
        ("IND", "IND"),
        ("CAN", "CAN"),
        ("PHIL", "PHL"),
        ("AU", "AUS"),
    ],
)
def test_normalizes_source_country_code_to_iso_alpha3(source_code, expected):
    assert normalize_country(source_code) == expected


def test_rejects_unknown_country_code():
    with pytest.raises(ValueError):
        normalize_country("XYZ")