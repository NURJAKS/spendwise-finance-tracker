from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from backend import crud
from backend.database import get_db
from backend.schemas import (
    AccountCreate,
    AccountOut,
    AccountUpdate,
    TransactionOut,
    TransferCreate,
)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("", response_model=List[AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return crud.get_accounts(db)


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(data: AccountCreate, db: Session = Depends(get_db)):
    return crud.create_account(db, data)


@router.post("/transfer", response_model=List[TransactionOut], status_code=status.HTTP_201_CREATED)
def transfer_between_accounts(data: TransferCreate, db: Session = Depends(get_db)):
    return crud.create_transfer(db, data)


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int, data: AccountUpdate, db: Session = Depends(get_db)
):
    return crud.update_account(db, account_id, data)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, db: Session = Depends(get_db)):
    crud.delete_account(db, account_id)
    return None
