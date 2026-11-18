import os
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "spendwise.db"
SQLALCHEMY_DATABASE_URL = os.environ.get(
    "SPENDWISE_DB_URL", f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DEFAULT_CATEGORIES = [
    {"id": 1, "name": "Продукты", "type": "expense", "color": "#34C38F", "icon": "cart"},
    {"id": 2, "name": "Транспорт", "type": "expense", "color": "#4F8EF7", "icon": "bus"},
    {"id": 3, "name": "Учёба", "type": "expense", "color": "#F59E0B", "icon": "book"},
    {"id": 4, "name": "Развлечения", "type": "expense", "color": "#EC4899", "icon": "film"},
    {"id": 5, "name": "Другое", "type": "expense", "color": "#8B5CF6", "icon": "box"},
    {"id": 6, "name": "Стипендия/Зарплата", "type": "income", "color": "#10B981", "icon": "wallet"},
    {"id": 7, "name": "Подработка", "type": "income", "color": "#06B6D4", "icon": "briefcase"},
]

DEFAULT_ACCOUNTS = [
    {
        "id": 1,
        "name": "Основная карта",
        "type": "card",
        "color": "#6C7CFF",
        "icon": "card",
        "initial_balance": 0,
        "is_default": True,
    },
    {
        "id": 2,
        "name": "Наличные",
        "type": "cash",
        "color": "#34C38F",
        "icon": "cash",
        "initial_balance": 0,
        "is_default": False,
    },
]


def _migrate_existing_schema(target_engine) -> None:
    """Safely add new columns and indexes to pre-existing SQLite databases."""
    if not str(target_engine.url).startswith("sqlite"):
        return

    with target_engine.begin() as conn:
        cat_cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(categories)")).fetchall()
        }
        if cat_cols:
            if "icon" not in cat_cols:
                conn.execute(
                    text("ALTER TABLE categories ADD COLUMN icon VARCHAR(32) NOT NULL DEFAULT 'tag'")
                )
            if "is_default" not in cat_cols:
                conn.execute(
                    text("ALTER TABLE categories ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT 0")
                )

        tx_cols = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(transactions)")).fetchall()
        }
        if tx_cols:
            if "account_id" not in tx_cols:
                conn.execute(text("ALTER TABLE transactions ADD COLUMN account_id INTEGER"))
            if "is_transfer" not in tx_cols:
                conn.execute(
                    text("ALTER TABLE transactions ADD COLUMN is_transfer BOOLEAN NOT NULL DEFAULT 0")
                )

            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transactions_date ON transactions (date)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transactions_type ON transactions (type)"))
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_transactions_category_id ON transactions (category_id)")
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_transactions_account_id ON transactions (account_id)")
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_transactions_is_transfer ON transactions (is_transfer)")
            )


def seed_categories(db: Session):
    from backend.models import Category

    for cat_data in DEFAULT_CATEGORIES:
        existing = db.query(Category).filter(Category.id == cat_data["id"]).first()
        if not existing:
            cat = Category(
                id=cat_data["id"],
                name=cat_data["name"],
                type=cat_data["type"],
                color=cat_data["color"],
                icon=cat_data["icon"],
                is_default=True,
            )
            db.add(cat)
        else:
            if not existing.icon or existing.icon == "tag":
                existing.icon = cat_data["icon"]
            existing.is_default = True
    db.commit()


def seed_accounts(db: Session):
    from backend.models import Account, Transaction

    if db.query(Account).count() == 0:
        for acc_data in DEFAULT_ACCOUNTS:
            db.add(Account(**acc_data))
        db.commit()

    default_acc = db.query(Account).order_by(Account.is_default.desc(), Account.id.asc()).first()
    if default_acc:
        db.query(Transaction).filter(Transaction.account_id.is_(None)).update(
            {"account_id": default_acc.id}, synchronize_session=False
        )
        db.commit()


def init_db(target_engine=None, session_factory=None):
    from backend import models  # noqa: F401

    eng = target_engine or engine
    sess_maker = session_factory or (
        sessionmaker(autocommit=False, autoflush=False, bind=eng) if target_engine else SessionLocal
    )

    Base.metadata.create_all(bind=eng)
    _migrate_existing_schema(eng)
    with sess_maker() as db:
        seed_categories(db)
        seed_accounts(db)
