import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.database import init_db
from backend.routers import (
    accounts,
    budgets,
    categories,
    goals,
    recurring,
    stats,
    transactions,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SpendWise API", version="2.0.0", lifespan=lifespan)

raw_origins = os.environ.get("SPENDWISE_CORS_ORIGINS", "*")
cors_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    if errors:
        msg = errors[0].get("msg", "Ошибка валидации")
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
        return JSONResponse(status_code=422, content={"detail": msg})
    return JSONResponse(status_code=422, content={"detail": "Ошибка валидации"})


@app.get("/api/health", tags=["system"])
def health_check():
    return {"status": "ok", "message": "Backend is running!", "version": "2.0.0"}


app.include_router(categories.router)
app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(stats.router)
app.include_router(budgets.router)
app.include_router(recurring.router)
app.include_router(goals.router)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_dir = os.path.join(BASE_DIR, "проект пайтон")

if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")
