import csv
import io
from datetime import date
from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend import analytics, crud
from backend.database import get_db
from backend.schemas import (
    CategorySuggestionOut,
    ImportBatchRequest,
    ImportResultOut,
    TransactionCreate,
    TransactionOut,
    TransactionUpdate,
)
from backend.utils import get_period_range

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    tx_data: TransactionCreate,
    db: Session = Depends(get_db),
):
    return crud.create_transaction(db, tx_data)


@router.get("", response_model=List[TransactionOut])
def list_transactions(
    period: Literal["day", "week", "month"] = Query("month"),
    date: date = Query(default_factory=date.today),
    type: Optional[Literal["income", "expense"]] = Query(None),
    category_id: Optional[int] = Query(None),
    account_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None, max_length=100),
    limit: Optional[int] = Query(None, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    start_date, end_date = get_period_range(period, date)
    return crud.get_transactions(
        db,
        start_date=start_date,
        end_date=end_date,
        tx_type=type,
        category_id=category_id,
        account_id=account_id,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get("/export")
def export_transactions_csv(
    period: Literal["day", "week", "month"] = Query("month"),
    date: date = Query(default_factory=date.today),
    type: Optional[Literal["income", "expense"]] = Query(None),
    category_id: Optional[int] = Query(None),
    account_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None, max_length=100),
    db: Session = Depends(get_db),
):
    start_date, end_date = get_period_range(period, date)
    items = crud.get_transactions(
        db,
        start_date=start_date,
        end_date=end_date,
        tx_type=type,
        category_id=category_id,
        account_id=account_id,
        q=q,
    )

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["Дата", "Тип", "Категория", "Счёт", "Сумма (₸)", "Заметка"])
    for tx in items:
        writer.writerow([
            tx["date"].isoformat() if hasattr(tx["date"], "isoformat") else str(tx["date"]),
            "Доход" if tx["type"] == "income" else "Расход",
            tx["category_name"],
            tx.get("account_name") or "",
            tx["amount"],
            tx.get("note") or "",
        ])

    csv_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
    filename = f"spendwise-{start_date.isoformat()}-to-{end_date.isoformat()}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", response_model=ImportResultOut, status_code=status.HTTP_201_CREATED)
def import_transactions(
    batch: ImportBatchRequest,
    db: Session = Depends(get_db),
):
    return crud.import_transactions(db, batch)


@router.get("/suggest-category", response_model=CategorySuggestionOut)
def suggest_category(
    note: str = Query(..., min_length=1, max_length=100),
    type: Literal["income", "expense"] = Query("expense"),
    db: Session = Depends(get_db),
):
    return analytics.suggest_category_for_note(db, note=note, tx_type=type)


@router.patch("/{transaction_id}", response_model=TransactionOut)
def update_transaction(
    transaction_id: int,
    tx_data: TransactionUpdate,
    db: Session = Depends(get_db),
):
    return crud.update_transaction(db, transaction_id, tx_data)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
):
    crud.delete_transaction(db, transaction_id)
    return None
