from __future__ import annotations

from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag import RAGService

router = APIRouter(prefix="/api", tags=["chat"])
rag = RAGService()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    return rag.answer(req.message, domain=req.domain.value, top_k=req.top_k, doc_name=req.doc_name, history=req.history)
