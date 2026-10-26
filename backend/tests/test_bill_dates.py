from datetime import date

from app.services.bills import next_due_date


def test_monthly_normal_and_year_rollover():
    assert next_due_date(date(2026, 10, 10), "MONTHLY", 10) == date(2026, 11, 10)
    assert next_due_date(date(2026, 12, 10), "MONTHLY", 10) == date(2027, 1, 10)


def test_month_end_clamps_and_recovers():
    d = next_due_date(date(2027, 1, 31), "MONTHLY", 31)
    assert d == date(2027, 2, 28)
    d = next_due_date(d, "MONTHLY", 31)  # anchor is remembered: back to the 31st
    assert d == date(2027, 3, 31)
    assert next_due_date(d, "MONTHLY", 31) == date(2027, 4, 30)


def test_leap_year_february():
    assert next_due_date(date(2028, 1, 31), "MONTHLY", 31) == date(2028, 2, 29)


def test_weekly():
    assert next_due_date(date(2026, 10, 28), "WEEKLY", 28) == date(2026, 11, 4)


def test_yearly_feb_29():
    d = next_due_date(date(2028, 2, 29), "YEARLY", 29)
    assert d == date(2029, 2, 28)
    assert next_due_date(date(2031, 2, 28), "YEARLY", 29) == date(2032, 2, 29)
