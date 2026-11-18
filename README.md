# SpendWise — Сервис учета и прогнозирования личных финансов

**SpendWise** — веб-приложение для учета доходов, расходов, бюджетов, счетов и прогнозирования будущих трат на базе **FastAPI**, **SQLite** и **Vanilla JS + Chart.js**.

---

## Основные возможности

- **Обзор и аналитика**:
  - Переключение периодов (`День` / `Неделя` / `Месяц`), кнопка `Сегодня` и горячие клавиши (`N`, `T`, `←`, `→`).
  - Карточки итогов (`Остаток`, `Доход`, `Расход`) с процентом изменения к прошлому периоду и безопасным дневным лимитом.
  - Кольцевая диаграмма по категориям (`Расходы` / `Доходы`) с фильтрацией списка при клике на категорию.
  - **Наложенное сравнение периодов (Прошлый vs Текущий)**: график наложения динамики текущего и предыдущего периодов (режимы `Накопительно` и `По дням`).
  - **Прогноз расходов на будущий месяц**: расчет ожидаемых трат следующего месяца, оценка итога текущего месяца, вероятный диапазон, прогноз по категориям и текстовые подсказки.
- **Операции**:
  - Создание, редактирование (`PATCH`), удаление, поиск по заметкам, фильтры по типу, категории и счёту.
  - Умная авто-подсказка категории при вводе заметки.
  - Экспорт в CSV и импорт выписки из CSV с предпросмотром.
- **Бюджеты, цели и счета**:
  - Месячные лимиты по категориям с прогресс-барами.
  - Цели накоплений с прогрессом и быстрыми пополнениями.
  - Регулярные платежи (стипендия, проездной, подписки) с начислением за месяц без дублей.
  - Несколько счетов/кошельков и переводы между ними (не искажают статистику доходов/расходов).
  - Пользовательские категории с цветом и SVG-иконкой.
  - Тёмная/светлая тема и поддержка PWA (`manifest.json` + `sw.js`).

---

## Требования

- **Python 3.10+** (скачать можно с [python.org/downloads](https://www.python.org/downloads/))
- **Git** (опционально — можно также скачать проект архивом через кнопку **Code → Download ZIP** на GitHub)

> **Важно для Windows:** при установке Python обязательно поставьте галочку **`Add python.exe to PATH`** внизу окна установщика.

---

## Пошаговый запуск на Windows

### Способ 1 — Самый быстрый (в один клик через `start.bat`)

1. Скачайте репозиторий:
   ```cmd
   git clone https://github.com/NURJAKS/spendwise-finance-tracker.git
   cd spendwise-finance-tracker
   ```
   *(либо скачайте ZIP с GitHub и распакуйте папку)*
2. Откройте папку проекта в Проводнике и дважды нажмите на файл **`start.bat`**.
3. Скрипт автоматически:
   - создаст виртуальное окружение `.venv`;
   - установит все зависимости из `requirements.txt`;
   - запустит сервер и откроет браузер на [http://127.0.0.1:8000](http://127.0.0.1:8000).
4. *(По желанию)* Чтобы сразу наполнить базу реалистичными демо-данными за последние 4 месяца (для графиков сравнения и прогноза), откройте PowerShell или CMD в папке проекта и выполните:
   ```cmd
   .venv\Scripts\python.exe seed_demo.py
   ```
   После этого обновите страницу в браузере (`F5`).

---

### Способ 2 — Ручной запуск через PowerShell или CMD (Windows)

#### Шаг 1. Клонируйте проект и перейдите в папку
```powershell
git clone https://github.com/NURJAKS/spendwise-finance-tracker.git
cd spendwise-finance-tracker
```

#### Шаг 2. Создайте виртуальное окружение
```powershell
python -m venv .venv
```
*(если команда `python` не найдена, используйте `py -3 -m venv .venv`)*

#### Шаг 3. Активируйте виртуальное окружение
- **В PowerShell:**
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
  > Если PowerShell выдаст ошибку политики выполнения скриптов (`ExecutionPolicy`), выполните один раз:
  > ```powershell
  > Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  > ```
  > и повторите команду активации.
- **В Командной строке (CMD):**
  ```cmd
  .venv\Scripts\activate.bat
  ```

#### Шаг 4. Установите зависимости
```powershell
pip install -r requirements.txt
```

#### Шаг 5. *(Опционально)* Заполните демонстрационными данными
```powershell
python seed_demo.py
```

#### Шаг 6. Запустите сервер
```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Шаг 7. Откройте приложение в браузере
- **Веб-приложение:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Документация API (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Проверка работы API:** [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

Для остановки сервера нажмите `Ctrl + C` в терминале.

---

## Пошаговый запуск на Linux / macOS

### Быстрый запуск
```bash
git clone https://github.com/NURJAKS/spendwise-finance-tracker.git
cd spendwise-finance-tracker
chmod +x start.sh
./start.sh
```

### Ручной запуск
```bash
git clone https://github.com/NURJAKS/spendwise-finance-tracker.git
cd spendwise-finance-tracker

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# (Опционально) Заполнить демо-данными за последние 4 месяца:
python seed_demo.py

# Запуск сервера:
uvicorn backend.main:app --reload
```

Откройте [http://127.0.0.1:8000](http://127.0.0.1:8000) в браузере.

---

## Запуск через Docker (Windows / Linux / macOS)

Если установлен **Docker Desktop**, достаточно одной команды:

```bash
docker compose up --build
```

Приложение будет доступно по адресу [http://localhost:8000](http://localhost:8000). База данных сохраняется в Docker volume `spendwise_data`.

---

## Запуск автотестов

Интеграционные и unit-тесты используют изолированную временную базу SQLite и не затрагивают вашу рабочую `spendwise.db`:

- **Windows (PowerShell / CMD):**
  ```powershell
  .\.venv\Scripts\python.exe -m unittest discover tests -v
  ```
- **Linux / macOS:**
  ```bash
  .venv/bin/python -m unittest discover tests -v
  ```

---

## Решение частых проблем (Windows)

| Проблема | Решение |
|---|---|
| `'python' is not recognized` | Переустановите Python с галочкой **Add python.exe to PATH** или используйте `py -3` вместо `python`. |
| Ошибка `running scripts is disabled` в PowerShell | Выполните `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` или используйте `CMD` / `start.bat`. |
| Порт `8000` уже занят | Запустите на другом порту: `python -m uvicorn backend.main:app --port 8080 --reload` и откройте `http://127.0.0.1:8080`. |
| Графики пустые после первого запуска | Выполните `python seed_demo.py`, чтобы загрузить тестовые данные за 4 месяца, или добавьте операции кнопкой **«+ Добавить»**. |

---

## Структура проекта

```text
spendwise-finance-tracker/
├── backend/
│   ├── main.py              # FastAPI приложение, CORS, раздача статики из "проект пайтон"
│   ├── database.py          # SQLite подключение, авто-миграция схемы и seed базовых данных
│   ├── models.py            # Category, Account, Transaction, Budget, RecurringRule, SavingsGoal
│   ├── schemas.py           # Pydantic v2 схемы валидации
│   ├── crud.py              # CRUD для операций, категорий, счетов, бюджетов, целей и правил
│   ├── analytics.py         # Сводки, структура, наложенное сравнение периодов и прогноз
│   ├── utils.py             # Расчет диапазонов дат и смещение периодов
│   └── routers/             # API роутеры: categories, transactions, stats, budgets, recurring, accounts, goals
├── проект пайтон/           # Фронтенд (HTML/CSS/JS + Chart.js + PWA)
├── tests/
│   ├── test_utils.py        # Unit-тесты утилит дат
│   └── test_integration.py  # Изолированные интеграционные тесты API и миграций
├── start.bat                # Скрипт запуска в 1 клик для Windows
├── start.sh                 # Скрипт запуска в 1 клик для Linux / macOS
├── seed_demo.py             # Генератор демонстрационных данных за 4 месяца
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```
