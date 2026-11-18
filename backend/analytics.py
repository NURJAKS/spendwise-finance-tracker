import calendar
import math
import re
from collections import Counter, defaultdict
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from backend.models import Budget, Category, RecurringRule, Transaction
from backend.utils import (
    RU_WEEKDAYS_SHORT,
    coerce_date,
    format_month_key,
    format_month_label,
    get_period_range,
    get_previous_period_ref,
    month_bounds,
    shift_month,
)

KEYWORD_RULES = {
    "expense": [
        (
            1,
            (
                "magnum", "small", "galmart", "arbuz", "анвар", "продукт", "супермаркет",
                "молок", "хлеб", "яйц", "мяс", "сыр", "овощ", "фрукт", "еда", "выпечк",
                "базар", "гастроном",
            ),
        ),
        (
            2,
            (
                "onay", "онай", "такси", "яндекс", "indrive", "uber", "автобус",
                "метро", "проезд", "билет", "бензин", "троллейбус",
            ),
        ),
        (
            3,
            (
                "учеб", "книг", "тетрад", "канц", "печать", "курс", "универ",
                "колледж", "лекц", "реферат", "coursera", "udemy", "stepik",
            ),
        ),
        (
            4,
            (
                "кино", "кафе", "кофе", "пицц", "додо", "боулинг", "бургер",
                "ресторан", "бар", "игр", "steam", "подписк", "spotify", "netflix",
                "kfc", "mcdonald", "десерт",
            ),
        ),
        (
            5,
            (
                "аптек", "лекар", "стрижк", "подар", "хозтов", "одежд",
                "связь", "мобил", "интернет", "kaspi", "коммунал",
            ),
        ),
    ],
    "income": [
        (6, ("стипенд", "зарплат", "аванс", "оклад", "перевод от родит")),
        (7, ("подработ", "фриланс", "проект", "верстк", "репетитор", "заказ", "бонус")),
    ],
}


def _pct_change(current: int, previous: int) -> Optional[float]:
    if previous == 0:
        return None if current == 0 else 100.0
    return round(((current - previous) / previous) * 100, 1)


def _period_totals(db: Session, start_date: date, end_date: date) -> Tuple[int, int]:
    row = (
        db.query(
            func.coalesce(
                func.sum(case((Transaction.type == "income", Transaction.amount), else_=0)), 0
            ).label("income"),
            func.coalesce(
                func.sum(case((Transaction.type == "expense", Transaction.amount), else_=0)), 0
            ).label("expense"),
        )
        .filter(
            Transaction.date >= start_date,
            Transaction.date <= end_date,
            Transaction.is_transfer.is_(False),
        )
        .one()
    )
    return int(row.income or 0), int(row.expense or 0)


def get_summary(
    db: Session,
    start_date: date,
    end_date: date,
    prev_start: Optional[date] = None,
    prev_end: Optional[date] = None,
) -> Dict[str, Any]:
    income_sum, expense_sum = _period_totals(db, start_date, end_date)
    balance = income_sum - expense_sum

    if prev_start is None or prev_end is None:
        days_span = (end_date - start_date).days + 1
        prev_end_calc = date.fromordinal(start_date.toordinal() - 1)
        prev_start_calc = date.fromordinal(prev_end_calc.toordinal() - days_span + 1)
        prev_start, prev_end = prev_start_calc, prev_end_calc

    prev_income, prev_expense = _period_totals(db, prev_start, prev_end)
    prev_balance = prev_income - prev_expense

    month_key = format_month_key(start_date)
    m_start, m_end = month_bounds(start_date.year, start_date.month)
    today = date.today()
    if today < m_start:
        days_remaining = (m_end - m_start).days + 1
    elif today > m_end:
        days_remaining = 0
    else:
        days_remaining = (m_end - today).days + 1

    total_budget = (
        db.query(func.coalesce(func.sum(Budget.limit_amount), 0))
        .filter(Budget.month == month_key)
        .scalar()
        or 0
    )

    safe_daily_spend = None
    if total_budget > 0 and days_remaining > 0:
        _, month_exp = _period_totals(db, m_start, m_end)
        safe_daily_spend = max(0, (int(total_budget) - month_exp) // days_remaining)

    return {
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "income": income_sum,
        "expense": expense_sum,
        "balance": balance,
        "prev_income": prev_income,
        "prev_expense": prev_expense,
        "prev_balance": prev_balance,
        "expense_change_pct": _pct_change(expense_sum, prev_expense),
        "income_change_pct": _pct_change(income_sum, prev_income),
        "safe_daily_spend": safe_daily_spend,
        "days_remaining": days_remaining,
    }


def get_stats_by_category(
    db: Session, start_date: date, end_date: date, tx_type: str = "expense"
) -> List[Dict[str, Any]]:
    results = (
        db.query(
            Category.id.label("category_id"),
            Category.name.label("name"),
            Category.color.label("color"),
            Category.icon.label("icon"),
            func.sum(Transaction.amount).label("total"),
        )
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.type == tx_type,
            Transaction.is_transfer.is_(False),
            Transaction.date >= start_date,
            Transaction.date <= end_date,
        )
        .group_by(Category.id, Category.name, Category.color, Category.icon)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )

    total_sum = sum(row.total for row in results)
    if total_sum == 0:
        return []

    return [
        {
            "category_id": row.category_id,
            "name": row.name,
            "color": row.color,
            "icon": row.icon or "tag",
            "total": int(row.total),
            "percent": round((row.total / total_sum) * 100, 1),
        }
        for row in results
    ]


def _format_period_short(period: str, start_d: date, end_d: date) -> str:
    if period == "day":
        return start_d.strftime("%d.%m.%Y")
    if period == "week":
        return f"{start_d.strftime('%d.%m')}–{end_d.strftime('%d.%m')}"
    return format_month_label(start_d.year, start_d.month)


def get_period_comparison(
    db: Session, period: str, ref_date: date, tx_type: str = "expense"
) -> Dict[str, Any]:
    ref_date = coerce_date(ref_date)
    cur_start, cur_end = get_period_range(period, ref_date)
    prev_ref = get_previous_period_ref(period, ref_date)
    prev_start, prev_end = get_period_range(period, prev_ref)

    cur_label = _format_period_short(period, cur_start, cur_end)
    prev_label = _format_period_short(period, prev_start, prev_end)

    if period == "day":
        cur_rows = get_stats_by_category(db, cur_start, cur_end, tx_type=tx_type)
        prev_rows = get_stats_by_category(db, prev_start, prev_end, tx_type=tx_type)
        cur_map = {r["name"]: r["total"] for r in cur_rows}
        prev_map = {r["name"]: r["total"] for r in prev_rows}

        ordered_names = list(cur_map.keys()) + [n for n in prev_map.keys() if n not in cur_map]
        cur_vals = [cur_map.get(n, 0) for n in ordered_names]
        prev_vals = [prev_map.get(n, 0) for n in ordered_names]

        cur_tot = sum(cur_vals)
        prev_tot = sum(prev_vals)

        cur_cum: List[Optional[int]] = []
        prev_cum: List[Optional[int]] = []
        running_c, running_p = 0, 0
        for c_v, p_v in zip(cur_vals, prev_vals):
            running_c += c_v
            running_p += p_v
            cur_cum.append(running_c)
            prev_cum.append(running_p)

        return {
            "period": period,
            "type": tx_type,
            "mode": "category",
            "current_label": cur_label,
            "previous_label": prev_label,
            "labels": ordered_names,
            "current_daily": cur_vals,
            "previous_daily": prev_vals,
            "current_cumulative": cur_cum,
            "previous_cumulative": prev_cum,
            "current_total": cur_tot,
            "previous_total": prev_tot,
            "pace_current_total": cur_tot,
            "pace_previous_total": prev_tot,
            "delta_pct": _pct_change(cur_tot, prev_tot),
        }

    cur_txs = (
        db.query(Transaction.date, func.sum(Transaction.amount))
        .filter(
            Transaction.type == tx_type,
            Transaction.is_transfer.is_(False),
            Transaction.date >= cur_start,
            Transaction.date <= cur_end,
        )
        .group_by(Transaction.date)
        .all()
    )
    prev_txs = (
        db.query(Transaction.date, func.sum(Transaction.amount))
        .filter(
            Transaction.type == tx_type,
            Transaction.is_transfer.is_(False),
            Transaction.date >= prev_start,
            Transaction.date <= prev_end,
        )
        .group_by(Transaction.date)
        .all()
    )

    cur_by_date = {d: int(total) for d, total in cur_txs}
    prev_by_date = {d: int(total) for d, total in prev_txs}

    cur_len = (cur_end - cur_start).days + 1
    prev_len = (prev_end - prev_start).days + 1
    axis_len = max(cur_len, prev_len)
    labels = RU_WEEKDAYS_SHORT if period == "week" else [str(i + 1) for i in range(axis_len)]

    today = date.today()
    if today < cur_start:
        cur_cutoff = -1
    elif today > cur_end:
        cur_cutoff = cur_len - 1
    else:
        cur_cutoff = (today - cur_start).days

    cur_daily: List[Optional[int]] = []
    prev_daily: List[Optional[int]] = []
    cur_cum: List[Optional[int]] = []
    prev_cum: List[Optional[int]] = []

    run_c = 0
    run_p = 0
    for idx in range(axis_len):
        if idx < cur_len and idx <= cur_cutoff:
            d = date.fromordinal(cur_start.toordinal() + idx)
            val = cur_by_date.get(d, 0)
            run_c += val
            cur_daily.append(val)
            cur_cum.append(run_c)
        else:
            cur_daily.append(None)
            cur_cum.append(None)

        if idx < prev_len:
            d_p = date.fromordinal(prev_start.toordinal() + idx)
            val_p = prev_by_date.get(d_p, 0)
            run_p += val_p
            prev_daily.append(val_p)
            prev_cum.append(run_p)
        else:
            prev_daily.append(None)
            prev_cum.append(None)

    pace_idx = min(max(cur_cutoff, 0), prev_len - 1) if cur_cutoff >= 0 else 0
    pace_prev_total = prev_cum[pace_idx] or 0 if prev_cum else 0
    pace_cur_total = run_c

    return {
        "period": period,
        "type": tx_type,
        "mode": "timeline",
        "current_label": cur_label,
        "previous_label": prev_label,
        "labels": labels,
        "current_daily": cur_daily,
        "previous_daily": prev_daily,
        "current_cumulative": cur_cum,
        "previous_cumulative": prev_cum,
        "current_total": run_c,
        "previous_total": run_p,
        "pace_current_total": pace_cur_total,
        "pace_previous_total": pace_prev_total if cur_cutoff >= 0 else run_p,
        "delta_pct": _pct_change(
            pace_cur_total, pace_prev_total if cur_cutoff >= 0 else run_p
        ),
    }


def _weighted_average(values: List[float]) -> float:
    if not values:
        return 0.0
    weights = [i + 1 for i in range(len(values))]
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)


def _damped_trend_slope(values: List[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    if den == 0:
        return 0.0
    slope = num / den
    cap = 0.2 * y_mean if y_mean > 0 else 0.0
    return max(-cap, min(cap, slope))


def get_expense_forecast(db: Session, ref_date: date) -> Dict[str, Any]:
    ref_date = coerce_date(ref_date)
    cur_year, cur_month = ref_date.year, ref_date.month
    nxt_year, nxt_month = shift_month(cur_year, cur_month, 1)

    cur_month_key = format_month_key((cur_year, cur_month))
    nxt_month_key = format_month_key((nxt_year, nxt_month))
    cur_month_label = format_month_label(cur_year, cur_month)
    nxt_month_label = format_month_label(nxt_year, nxt_month)

    past_months = [shift_month(cur_year, cur_month, -i) for i in range(5, 0, -1)]
    window_start, _ = month_bounds(*past_months[0])
    _, window_end = month_bounds(cur_year, cur_month)

    tx_rows = (
        db.query(
            Transaction.date,
            Transaction.type,
            Transaction.amount,
            Transaction.category_id,
        )
        .filter(
            Transaction.is_transfer.is_(False),
            Transaction.date >= window_start,
            Transaction.date <= window_end,
        )
        .all()
    )

    monthly_exp: Dict[str, int] = defaultdict(int)
    monthly_inc: Dict[str, int] = defaultdict(int)
    cat_monthly_exp: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for tx_date, tx_type, amount, cat_id in tx_rows:
        m_key = format_month_key(tx_date)
        if tx_type == "expense":
            monthly_exp[m_key] += int(amount)
            cat_monthly_exp[cat_id][m_key] += int(amount)
        elif tx_type == "income":
            monthly_inc[m_key] += int(amount)

    past_expense_series: List[float] = []
    past_income_series: List[float] = []
    for y, m in past_months:
        mk = format_month_key((y, m))
        if monthly_exp[mk] > 0:
            past_expense_series.append(float(monthly_exp[mk]))
        if monthly_inc[mk] > 0:
            past_income_series.append(float(monthly_inc[mk]))

    hist_weighted_exp = _weighted_average(past_expense_series)

    cur_actual = monthly_exp[cur_month_key]
    cur_income = monthly_inc[cur_month_key]
    today = date.today()
    is_current_ongoing = (today.year, today.month) == (cur_year, cur_month)
    days_in_cur = calendar.monthrange(cur_year, cur_month)[1]

    if is_current_ongoing:
        days_elapsed = max(1, today.day)
        raw_run_rate = (cur_actual / days_elapsed) * days_in_cur
        if hist_weighted_exp > 0:
            if days_elapsed < 7:
                alpha = days_elapsed / 7.0
                projected = alpha * raw_run_rate + (1.0 - alpha) * hist_weighted_exp
            else:
                projected = 0.7 * raw_run_rate + 0.3 * hist_weighted_exp
        else:
            projected = raw_run_rate
        cur_projected = max(cur_actual, round(projected))
    else:
        cur_projected = cur_actual

    active_recurring_exp = (
        db.query(func.coalesce(func.sum(RecurringRule.amount), 0))
        .filter(RecurringRule.is_active.is_(True), RecurringRule.type == "expense")
        .scalar()
        or 0
    )
    active_recurring_inc = (
        db.query(func.coalesce(func.sum(RecurringRule.amount), 0))
        .filter(RecurringRule.is_active.is_(True), RecurringRule.type == "income")
        .scalar()
        or 0
    )

    series_for_forecast = list(past_expense_series)
    if cur_projected > 0:
        series_for_forecast.append(float(cur_projected))

    months_analyzed = len(past_expense_series) + (1 if cur_actual > 0 else 0)

    if not series_for_forecast:
        forecast_next = int(active_recurring_exp)
        hist_avg_base = float(forecast_next)
        sigma = forecast_next * 0.12
    elif len(series_for_forecast) == 1:
        forecast_next = max(round(series_for_forecast[0]), int(active_recurring_exp))
        hist_avg_base = series_for_forecast[0]
        sigma = forecast_next * 0.15
    else:
        w_avg = _weighted_average(series_for_forecast)
        slope = _damped_trend_slope(series_for_forecast)
        raw_forecast = max(0.0, w_avg + 0.5 * slope)
        forecast_next = max(round(raw_forecast), int(active_recurring_exp))
        hist_avg_base = sum(past_expense_series) / len(past_expense_series) if past_expense_series else series_for_forecast[0]
        mean_s = sum(series_for_forecast) / len(series_for_forecast)
        variance = sum((x - mean_s) ** 2 for x in series_for_forecast) / len(series_for_forecast)
        sigma = max(math.sqrt(variance), forecast_next * 0.08)

    forecast_low = max(0, round(forecast_next - sigma))
    forecast_high = round(forecast_next + sigma)

    income_series = list(past_income_series)
    if cur_income > 0:
        income_series.append(float(cur_income))
    expected_income = max(round(_weighted_average(income_series)), int(active_recurring_inc)) if income_series else int(active_recurring_inc)
    expected_savings = expected_income - forecast_next

    trend_percent = (
        round(((forecast_next - hist_avg_base) / hist_avg_base) * 100, 1)
        if hist_avg_base > 0
        else 0.0
    )

    if months_analyzed >= 3:
        confidence = "high"
    elif months_analyzed == 2:
        confidence = "medium"
    else:
        confidence = "low"

    # Build chart timeline: last 4 past months + current month + next month forecast
    history_points: List[Dict[str, Any]] = []
    for y, m in past_months[-4:]:
        mk = format_month_key((y, m))
        history_points.append(
            {
                "month": mk,
                "label": format_month_label(y, m, short=True),
                "actual_expense": monthly_exp[mk],
                "actual_income": monthly_inc[mk],
                "projected_expense": None,
                "is_current": False,
                "is_forecast": False,
            }
        )

    history_points.append(
        {
            "month": cur_month_key,
            "label": format_month_label(cur_year, cur_month, short=True),
            "actual_expense": cur_actual,
            "actual_income": cur_income,
            "projected_expense": cur_projected,
            "is_current": True,
            "is_forecast": False,
        }
    )

    history_points.append(
        {
            "month": nxt_month_key,
            "label": format_month_label(nxt_year, nxt_month, short=True),
            "actual_expense": 0,
            "actual_income": 0,
            "projected_expense": forecast_next,
            "is_current": False,
            "is_forecast": True,
        }
    )

    # Per-category forecast
    exp_categories = (
        db.query(Category).filter(Category.type == "expense").order_by(Category.id).all()
    )
    budgets_nxt = {
        b.category_id: b.limit_amount
        for b in db.query(Budget).filter(Budget.month == nxt_month_key).all()
    }
    budgets_cur = {
        b.category_id: b.limit_amount
        for b in db.query(Budget).filter(Budget.month == cur_month_key).all()
    }

    raw_cat_forecasts: List[Tuple[Category, int, int, float]] = []
    for cat in exp_categories:
        cat_vals: List[float] = []
        for y, m in past_months:
            mk = format_month_key((y, m))
            if monthly_exp[mk] > 0:
                cat_vals.append(float(cat_monthly_exp[cat.id].get(mk, 0)))

        cur_cat = cat_monthly_exp[cat.id].get(cur_month_key, 0)
        avg_past = round(sum(cat_vals) / len(cat_vals)) if cat_vals else cur_cat

        if is_current_ongoing and cur_actual > 0:
            cur_cat_proj = (cur_cat / max(1, cur_actual)) * cur_projected
            cat_vals.append(cur_cat_proj)
        elif not is_current_ongoing and cur_cat > 0:
            cat_vals.append(float(cur_cat))

        est = _weighted_average(cat_vals)
        if est > 0 or cur_cat > 0:
            raw_cat_forecasts.append((cat, avg_past, cur_cat, est))

    raw_sum = sum(est for _, _, _, est in raw_cat_forecasts)
    by_category: List[Dict[str, Any]] = []
    for cat, avg_past, cur_cat, est in raw_cat_forecasts:
        if raw_sum > 0 and forecast_next > 0:
            scaled = round((est / raw_sum) * forecast_next)
        else:
            scaled = round(est)
        share_pct = round((scaled / forecast_next) * 100, 1) if forecast_next > 0 else 0.0
        b_limit = budgets_nxt.get(cat.id) or budgets_cur.get(cat.id)
        by_category.append(
            {
                "category_id": cat.id,
                "name": cat.name,
                "color": cat.color,
                "icon": cat.icon or "tag",
                "avg_monthly": avg_past,
                "current_month": cur_cat,
                "forecast_next_month": scaled,
                "budget_limit": b_limit,
                "share_pct": share_pct,
            }
        )

    by_category.sort(key=lambda item: item["forecast_next_month"], reverse=True)

    insights: List[str] = []
    if months_analyzed == 0 and active_recurring_exp == 0:
        insights.append("Добавьте траты за текущий месяц — прогноз автоматически подстроится под ваш темп.")
    else:
        if is_current_ongoing and cur_projected > 0:
            insights.append(
                f"При текущем темпе расходы за {cur_month_label.lower()} составят около {cur_projected:,} ₸."
                .replace(",", " ")
            )
        if trend_percent >= 5:
            insights.append(
                f"Расходы растут (+{trend_percent}% к среднему за прошлые месяцы) — стоит проверить необязательные траты."
            )
        elif trend_percent <= -5:
            insights.append(
                f"Отличная динамика: прогноз на {abs(trend_percent)}% ниже среднего уровня прошлых месяцев."
            )
        if by_category:
            top = by_category[0]
            insights.append(
                f"Главная статья прогноза: «{top['name']}» ({top['share_pct']}% от всех ожидаемых трат)."
            )
        over_budget = [
            c for c in by_category if c["budget_limit"] and c["forecast_next_month"] > c["budget_limit"]
        ]
        if over_budget:
            names = ", ".join(c["name"] for c in over_budget[:2])
            insights.append(f"Риск превышения лимита в следующем месяце по категориям: {names}.")

    return {
        "current_month": cur_month_key,
        "current_month_label": cur_month_label,
        "target_month": nxt_month_key,
        "target_month_label": nxt_month_label,
        "current_month_actual": cur_actual,
        "current_month_projected": cur_projected,
        "forecast_next_month": forecast_next,
        "forecast_low": forecast_low,
        "forecast_high": forecast_high,
        "expected_income": expected_income,
        "expected_savings": expected_savings,
        "trend_percent": trend_percent,
        "months_analyzed": months_analyzed,
        "confidence": confidence,
        "history": history_points,
        "by_category": by_category,
        "insights": insights,
    }


def suggest_category_for_note(
    db: Session, note: str, tx_type: str = "expense"
) -> Dict[str, Any]:
    cleaned = note.strip().lower()
    if len(cleaned) < 2:
        return {"category_id": None, "category_name": None, "confidence": "none"}

    tokens = [t for t in re.split(r"[\s,.;:!?()\-]+", cleaned) if len(t) >= 2]
    categories = {
        c.id: c
        for c in db.query(Category).filter(Category.type == tx_type).all()
    }
    if not categories:
        return {"category_id": None, "category_name": None, "confidence": "none"}

    # 1. History-based match from user's own previous transactions
    past = (
        db.query(Transaction.category_id, Transaction.note)
        .filter(
            Transaction.type == tx_type,
            Transaction.is_transfer.is_(False),
            Transaction.note.isnot(None),
        )
        .order_by(Transaction.id.desc())
        .limit(300)
        .all()
    )
    scores: Counter = Counter()
    for cat_id, past_note in past:
        if cat_id not in categories or not past_note:
            continue
        p_lower = past_note.lower()
        if cleaned in p_lower or p_lower in cleaned:
            scores[cat_id] += 5
        for tok in tokens:
            if tok in p_lower:
                scores[cat_id] += 2

    if scores:
        best_id, best_score = scores.most_common(1)[0]
        if best_score >= 2:
            return {
                "category_id": best_id,
                "category_name": categories[best_id].name,
                "confidence": "history",
            }

    # 2. Keyword rules fallback
    for cat_id, keywords in KEYWORD_RULES.get(tx_type, []):
        if cat_id in categories and any(kw in cleaned for kw in keywords):
            return {
                "category_id": cat_id,
                "category_name": categories[cat_id].name,
                "confidence": "keyword",
            }

    return {"category_id": None, "category_name": None, "confidence": "none"}
