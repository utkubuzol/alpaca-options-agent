"""FastAPI entrypoint. `uvicorn app.main:app`."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.settings import get_settings
from app.routers import account, broker, notifications, runs, strategies, trades

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="alpaca-options-saas API", version="0.1.0")

_s = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_s.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (account.router, broker.router, strategies.router, trades.router,
          notifications.router, runs.router):
    app.include_router(r)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "alpaca-options-saas"}
