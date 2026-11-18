import calendar
from datetime import date
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session, joinedload

from backend.models import (
    Account,
    Budget,
    Category,
    RecurringRule,
    SavingsGoal,
    Transaction,
)
from backend.schemas import (
    AccountCreate,
    AccountUpdate,
    BudgetUpsert,
    CategoryCreate,
    CategoryUpdate,
    GoalContribute,
    GoalCreate,
    GoalUpdate,
    ImportBatchRequest,
    RecurringCreate,
    RecurringUpdate,
    TransactionCreate,
    TransactionUpdate,
    TransferCreate,
)
from backend.utils import format_month_key, month_bounds, parse_month_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_account_id(db: Session, account_id: Optional[int]) -> Optional[int]:
    if account_id is not None:
        acc = db.query(Account).filter(Account.id == account_id).first()
        if not acc:
            raise HTTPException(status_code=422, detail=f"Счёт с id={account_id} не найден")
        return acc.id
    default_acc = db.query(Account).order_by(Account.is_default.desc(), Account.id.asc()).first()
    return default_acc.id if default_acc else None


def _validate_category_for_type(db: Session, category_id: int, tx_type: str) -> Category:
    category = get_category_by_id(db, category_id)
    if not category:
        raise HTTPException(
            status_code=422,
            detail=f"Категория с id={category_id} не найдена",
        )
    if category.type != tx_type:
        raise HTTPException(
            status_code=422,
            detail=f"Тип категории '{category.type}' не совпадает с типом операции '{tx_type}'",
        )
    return category


def transaction_to_dict(tx: Transaction) -> Dict[str, Any]:
    return {
        "id": tx.id,
        "type": tx.type,
        "amount": tx.amount,
        "category_id": tx.category_id,
        "category_name": tx.category.name if tx.category else "",
        "category_color": tx.category.color if tx.category else None,
        "category_icon": tx.category.icon if tx.category else "tag",
        "account_id": tx.account_id,
        "account_name": tx.account.name if tx.account else None,
        "note": tx.note,
        "date": tx.date,
        "is_transfer": bool(tx.is_transfer),
        "created_at": tx.created_at,
    }


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

def get_categories(db: Session) -> List[Category]:
    return db.query(Category).order_by(Category.id).all()


def get_category_by_id(db: Session, category_id: int) -> Optional[Category]:
    return db.query(Category).filter(Category.id == category_id).first()


def create_category(db: Session, data: CategoryCreate) -> Category:
    duplicate = (
        db.query(Category)
        .filter(func.lower(Category.name) == data.name.lower(), Category.type == data.type)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=422, detail="Категория с таким названием уже существует")

    cat = Category(
        name=data.name,
        type=data.type,
        color=data.color,
        icon=data.icon,
        is_default=False,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def update_category(db: Session, category_id: int, data: CategoryUpdate) -> Category:
    cat = get_category_by_id(db, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Категория не найдена")

    if data.name is not None:
        duplicate = (
            db.query(Category)
            .filter(
                func.lower(Category.name) == data.name.lower(),
                Category.type == cat.type,
                Category.id != category_id,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=422, detail="Категория с таким названием уже существует")
        cat.name = data.name
    if data.color is not None:
        cat.color = data.color
    if data.icon is not None:
        cat.icon = data.icon

    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, category_id: int, reassign_to: Optional[int] = None) -> None:
    cat = get_category_by_id(db, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    if cat.is_default:
        raise HTTPException(status_code=422, detail="Базовые категории нельзя удалить")

    tx_count = db.query(Transaction).filter(Transaction.category_id == category_id).count()
    rec_count = db.query(RecurringRule).filter(RecurringRule.category_id == category_id).count()

    if tx_count > 0 or rec_count > 0:
        if reassign_to is None:
            raise HTTPException(
                status_code=422,
                detail="Нельзя удалить категорию с операциями — сначала выберите замену",
            )
        if reassign_to == category_id:
            raise HTTPException(status_code=422, detail="Категория замены должна отличаться")
        target = get_category_by_id(db, reassign_to)
        if not target or target.type != cat.type:
            raise HTTPException(status_code=422, detail="Некорректная категория для переноса")
        db.query(Transaction).filter(Transaction.category_id == category_id).update(
            {"category_id": reassign_to}, synchronize_session=False
        )
        db.query(RecurringRule).filter(RecurringRule.category_id == category_id).update(
            {"category_id": reassign_to}, synchronize_session=False
        )

    db.query(Budget).filter(Budget.category_id == category_id).delete(synchronize_session=False)
    db.delete(cat)
    db.commit()


# ---------------------------------------------------------------------------
# Accounts / Wallets
# ---------------------------------------------------------------------------

def get_accounts(db: Session) -> List[Dict[str, Any]]:
    accounts = db.query(Account).order_by(Account.is_default.desc(), Account.id.asc()).all()
    if not accounts:
        return []

    rows = (
        db.query(
            Transaction.account_id,
            func.coalesce(
                func.sum(case((Transaction.type == "income", Transaction.amount), else_=0)), 0
            ).label("inc"),
            func.coalesce(
                func.sum(case((Transaction.type == "expense", Transaction.amount), else_=0)), 0
            ).label("exp"),
        )
        .filter(Transaction.account_id.isnot(None))
        .group_by(Transaction.account_id)
        .all()
    )
    delta_map = {r.account_id: int(r.inc) - int(r.exp) for r in rows}

    return [
        {
            "id": acc.id,
            "name": acc.name,
            "type": acc.type,
            "color": acc.color,
            "icon": acc.icon,
            "initial_balance": int(acc.initial_balance),
            "is_default": bool(acc.is_default),
            "current_balance": int(acc.initial_balance) + delta_map.get(acc.id, 0),
        }
        for acc in accounts
    ]


def create_account(db: Session, data: AccountCreate) -> Dict[str, Any]:
    acc = Account(
        name=data.name,
        type=data.type,
        color=data.color,
        icon=data.icon,
        initial_balance=data.initial_balance,
        is_default=False,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return {
        "id": acc.id,
        "name": acc.name,
        "type": acc.type,
        "color": acc.color,
        "icon": acc.icon,
        "initial_balance": int(acc.initial_balance),
        "is_default": bool(acc.is_default),
        "current_balance": int(acc.initial_balance),
    }


def update_account(db: Session, account_id: int, data: AccountUpdate) -> Dict[str, Any]:
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Счёт не найден")

    for field in ("name", "type", "color", "icon", "initial_balance"):
        val = getattr(data, field)
        if val is not None:
            setattr(acc, field, val)
    db.commit()
    db.refresh(acc)
    return next(a for a in get_accounts(db) if a["id"] == acc.id)


def delete_account(db: Session, account_id: int) -> None:
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Счёт не найден")
    if acc.is_default:
        raise HTTPException(status_code=422, detail="Основной счёт нельзя удалить")

    default_acc = db.query(Account).filter(Account.is_default.is_(True)).first()
    if default_acc:
        db.query(Transaction).filter(Transaction.account_id == account_id).update(
            {"account_id": default_acc.id}, synchronize_session=False
        )
        db.query(RecurringRule).filter(RecurringRule.account_id == account_id).update(
            {"account_id": default_acc.id}, synchronize_session=False
        )
    db.delete(acc)
    db.commit()


def create_transfer(db: Session, data: TransferCreate) -> List[Dict[str, Any]]:
    if data.from_account_id == data.to_account_id:
        raise HTTPException(status_code=422, detail="Счета отправления и зачисления должны отличаться")

    from_acc = db.query(Account).filter(Account.id == data.from_account_id).first()
    to_acc = db.query(Account).filter(Account.id == data.to_account_id).first()
    if not from_acc or not to_acc:
        raise HTTPException(status_code=422, detail="Один из выбранных счетов не найден")

    exp_cat = (
        db.query(Category).filter(Category.type == "expense").order_by(Category.id.desc()).first()
    )
    inc_cat = (
        db.query(Category).filter(Category.type == "income").order_by(Category.id.asc()).first()
    )
    if not exp_cat or not inc_cat:
        raise HTTPException(status_code=422, detail="Отсутствуют категории для перевода")

    base_note = f"Перевод: {from_acc.name} → {to_acc.name}"
    if data.note and data.note.strip():
        base_note = f"{base_note} ({data.note.strip()})"[:100]

    tx_out = Transaction(
        type="expense",
        amount=data.amount,
        category_id=exp_cat.id,
        account_id=from_acc.id,
        note=base_note,
        date=data.date,
        is_transfer=True,
    )
    tx_in = Transaction(
        type="income",
        amount=data.amount,
        category_id=inc_cat.id,
        account_id=to_acc.id,
        note=base_note,
        date=data.date,
        is_transfer=True,
    )
    db.add_all([tx_out, tx_in])
    db.commit()
    db.refresh(tx_out)
    db.refresh(tx_in)
    return [transaction_to_dict(tx_out), transaction_to_dict(tx_in)]


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

def create_transaction(db: Session, tx_data: TransactionCreate) -> Dict[str, Any]:
    _validate_category_for_type(db, tx_data.category_id, tx_data.type)
    account_id = _resolve_account_id(db, tx_data.account_id)

    db_tx = Transaction(
        type=tx_data.type,
        amount=tx_data.amount,
        category_id=tx_data.category_id,
        account_id=account_id,
        note=tx_data.note,
        date=tx_data.date,
        is_transfer=False,
    )
    db.add(db_tx)
    db.commit()

    saved = (
        db.query(Transaction)
        .options(joinedload(Transaction.category), joinedload(Transaction.account))
        .filter(Transaction.id == db_tx.id)
        .first()
    )
    return transaction_to_dict(saved)


def update_transaction(db: Session, tx_id: int, tx_data: TransactionUpdate) -> Dict[str, Any]:
    tx = (
        db.query(Transaction)
        .options(joinedload(Transaction.category), joinedload(Transaction.account))
        .filter(Transaction.id == tx_id)
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Операция не найдена")

    new_type = tx_data.type if tx_data.type is not None else tx.type
    new_cat_id = tx_data.category_id if tx_data.category_id is not None else tx.category_id
    _validate_category_for_type(db, new_cat_id, new_type)

    tx.type = new_type
    tx.category_id = new_cat_id
    if tx_data.amount is not None:
        tx.amount = tx_data.amount
    if tx_data.account_id is not None:
        tx.account_id = _resolve_account_id(db, tx_data.account_id)
    if tx_data.note is not None:
        tx.note = tx_data.note
    if tx_data.date is not None:
        tx.date = tx_data.date

    db.commit()
    db.refresh(tx)
    refreshed = (
        db.query(Transaction)
        .options(joinedload(Transaction.category), joinedload(Transaction.account))
        .filter(Transaction.id == tx.id)
        .first()
    )
    return transaction_to_dict(refreshed)


def get_transactions(
    db: Session,
    start_date: date,
    end_date: date,
    tx_type: Optional[str] = None,
    category_id: Optional[int] = None,
    account_id: Optional[int] = None,
    q: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    query = (
        db.query(Transaction)
        .options(joinedload(Transaction.category), joinedload(Transaction.account))
        .filter(Transaction.date >= start_date, Transaction.date <= end_date)
    )

    if tx_type:
        query = query.filter(Transaction.type == tx_type)
    if category_id is not None:
        query = query.filter(Transaction.category_id == category_id)
    if account_id is not None:
        query = query.filter(Transaction.account_id == account_id)
    if q and q.strip():
        needle = f"%{q.strip()}%"
        query = query.join(Category, Transaction.category_id == Category.id).filter(
            or_(Transaction.note.ilike(needle), Category.name.ilike(needle))
        )

    query = query.order_by(Transaction.date.desc(), Transaction.id.desc())
    if offset > 0:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    return [transaction_to_dict(tx) for tx in query.all()]


def delete_transaction(db: Session, tx_id: int) -> None:
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Операция не найдена")

    db.delete(tx)
    db.commit()


def import_transactions(db: Session, batch: ImportBatchRequest) -> Dict[str, int]:
    categories = {c.id: c for c in db.query(Category).all()}
    default_acc_id = _resolve_account_id(db, None)
    valid_acc_ids = {a.id for a in db.query(Account).all()}

    imported = 0
    skipped = 0
    for item in batch.items:
        cat = categories.get(item.category_id)
        if not cat or cat.type != item.type:
            skipped += 1
            continue
        acc_id = item.account_id if item.account_id in valid_acc_ids else default_acc_id
        note = item.note.strip()[:100] if item.note else None
        db.add(
            Transaction(
                type=item.type,
                amount=item.amount,
                category_id=cat.id,
                account_id=acc_id,
                note=note,
                date=item.date,
                is_transfer=False,
            )
        )
        imported += 1

    db.commit()
    return {"imported": imported, "skipped": skipped}


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

def get_budgets_overview(db: Session, month_key: str) -> Dict[str, Any]:
    year, month = parse_month_key(month_key)
    start_d, end_d = month_bounds(year, month)

    exp_categories = (
        db.query(Category).filter(Category.type == "expense").order_by(Category.id).all()
    )
    budgets = {
        b.category_id: b
        for b in db.query(Budget).filter(Budget.month == month_key).all()
    }
    spent_rows = (
        db.query(Transaction.category_id, func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.type == "expense",
            Transaction.is_transfer.is_(False),
            Transaction.date >= start_d,
            Transaction.date <= end_d,
        )
        .group_by(Transaction.category_id)
        .all()
    )
    spent_map = {cat_id: int(total) for cat_id, total in spent_rows}

    items = []
    total_limit = 0
    total_spent_budgeted = 0

    for cat in exp_categories:
        b = budgets.get(cat.id)
        spent = spent_map.get(cat.id, 0)
        limit_val = b.limit_amount if b else None
        remaining = (limit_val - spent) if limit_val is not None else None
        percent = round((spent / limit_val) * 100, 1) if (limit_val and limit_val > 0) else None

        if limit_val is None:
            status_val = "unset"
        elif spent > limit_val:
            status_val = "exceeded"
        elif percent is not None and percent >= 80.0:
            status_val = "warning"
        else:
            status_val = "ok"

        if limit_val is not None:
            total_limit += limit_val
            total_spent_budgeted += spent

        items.append(
            {
                "budget_id": b.id if b else None,
                "category_id": cat.id,
                "category_name": cat.name,
                "category_color": cat.color,
                "category_icon": cat.icon,
                "month": month_key,
                "limit_amount": limit_val,
                "spent": spent,
                "remaining": remaining,
                "percent": percent,
                "status": status_val,
            }
        )

    today = date.today()
    days_in_month = (end_d - start_d).days + 1
    if today < start_d:
        days_remaining = days_in_month
    elif today > end_d:
        days_remaining = 0
    else:
        days_remaining = (end_d - today).days + 1

    safe_daily_spend = None
    if total_limit > 0 and days_remaining > 0:
        safe_daily_spend = max(0, (total_limit - total_spent_budgeted) // days_remaining)

    return {
        "month": month_key,
        "total_limit": total_limit,
        "total_spent": sum(spent_map.values()),
        "safe_daily_spend": safe_daily_spend,
        "days_remaining": days_remaining,
        "items": items,
    }


def upsert_budget(db: Session, data: BudgetUpsert) -> Dict[str, Any]:
    parse_month_key(data.month)
    cat = get_category_by_id(db, data.category_id)
    if not cat or cat.type != "expense":
        raise HTTPException(
            status_code=422, detail="Бюджет можно установить только на категорию расхода"
        )

    existing = (
        db.query(Budget)
        .filter(Budget.category_id == data.category_id, Budget.month == data.month)
        .first()
    )
    if data.limit_amount == 0:
        if existing:
            db.delete(existing)
            db.commit()
    elif existing:
        existing.limit_amount = data.limit_amount
        db.commit()
    else:
        db.add(
            Budget(
                category_id=data.category_id,
                month=data.month,
                limit_amount=data.limit_amount,
            )
        )
        db.commit()

    overview = get_budgets_overview(db, data.month)
    return next(i for i in overview["items"] if i["category_id"] == data.category_id)


def delete_budget(db: Session, budget_id: int) -> None:
    b = db.query(Budget).filter(Budget.id == budget_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Бюджет не найден")
    db.delete(b)
    db.commit()


# ---------------------------------------------------------------------------
# Recurring Rules
# ---------------------------------------------------------------------------

def _recurring_to_dict(rule: RecurringRule, current_month: str) -> Dict[str, Any]:
    return {
        "id": rule.id,
        "type": rule.type,
        "amount": rule.amount,
        "category_id": rule.category_id,
        "account_id": rule.account_id,
        "note": rule.note,
        "day_of_month": rule.day_of_month,
        "is_active": bool(rule.is_active),
        "category_name": rule.category.name if rule.category else "",
        "category_color": rule.category.color if rule.category else "#6C7CFF",
        "category_icon": rule.category.icon if rule.category else "tag",
        "account_name": rule.account.name if rule.account else None,
        "last_applied_month": rule.last_applied_month,
        "applied_current_month": rule.last_applied_month == current_month,
    }


def get_recurring_rules(db: Session, ref_month: Optional[str] = None) -> List[Dict[str, Any]]:
    month_key = ref_month or format_month_key(date.today())
    rules = (
        db.query(RecurringRule)
        .options(joinedload(RecurringRule.category), joinedload(RecurringRule.account))
        .order_by(RecurringRule.day_of_month.asc(), RecurringRule.id.asc())
        .all()
    )
    return [_recurring_to_dict(r, month_key) for r in rules]


def create_recurring_rule(db: Session, data: RecurringCreate) -> Dict[str, Any]:
    _validate_category_for_type(db, data.category_id, data.type)
    acc_id = _resolve_account_id(db, data.account_id)
    rule = RecurringRule(
        type=data.type,
        amount=data.amount,
        category_id=data.category_id,
        account_id=acc_id,
        note=data.note.strip() if data.note else None,
        day_of_month=data.day_of_month,
        is_active=data.is_active,
    )
    db.add(rule)
    db.commit()
    saved = (
        db.query(RecurringRule)
        .options(joinedload(RecurringRule.category), joinedload(RecurringRule.account))
        .filter(RecurringRule.id == rule.id)
        .first()
    )
    return _recurring_to_dict(saved, format_month_key(date.today()))


def update_recurring_rule(db: Session, rule_id: int, data: RecurringUpdate) -> Dict[str, Any]:
    rule = (
        db.query(RecurringRule)
        .options(joinedload(RecurringRule.category), joinedload(RecurringRule.account))
        .filter(RecurringRule.id == rule_id)
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")

    new_type = data.type if data.type is not None else rule.type
    new_cat_id = data.category_id if data.category_id is not None else rule.category_id
    _validate_category_for_type(db, new_cat_id, new_type)

    rule.type = new_type
    rule.category_id = new_cat_id
    if data.amount is not None:
        rule.amount = data.amount
    if data.account_id is not None:
        rule.account_id = _resolve_account_id(db, data.account_id)
    if data.note is not None:
        rule.note = data.note.strip()
    if data.day_of_month is not None:
        rule.day_of_month = data.day_of_month
    if data.is_active is not None:
        rule.is_active = data.is_active

    db.commit()
    refreshed = (
        db.query(RecurringRule)
        .options(joinedload(RecurringRule.category), joinedload(RecurringRule.account))
        .filter(RecurringRule.id == rule.id)
        .first()
    )
    return _recurring_to_dict(refreshed, format_month_key(date.today()))


def delete_recurring_rule(db: Session, rule_id: int) -> None:
    rule = db.query(RecurringRule).filter(RecurringRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    db.delete(rule)
    db.commit()


def apply_recurring_rules(db: Session, month_key: str) -> Dict[str, Any]:
    year, month = parse_month_key(month_key)
    _, last_day = calendar.monthrange(year, month)

    rules = (
        db.query(RecurringRule)
        .filter(
            RecurringRule.is_active.is_(True),
            or_(
                RecurringRule.last_applied_month.is_(None),
                RecurringRule.last_applied_month != month_key,
            ),
        )
        .all()
    )

    created_count = 0
    default_acc_id = _resolve_account_id(db, None)
    for rule in rules:
        tx_day = min(rule.day_of_month, last_day)
        db.add(
            Transaction(
                type=rule.type,
                amount=rule.amount,
                category_id=rule.category_id,
                account_id=rule.account_id or default_acc_id,
                note=rule.note,
                date=date(year, month, tx_day),
                is_transfer=False,
            )
        )
        rule.last_applied_month = month_key
        created_count += 1

    db.commit()
    return {"month": month_key, "created_count": created_count}


# ---------------------------------------------------------------------------
# Savings Goals
# ---------------------------------------------------------------------------

def _goal_to_dict(goal: SavingsGoal) -> Dict[str, Any]:
    pct = round(min(100.0, (goal.current_amount / goal.target_amount) * 100), 1)
    remaining = max(0, goal.target_amount - goal.current_amount)
    return {
        "id": goal.id,
        "name": goal.name,
        "target_amount": goal.target_amount,
        "current_amount": goal.current_amount,
        "deadline": goal.deadline,
        "color": goal.color,
        "icon": goal.icon,
        "percent": pct,
        "remaining": remaining,
        "is_completed": goal.current_amount >= goal.target_amount,
    }


def get_goals(db: Session) -> List[Dict[str, Any]]:
    goals = db.query(SavingsGoal).order_by(SavingsGoal.id.desc()).all()
    return [_goal_to_dict(g) for g in goals]


def create_goal(db: Session, data: GoalCreate) -> Dict[str, Any]:
    goal = SavingsGoal(
        name=data.name,
        target_amount=data.target_amount,
        current_amount=data.current_amount,
        deadline=data.deadline,
        color=data.color,
        icon=data.icon,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return _goal_to_dict(goal)


def update_goal(db: Session, goal_id: int, data: GoalUpdate) -> Dict[str, Any]:
    goal = db.query(SavingsGoal).filter(SavingsGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Цель не найдена")

    for field in ("name", "target_amount", "deadline", "color", "icon"):
        val = getattr(data, field)
        if val is not None:
            setattr(goal, field, val)
    db.commit()
    db.refresh(goal)
    return _goal_to_dict(goal)


def contribute_goal(db: Session, goal_id: int, data: GoalContribute) -> Dict[str, Any]:
    goal = db.query(SavingsGoal).filter(SavingsGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Цель не найдена")

    new_amount = goal.current_amount + data.delta
    if new_amount < 0:
        raise HTTPException(status_code=422, detail="Нельзя снять больше накопленной суммы")
    goal.current_amount = new_amount
    db.commit()
    db.refresh(goal)
    return _goal_to_dict(goal)


def delete_goal(db: Session, goal_id: int) -> None:
    goal = db.query(SavingsGoal).filter(SavingsGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Цель не найдена")
    db.delete(goal)
    db.commit()


# Re-export analytics functions for backwards compatibility with any direct imports
from backend.analytics import get_stats_by_category, get_summary  # noqa: E402, F401
