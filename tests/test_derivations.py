from datetime import date

from skypoints.derivations import calculate_age, is_stale_member


def test_age_counts_birthday_already_passed_this_year():
    assert calculate_age(date(1985, 3, 5), as_of=date(2024, 6, 1)) == 39


def test_age_excludes_birthday_not_yet_reached_this_year():
    assert calculate_age(date(1985, 3, 5), as_of=date(2024, 3, 4)) == 38

def test_member_is_stale_when_last_flight_over_90_days_ago():
    assert is_stale_member(date(2023, 10, 16), as_of=date(2024, 1, 15)) is True


def test_member_is_not_stale_at_exactly_90_days():
    assert is_stale_member(date(2023, 10, 17), as_of=date(2024, 1, 15)) is False


def test_staleness_is_unknown_without_a_flight_date():
    assert is_stale_member(None, as_of=date(2024, 1, 15)) is None