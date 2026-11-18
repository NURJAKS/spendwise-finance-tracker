from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend import crud
from backend.database import get_db
from backend.schemas import BudgetCategoryStatusOut, BudgetsOverviewOut, BudgetUpsert
from backend.utils import format_month_key

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


@router.get("", response_model=BudgetsOverviewOut)
def get_budgets(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
):
    month_key = month or format_month_key(date.today())
    return crud.get_budgets_overview(db, month_key)


@router.put("", response_model=BudgetCategoryStatusOut)
def upsert_budget(data: BudgetUpsert, db: Session = Depends(get_db)):
    return crud.upsert_budget(db, data)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(budget_id: int, db: Session = Depends(get_db)):
    crud.delete_budget(db, budget_id)
    return None
