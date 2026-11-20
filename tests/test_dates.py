from datetime import date

from skypoints.dates import parse_date


def test_parses_compact_date_into_a_date():
    assert parse_date("20101012", "%Y%m%d") == date(2010, 10, 12)