from __future__ import annotations

from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.admin import router as admin_router
from app.observability.logging import setup_logging

setup_logging()

app = FastAPI(title="HD HHI Compliance Advisor Chatbot")

app.include_router(chat_router)
app.include_router(admin_router)

@app.get("/health")
def health() -> dict:
    return {"ok": True}