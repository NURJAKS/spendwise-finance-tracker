import unittest
from datetime import date
from backend.utils import (
    format_month_label,
    get_period_range,
    get_previous_period_ref,
    month_bounds,
    parse_month_key,
    shift_month,
)


class TestGetPeriodRange(unittest.TestCase):

    def test_day_period(self):
        start, end = get_period_range("day", "2026-10-28")
        self.assertEqual(start, date(2026, 10, 28))
        self.assertEqual(end, date(2026, 10, 28))

    def test_week_period_within_month(self):
        start, end = get_period_range("week", "2026-10-28")
        self.assertEqual(start, date(2026, 10, 26))
        self.assertEqual(end, date(2026, 11, 1))

    def test_week_period_starts_on_monday(self):
        start, end = get_period_range("week", date(2026, 10, 26))
        self.assertEqual(start, date(2026, 10, 26))
        self.assertEqual(end, date(2026, 11, 1))

    def test_week_period_ends_on_sunday(self):
        start, end = get_period_range("week", "2026-11-01")
        self.assertEqual(start, date(2026, 10, 26))
        self.assertEqual(end, date(2026, 11, 1))

    def test_month_regular_31_days(self):
        start, end = get_period_range("month", "2026-10-15")
        self.assertEqual(start, date(2026, 10, 1))
        self.assertEqual(end, date(2026, 10, 31))

    def test_month_february_leap_year(self):
        start, end = get_period_range("month", "2028-02-10")
        self.assertEqual(start, date(2028, 2, 1))
        self.assertEqual(end, date(2028, 2, 29))

    def test_month_february_non_leap_year(self):
        start, end = get_period_range("month", "2026-02-14")
        self.assertEqual(start, date(2026, 2, 1))
        self.assertEqual(end, date(2026, 2, 28))

    def test_invalid_period(self):
        with self.assertRaises(ValueError):
            get_period_range("year", "2026-10-28")

    def test_shift_month_year_boundary(self):
        self.assertEqual(shift_month(2026, 1, -1), (2025, 12))
        self.assertEqual(shift_month(2026, 12, 1), (2027, 1))
        self.assertEqual(shift_month(2026, 11, 2), (2027, 1))

    def test_previous_period_ref_clamps_month_end(self):
        self.assertEqual(get_previous_period_ref("month", "2026-03-31"), date(2026, 2, 28))
        self.assertEqual(get_previous_period_ref("week", "2026-11-11"), date(2026, 11, 4))
        self.assertEqual(get_previous_period_ref("day", "2026-11-01"), date(2026, 10, 31))

    def test_month_helpers(self):
        self.assertEqual(month_bounds(2026, 11), (date(2026, 11, 1), date(2026, 11, 30)))
        self.assertEqual(parse_month_key("2026-11"), (2026, 11))
        self.assertEqual(format_month_label(2026, 12), "Декабрь 2026")


if __name__ == "__main__":
    unittest.main()
