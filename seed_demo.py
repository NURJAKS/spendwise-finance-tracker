import calendar
from datetime import date
from typing import Optional
from backend.database import SessionLocal, init_db
from backend.models import Budget, RecurringRule, SavingsGoal, Transaction
from backend.utils import format_month_key, shift_month

MONTHLY_PATTERNS = [
    # (day, type, amount, category_id, account_id, note)
    (2, "expense", 6200, 1, 1, "Супермаркет Magnum"),
    (4, "expense", 1500, 2, 1, "Пополнение Onay"),
    (5, "income", 145000, 6, 1, "Стипендия и зарплата"),
    (7, "expense", 4300, 1, 2, "Продукты у дома"),
    (9, "expense", 5400, 4, 1, "Кино и кафе с друзьями"),
    (11, "expense", 2200, 2, 1, "Яндекс Такси в дождь"),
    (13, "expense", 3800, 3, 1, "Печать и учебные материалы"),
    (15, "expense", 8700, 1, 1, "Закупка продуктов на неделю"),
    (17, "expense", 3100, 5, 2, "Аптека и хозтовары"),
    (19, "income", 42000, 7, 1, "Фриланс: доработка сайта"),
    (21, "expense", 6800, 4, 1, "Пицца в Додо"),
    (23, "expense", 5500, 1, 1, "Small супермаркет"),
    (25, "expense", 1900, 2, 2, "Автобус и метро"),
    (27, "expense", 9500, 3, 1, "Онлайн-курс по Python"),
    (28, "expense", 4200, 5, 1, "Стрижка и мелочи"),
]


def _clamp_day(year: int, month: int, day: int) -> date:
    _, last_day = calendar.monthrange(year, month)
    return date(year, month, min(day, last_day))


def seed_demo_data(
    ref_today: Optional[date] = None,
    target_engine=None,
    session_factory=None,
):
    today = ref_today or date.today()
    init_db(target_engine=target_engine, session_factory=session_factory)
    sess_maker = session_factory or SessionLocal
    db = sess_maker()

    try:
        db.query(Transaction).delete()
        db.query(Budget).delete()
        db.query(RecurringRule).delete()
        db.query(SavingsGoal).delete()

        # Generate 3 previous full months + current month up to today
        offsets_scales = [
            (-3, 0.88),
            (-2, 0.96),
            (-1, 1.05),
            (0, 1.00),
        ]

        for delta, scale in offsets_scales:
            y, m = shift_month(today.year, today.month, delta)
            for day, tx_type, amount, cat_id, acc_id, note in MONTHLY_PATTERNS:
                tx_date = _clamp_day(y, m, day)
                if delta == 0 and tx_date > today:
                    continue
                scaled_amount = int(round((amount * scale) / 100.0) * 100)
                db.add(
                    Transaction(
                        type=tx_type,
                        amount=scaled_amount,
                        category_id=cat_id,
                        account_id=acc_id,
                        note=note,
                        date=tx_date,
                        is_transfer=False,
                    )
                )

        cur_month = format_month_key(today)
        demo_budgets = [
            (1, 35000),
            (2, 10000),
            (3, 18000),
            (4, 20000),
            (5, 15000),
        ]
        for cat_id, limit_amount in demo_budgets:
            db.add(Budget(category_id=cat_id, month=cur_month, limit_amount=limit_amount))

        db.add_all(
            [
                RecurringRule(
                    type="income",
                    amount=145000,
                    category_id=6,
                    account_id=1,
                    note="Ежемесячная стипендия / зарплата",
                    day_of_month=5,
                    is_active=True,
                    last_applied_month=cur_month,
                ),
                RecurringRule(
                    type="expense",
                    amount=1500,
                    category_id=2,
                    account_id=1,
                    note="Проездной Onay",
                    day_of_month=4,
                    is_active=True,
                    last_applied_month=cur_month,
                ),
                RecurringRule(
                    type="expense",
                    amount=9500,
                    category_id=3,
                    account_id=1,
                    note="Подписка на образовательные курсы",
                    day_of_month=15,
                    is_active=True,
                    last_applied_month=None,
                ),
            ]
        )

        db.add_all(
            [
                SavingsGoal(
                    name="Новый ноутбук для учёбы",
                    target_amount=450000,
                    current_amount=165000,
                    color="#6C7CFF",
                    icon="laptop",
                ),
                SavingsGoal(
                    name="Финансовая подушка",
                    target_amount=200000,
                    current_amount=85000,
                    color="#34C38F",
                    icon="shield",
                ),
            ]
        )

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
    print("Demo data seeded successfully.")
