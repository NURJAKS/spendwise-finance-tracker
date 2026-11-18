import os
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import get_db, init_db
from backend.main import app
from seed_demo import seed_demo_data


class TestSpendWiseAPIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls._tmp.close()
        cls.test_db_url = f"sqlite:///{Path(cls._tmp.name).as_posix()}"
        cls.test_engine = create_engine(
            cls.test_db_url, connect_args={"check_same_thread": False}
        )
        cls.TestSession = sessionmaker(
            autocommit=False, autoflush=False, bind=cls.test_engine
        )
        init_db(target_engine=cls.test_engine, session_factory=cls.TestSession)

        def override_get_db():
            db = cls.TestSession()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.test_engine.dispose()
        if os.path.exists(cls._tmp.name):
            os.unlink(cls._tmp.name)

    def test_01_health_check(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")

    def test_02_categories_contract(self):
        response = self.client.get("/api/categories")
        self.assertEqual(response.status_code, 200)
        categories = response.json()
        self.assertGreaterEqual(len(categories), 7)

        for cat in categories:
            self.assertIn("id", cat)
            self.assertIn("name", cat)
            self.assertIn("type", cat)
            self.assertIn("color", cat)
            self.assertIn("icon", cat)
            self.assertIn(cat["type"], ["income", "expense"])
            self.assertTrue(cat["color"].startswith("#"))

    def test_03_empty_period_behavior(self):
        future_date = "2040-01-15"

        tx_res = self.client.get(f"/api/transactions?period=month&date={future_date}")
        self.assertEqual(tx_res.status_code, 200)
        self.assertEqual(tx_res.json(), [])

        summary_res = self.client.get(f"/api/summary?period=month&date={future_date}")
        self.assertEqual(summary_res.status_code, 200)
        summary = summary_res.json()
        self.assertEqual(summary["period_start"], "2040-01-01")
        self.assertEqual(summary["period_end"], "2040-01-31")
        self.assertEqual(summary["income"], 0)
        self.assertEqual(summary["expense"], 0)
        self.assertEqual(summary["balance"], 0)

        stats_res = self.client.get(f"/api/stats/by-category?period=month&date={future_date}")
        self.assertEqual(stats_res.status_code, 200)
        self.assertEqual(stats_res.json(), [])

    def test_04_transaction_lifecycle_edit_and_delete(self):
        ref_date = "2026-10-28"
        init_summary = self.client.get(f"/api/summary?period=month&date={ref_date}").json()

        payload = {
            "type": "expense",
            "amount": 1500,
            "category_id": 2,
            "note": "Интеграционный тест: автобус",
            "date": ref_date,
        }
        create_res = self.client.post("/api/transactions", json=payload)
        self.assertEqual(create_res.status_code, 201)
        created = create_res.json()
        self.assertEqual(created["amount"], 1500)
        self.assertEqual(created["category_id"], 2)
        self.assertEqual(created["category_name"], "Транспорт")
        tx_id = created["id"]

        # Edit amount & note via PATCH
        patch_res = self.client.patch(
            f"/api/transactions/{tx_id}",
            json={"amount": 2200, "note": "Интеграционный тест: такси"},
        )
        self.assertEqual(patch_res.status_code, 200)
        patched = patch_res.json()
        self.assertEqual(patched["amount"], 2200)
        self.assertEqual(patched["note"], "Интеграционный тест: такси")

        new_summary = self.client.get(f"/api/summary?period=month&date={ref_date}").json()
        self.assertEqual(new_summary["expense"], init_summary["expense"] + 2200)
        self.assertEqual(new_summary["balance"], init_summary["balance"] - 2200)

        # Search filter by note
        search_res = self.client.get(f"/api/transactions?period=day&date={ref_date}&q=такси")
        self.assertEqual(search_res.status_code, 200)
        self.assertIn(tx_id, [t["id"] for t in search_res.json()])

        # Delete & verify 404 on repeat
        del_res = self.client.delete(f"/api/transactions/{tx_id}")
        self.assertEqual(del_res.status_code, 204)

        after_del_summary = self.client.get(f"/api/summary?period=month&date={ref_date}").json()
        self.assertEqual(after_del_summary["expense"], init_summary["expense"])
        self.assertEqual(after_del_summary["balance"], init_summary["balance"])

        del_again = self.client.delete(f"/api/transactions/{tx_id}")
        self.assertEqual(del_again.status_code, 404)
        self.assertEqual(del_again.json(), {"detail": "Операция не найдена"})

    def test_05_validation_errors_format(self):
        res = self.client.post(
            "/api/transactions",
            json={
                "type": "expense",
                "amount": -500,
                "category_id": 1,
                "note": "Ошибка",
                "date": "2026-10-28",
            },
        )
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.json(), {"detail": "Сумма должна быть больше 0"})

        res = self.client.post(
            "/api/transactions",
            json={
                "type": "expense",
                "amount": 500,
                "category_id": 9999,
                "note": "Ошибка",
                "date": "2026-10-28",
            },
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("не найдена", res.json()["detail"])

        res = self.client.post(
            "/api/transactions",
            json={
                "type": "expense",
                "amount": 500,
                "category_id": 6,
                "note": "Ошибка",
                "date": "2026-10-28",
            },
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("не совпадает с типом", res.json()["detail"])

    def test_06_period_comparison_and_forecast(self):
        # Seed 3 months of realistic history relative to today
        seed_demo_data(
            ref_today=date.today(),
            target_engine=self.test_engine,
            session_factory=self.TestSession,
        )
        today_str = date.today().isoformat()

        comp_res = self.client.get(
            f"/api/stats/comparison?period=month&date={today_str}&type=expense"
        )
        self.assertEqual(comp_res.status_code, 200)
        comp = comp_res.json()
        self.assertEqual(comp["mode"], "timeline")
        self.assertGreaterEqual(len(comp["labels"]), 28)
        self.assertEqual(len(comp["current_cumulative"]), len(comp["labels"]))
        self.assertEqual(len(comp["previous_cumulative"]), len(comp["labels"]))
        self.assertGreater(comp["previous_total"], 0)

        # Also check day mode comparison
        day_comp = self.client.get(
            f"/api/stats/comparison?period=day&date={today_str}&type=expense"
        )
        self.assertEqual(day_comp.status_code, 200)
        self.assertEqual(day_comp.json()["mode"], "category")

        # Check next-month expense forecast
        forecast_res = self.client.get(f"/api/stats/forecast?date={today_str}")
        self.assertEqual(forecast_res.status_code, 200)
        f = forecast_res.json()
        self.assertGreater(f["forecast_next_month"], 0)
        self.assertLessEqual(f["forecast_low"], f["forecast_next_month"])
        self.assertGreaterEqual(f["forecast_high"], f["forecast_next_month"])
        self.assertEqual(f["confidence"], "high")
        self.assertGreaterEqual(len(f["history"]), 6)
        self.assertGreater(len(f["by_category"]), 0)
        self.assertGreater(len(f["insights"]), 0)

    def test_07_stats_by_category_structure(self):
        today_str = date.today().isoformat()
        res = self.client.get(f"/api/stats/by-category?period=month&date={today_str}")
        self.assertEqual(res.status_code, 200)
        stats = res.json()
        if stats:
            total_percent = sum(item["percent"] for item in stats)
            self.assertTrue(99.0 <= total_percent <= 101.0)
            for item in stats:
                self.assertIn("category_id", item)
                self.assertIn("name", item)
                self.assertIn("color", item)
                self.assertIn("total", item)
                self.assertIn("percent", item)

        inc_res = self.client.get(
            f"/api/stats/by-category?period=month&date={today_str}&type=income"
        )
        self.assertEqual(inc_res.status_code, 200)

    def test_08_static_files_and_cors(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers.get("content-type", ""))

        cors_res = self.client.options(
            "/api/categories",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(cors_res.status_code, 200)
        self.assertIn("access-control-allow-origin", cors_res.headers)

    def test_09_frontend_assets_served_from_proekt_python(self):
        for path in [
            "/css/style.css",
            "/js/icons.js",
            "/js/api.js",
            "/js/app.js",
            "/js/chart.js",
            "/manifest.json",
            "/sw.js",
            "/icon.svg",
        ]:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200, f"Asset failed: {path}")

    def test_10_single_frontend_directory_used(self):
        root = Path(__file__).resolve().parent.parent
        self.assertFalse((root / "frontend").exists(), "Legacy frontend/ should be removed")
        proekt_api = root / "проект пайтон" / "js" / "api.js"
        self.assertTrue(proekt_api.exists())
        self.assertIn("API_URL", proekt_api.read_text(encoding="utf-8"))

    def test_11_custom_categories_budgets_accounts_recurring_goals(self):
        # Custom category create/update/delete
        cat_res = self.client.post(
            "/api/categories",
            json={"name": "Кофе", "type": "expense", "color": "#a855f7", "icon": "coffee"},
        )
        self.assertEqual(cat_res.status_code, 201)
        cat = cat_res.json()
        self.assertEqual(cat["color"], "#A855F7")

        # Cannot delete default category
        del_default = self.client.delete("/api/categories/1")
        self.assertEqual(del_default.status_code, 422)

        del_custom = self.client.delete(f"/api/categories/{cat['id']}")
        self.assertEqual(del_custom.status_code, 204)

        # Budgets
        month_key = date.today().strftime("%Y-%m")
        b_res = self.client.put(
            "/api/budgets",
            json={"category_id": 1, "month": month_key, "limit_amount": 25000},
        )
        self.assertEqual(b_res.status_code, 200)
        self.assertEqual(b_res.json()["limit_amount"], 25000)

        # Account & transfer does not alter summary income/expense
        today_str = date.today().isoformat()
        before_sum = self.client.get(f"/api/summary?period=month&date={today_str}").json()
        tr_res = self.client.post(
            "/api/accounts/transfer",
            json={
                "from_account_id": 1,
                "to_account_id": 2,
                "amount": 10000,
                "date": today_str,
                "note": "Снятие",
            },
        )
        self.assertEqual(tr_res.status_code, 201)
        after_sum = self.client.get(f"/api/summary?period=month&date={today_str}").json()
        self.assertEqual(before_sum["income"], after_sum["income"])
        self.assertEqual(before_sum["expense"], after_sum["expense"])

        # Recurring rules idempotency
        apply_first = self.client.post(f"/api/recurring/apply?month={month_key}")
        self.assertEqual(apply_first.status_code, 200)
        apply_second = self.client.post(f"/api/recurring/apply?month={month_key}")
        self.assertEqual(apply_second.status_code, 200)
        self.assertEqual(apply_second.json()["created_count"], 0)

        # Savings goals
        g_res = self.client.post(
            "/api/goals", json={"name": "Планшет", "target_amount": 100000}
        )
        self.assertEqual(g_res.status_code, 201)
        gid = g_res.json()["id"]
        c_res = self.client.post(f"/api/goals/{gid}/contribute", json={"delta": 25000})
        self.assertEqual(c_res.status_code, 200)
        self.assertEqual(c_res.json()["percent"], 25.0)
        self.assertEqual(self.client.delete(f"/api/goals/{gid}").status_code, 204)

    def test_12_export_import_and_auto_suggest(self):
        today_str = date.today().isoformat()
        suggest = self.client.get(
            "/api/transactions/suggest-category",
            params={"note": "Супермаркет Magnum", "type": "expense"},
        )
        self.assertEqual(suggest.status_code, 200)
        self.assertEqual(suggest.json()["category_id"], 1)

        imp = self.client.post(
            "/api/transactions/import",
            json={
                "items": [
                    {
                        "type": "expense",
                        "amount": 1200,
                        "category_id": 2,
                        "note": "CSV тест Onay",
                        "date": today_str,
                    }
                ]
            },
        )
        self.assertEqual(imp.status_code, 201)
        self.assertEqual(imp.json()["imported"], 1)

        exp = self.client.get(f"/api/transactions/export?period=month&date={today_str}")
        self.assertEqual(exp.status_code, 200)
        self.assertIn("text/csv", exp.headers.get("content-type", ""))
        self.assertIn("CSV тест Onay", exp.text)

    def test_13_legacy_sqlite_migration_preserves_rows(self):
        legacy_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        legacy_tmp.close()
        try:
            conn = sqlite3.connect(legacy_tmp.name)
            conn.execute(
                "CREATE TABLE categories (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, type VARCHAR NOT NULL, color VARCHAR NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE transactions (id INTEGER PRIMARY KEY, type VARCHAR NOT NULL, amount INTEGER NOT NULL, category_id INTEGER NOT NULL, note VARCHAR, date DATE NOT NULL, created_at DATETIME)"
            )
            conn.execute(
                "INSERT INTO categories VALUES (1, 'Продукты', 'expense', '#34C38F')"
            )
            conn.execute(
                "INSERT INTO transactions VALUES (1, 'expense', 4500, 1, 'Старая запись', '2026-10-01', NULL)"
            )
            conn.commit()
            conn.close()

            eng = create_engine(
                f"sqlite:///{Path(legacy_tmp.name).as_posix()}",
                connect_args={"check_same_thread": False},
            )
            Sess = sessionmaker(autocommit=False, autoflush=False, bind=eng)
            init_db(target_engine=eng, session_factory=Sess)
            eng.dispose()

            conn = sqlite3.connect(legacy_tmp.name)
            row = conn.execute(
                "SELECT amount, note, account_id, is_transfer FROM transactions WHERE id=1"
            ).fetchone()
            cat = conn.execute(
                "SELECT icon, is_default FROM categories WHERE id=1"
            ).fetchone()
            conn.close()

            self.assertEqual(row[0], 4500)
            self.assertEqual(row[1], "Старая запись")
            self.assertEqual(row[2], 1)
            self.assertEqual(row[3], 0)
            self.assertEqual(cat[0], "cart")
            self.assertEqual(cat[1], 1)
        finally:
            if os.path.exists(legacy_tmp.name):
                os.unlink(legacy_tmp.name)


if __name__ == "__main__":
    unittest.main()
