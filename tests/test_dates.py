from datetime import date

import pytest

from skypoints.dates import parse_date


def test_parses_compact_date_into_a_date():
    assert parse_date("20101012", "%Y%m%d") == date(2010, 10, 12)

def test_rejects_impossible_date():
    with pytest.raises(ValueError):
        parse_date("20211313", "%Y%m%d")


def test_rejects_ambiguous_date_without_leading_zero():
    with pytest.raises(ValueError):
        parse_date("1052022", "%m%d%Y")