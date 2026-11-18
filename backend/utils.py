import calendar
from datetime import date, timedelta
from typing import Tuple, Union

RU_MONTHS_NOM = [
    "",
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]

RU_MONTHS_SHORT = [
    "",
    "Янв",
    "Фев",
    "Мар",
    "Апр",
    "Май",
    "Июн",
    "Июл",
    "Авг",
    "Сен",
    "Окт",
    "Ноя",
    "Дек",
]

RU_WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def coerce_date(ref_date: Union[date, str]) -> date:
    if isinstance(ref_date, str):
        return date.fromisoformat(ref_date)
    return ref_date


def get_period_range(period: str, ref_date: Union[date, str]) -> Tuple[date, date]:
    ref_date = coerce_date(ref_date)

    if period == "day":
        return ref_date, ref_date

    if period == "week":
        start_date = ref_date - timedelta(days=ref_date.weekday())
        end_date = start_date + timedelta(days=6)
        return start_date, end_date

    if period == "month":
        start_date = ref_date.replace(day=1)
        _, last_day = calendar.monthrange(ref_date.year, ref_date.month)
        end_date = ref_date.replace(day=last_day)
        return start_date, end_date

    raise ValueError(f"Недопустимый период: '{period}'. Разрешены: 'day', 'week', 'month'")


def shift_month(year: int, month: int, delta: int) -> Tuple[int, int]:
    total_months = year * 12 + (month - 1) + delta
    new_year, zero_based_month = divmod(total_months, 12)
    return new_year, zero_based_month + 1


def month_bounds(year: int, month: int) -> Tuple[date, date]:
    _, last_day = calendar.monthrange(year, month)
    return date(year, month, 1), date(year, month, last_day)


def format_month_key(d: Union[date, Tuple[int, int]]) -> str:
    if isinstance(d, tuple):
        return f"{d[0]:04d}-{d[1]:02d}"
    return f"{d.year:04d}-{d.month:02d}"


def parse_month_key(month_key: str) -> Tuple[int, int]:
    parts = month_key.split("-")
    if len(parts) != 2:
        raise ValueError("Месяц должен быть в формате YYYY-MM")
    year, month = int(parts[0]), int(parts[1])
    if not (1 <= month <= 12 and 2000 <= year <= 2100):
        raise ValueError("Некорректный месяц")
    return year, month


def format_month_label(year: int, month: int, short: bool = False) -> str:
    names = RU_MONTHS_SHORT if short else RU_MONTHS_NOM
    return f"{names[month]} {year}"


def get_previous_period_ref(period: str, ref_date: Union[date, str]) -> date:
    ref_date = coerce_date(ref_date)

    if period == "day":
        return ref_date - timedelta(days=1)

    if period == "week":
        return ref_date - timedelta(days=7)

    if period == "month":
        prev_year, prev_month = shift_month(ref_date.year, ref_date.month, -1)
        _, last_day = calendar.monthrange(prev_year, prev_month)
        return date(prev_year, prev_month, min(ref_date.day, last_day))

    raise ValueError(f"Недопустимый период: '{period}'. Разрешены: 'day', 'week', 'month'")
