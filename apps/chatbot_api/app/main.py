from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.chat import init_rag_service, router as chat_router
from app.observability.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="HD HHI Compliance Advisor Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _warmup_rag_non_blocking() -> None:
    try:
        # Do not block server startup forever if warmup gets stuck.
        await asyncio.wait_for(asyncio.to_thread(init_rag_service), timeout=20)
        logger.info("RAG warmup succeeded")
    except Exception:
        logger.exception("RAG warmup failed; server will continue to run")


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Chatbot API startup complete; scheduling RAG warmup task")
    asyncio.create_task(_warmup_rag_non_blocking())


app.include_router(chat_router)
app.include_router(admin_router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
