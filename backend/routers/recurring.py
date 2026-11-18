from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend import crud
from backend.database import get_db
from backend.schemas import (
    RecurringApplyOut,
    RecurringCreate,
    RecurringOut,
    RecurringUpdate,
)
from backend.utils import format_month_key

router = APIRouter(prefix="/api/recurring", tags=["recurring"])


@router.get("", response_model=List[RecurringOut])
def list_recurring(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
):
    return crud.get_recurring_rules(db, ref_month=month)


@router.post("", response_model=RecurringOut, status_code=status.HTTP_201_CREATED)
def create_recurring(data: RecurringCreate, db: Session = Depends(get_db)):
    return crud.create_recurring_rule(db, data)


@router.patch("/{rule_id}", response_model=RecurringOut)
def update_recurring(
    rule_id: int, data: RecurringUpdate, db: Session = Depends(get_db)
):
    return crud.update_recurring_rule(db, rule_id, data)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recurring(rule_id: int, db: Session = Depends(get_db)):
    crud.delete_recurring_rule(db, rule_id)
    return None


@router.post("/apply", response_model=RecurringApplyOut)
def apply_recurring(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
):
    month_key = month or format_month_key(date.today())
    return crud.apply_recurring_rules(db, month_key)
