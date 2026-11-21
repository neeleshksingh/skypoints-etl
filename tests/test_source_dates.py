from datetime import date

import pytest

from skypoints.source_dates import AmbiguousDateError, parse_unambiguous_date


@pytest.mark.parametrize(
    "text, expected",
    [
        ("8/13/1982", date(1982, 8, 13)),
        ("6/15/2022", date(2022, 6, 15)),
        ("1/1/2022", date(2022, 1, 1)),
    ],
)
def test_accepts_slashed_date_with_only_one_possible_reading(text, expected):
    assert parse_unambiguous_date(text) == expected


@pytest.mark.parametrize("text", ["3/5/2022", "12/1/1998", "3/10/2022"])
def test_rejects_slashed_date_with_two_possible_readings(text):
    with pytest.raises(AmbiguousDateError):
        parse_unambiguous_date(text)


def test_rejects_slashed_date_with_no_valid_reading():
    with pytest.raises(ValueError):
        parse_unambiguous_date("13/13/2022")