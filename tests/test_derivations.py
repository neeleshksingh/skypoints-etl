from datetime import date

from skypoints.derivations import calculate_age


def test_age_counts_birthday_already_passed_this_year():
    assert calculate_age(date(1985, 3, 5), as_of=date(2024, 6, 1)) == 39


def test_age_excludes_birthday_not_yet_reached_this_year():
    assert calculate_age(date(1985, 3, 5), as_of=date(2024, 3, 4)) == 38