from datetime import date

from app.worker.time_utils import get_target_month_year


def test_target_month_uses_previous_cycle_for_first_three_days():
    assert get_target_month_year(date(2026, 7, 1)) == (6, 2026, "June 2026")
    assert get_target_month_year(date(2026, 7, 3)) == (6, 2026, "June 2026")


def test_target_month_uses_current_cycle_after_boundary():
    assert get_target_month_year(date(2026, 7, 4)) == (7, 2026, "July 2026")


def test_target_month_handles_january_boundary():
    assert get_target_month_year(date(2026, 1, 2)) == (12, 2025, "December 2025")
