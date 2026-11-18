@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   SpendWise — Запуск проекта на Windows
echo ============================================

set "PY_CMD="
where python >nul 2>&1
if %errorlevel%==0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>&1
    if %errorlevel%==0 (
        set "PY_CMD=py -3"
    )
)

if "%PY_CMD%"=="" (
    echo [ОШИБКА] Python не найден в системе!
    echo Скачайте Python 3.10+ с https://www.python.org/downloads/
    echo При установке обязательно поставьте галочку "Add python.exe to PATH".
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Создание виртуального окружения .venv...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось создать виртуальное окружение.
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\uvicorn.exe" (
    echo [2/3] Установка зависимостей из requirements.txt...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось установить зависимости.
        pause
        exit /b 1
    )
)

echo [3/3] Запуск сервера SpendWise на http://127.0.0.1:8000 ...
echo Нажмите Ctrl+C в этом окне, чтобы остановить сервер.
echo.
start "" "http://127.0.0.1:8000"
".venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
pause
