from __future__ import annotations

import requests
import fitz  # PyMuPDF (requirements.txt에 이미 포함됨)
from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag import RAGService

router = APIRouter(prefix="/api", tags=["chat"])
rag = RAGService()


def _download_and_extract(url: str) -> str:
    """S3 URL에서 PDF를 다운로드하고 텍스트를 추출합니다."""
    try:
        # 1. 파일 다운로드 (타임아웃 설정)
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # 2. PDF 텍스트 추출
        with fitz.open(stream=response.content, filetype="pdf") as doc:
            text = []
            for page in doc:
                text.append(page.get_text())
            return "\n".join(text)
    except Exception as e:
        print(f"PDF extraction failed: {e}")
        return ""


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    # 1. 파일이 있으면 내용 추출
    message = req.message
    if req.file_url:
        context = _download_and_extract(req.file_url)
        if context:
            # 2. 메시지에 문서 내용 주입 (Context Injection)
            # 토큰 제한을 고려하여 텍스트 길이 제한 (예: 20,000자)
            message = f"다음 문서를 참고하여 답변해줘.\n\n[문서 내용]\n{context[:20000]}\n\n질문: {req.message}"

    # 3. RAG 서비스 호출 (수정된 메시지 전달)
    return rag.answer(message, domain=req.domain.value, top_k=req.top_k, doc_name=req.doc_name, history=req.history)
