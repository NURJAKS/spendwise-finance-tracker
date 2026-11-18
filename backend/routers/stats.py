from datetime import date
from typing import List, Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend import analytics
from backend.database import get_db
from backend.schemas import (
    CategoryStatOut,
    ComparisonSeriesOut,
    ForecastOut,
    SummaryOut,
)
from backend.utils import get_period_range, get_previous_period_ref

router = APIRouter(tags=["stats & summary"])


@router.get("/api/summary", response_model=SummaryOut)
def get_summary(
    period: Literal["day", "week", "month"] = Query("month"),
    date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
):
    start_date, end_date = get_period_range(period, date)
    prev_ref = get_previous_period_ref(period, date)
    prev_start, prev_end = get_period_range(period, prev_ref)
    return analytics.get_summary(
        db,
        start_date=start_date,
        end_date=end_date,
        prev_start=prev_start,
        prev_end=prev_end,
    )


@router.get("/api/stats/by-category", response_model=List[CategoryStatOut])
def get_stats_by_category(
    period: Literal["day", "week", "month"] = Query("month"),
    date: date = Query(default_factory=date.today),
    type: Literal["expense", "income"] = Query("expense"),
    db: Session = Depends(get_db),
):
    start_date, end_date = get_period_range(period, date)
    return analytics.get_stats_by_category(
        db, start_date=start_date, end_date=end_date, tx_type=type
    )


@router.get("/api/stats/comparison", response_model=ComparisonSeriesOut)
def get_period_comparison(
    period: Literal["day", "week", "month"] = Query("month"),
    date: date = Query(default_factory=date.today),
    type: Literal["expense", "income"] = Query("expense"),
    db: Session = Depends(get_db),
):
    return analytics.get_period_comparison(db, period=period, ref_date=date, tx_type=type)


@router.get("/api/stats/forecast", response_model=ForecastOut)
def get_expense_forecast(
    date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
):
    return analytics.get_expense_forecast(db, ref_date=date)
