from __future__ import annotations

import logging
import re
from functools import lru_cache

import fitz  # PyMuPDF
import requests
from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag import RAGService

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_rag_service() -> RAGService:
    logger.info("Initializing RAG service")
    service = RAGService()
    logger.info("RAG service initialized")
    return service


def init_rag_service() -> None:
    # Startup warm-up hook (non-fatal if it fails).
    get_rag_service()


def _download_and_extract(url: str) -> str:
    """Download a PDF from URL and extract text."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with fitz.open(stream=response.content, filetype="pdf") as doc:
            pages: list[str] = []
            for page in doc:
                pages.append(page.get_text())
            return "\n".join(pages)
    except Exception as e:
        logger.warning("PDF extraction failed: %s", e)
        return ""


def _normalize_question_terms(question: str) -> list[str]:
    tokens = [token.strip() for token in re.split(r"\s+", question) if token.strip()]
    cleaned: list[str] = []
    for token in tokens:
        t = re.sub(r"[^\w가-힣]", "", token.lower())
        if len(t) < 2:
            continue
        t = re.sub(r"(은|는|이|가|을|를|에|에서|으로|와|과|도|요|까|죠|나요|했어|했나요)$", "", t)
        if len(t) >= 2:
            cleaned.append(t)
    return cleaned


def _clean_context_lines(context: str) -> list[str]:
    lines: list[str] = []
    for raw in context.splitlines():
        text = re.sub(r"\s+", " ", raw).strip()
        if not text:
            continue
        text = re.sub(r"[^\w가-힣\s\-\.,:/()%\[\]_·]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 3:
            continue
        lines.append(text)
    return lines


def _find_best_matches(lines: list[str], terms: list[str], limit: int = 4) -> list[str]:
    scored: list[tuple[int, int, str]] = []
    for idx, line in enumerate(lines):
        lowered = line.lower()
        score = sum(2 for term in terms if term and term in lowered)
        if score == 0 and terms:
            continue
        score += 1 if any(char.isdigit() for char in line) else 0
        scored.append((score, -idx, line))

    scored.sort(reverse=True)
    selected: list[str] = []
    seen = set()
    for _, _, line in scored:
        if line in seen:
            continue
        seen.add(line)
        selected.append(line)
        if len(selected) >= limit:
            break
    return selected


def _fallback_chat_response(question: str, context: str) -> ChatResponse:
    lines = _clean_context_lines(context)
    terms = _normalize_question_terms(question)
    matched = _find_best_matches(lines, terms)

    if matched and terms:
        key_phrase = " ".join(terms[:3])
        answer = (
            "현재 GPT 고급 분석 연결이 제한되어 문서 원문 기준으로 답변드립니다.\n"
            f"결론: 문서에서 '{key_phrase}' 관련 항목이 확인됩니다.\n"
            "근거:\n"
            + "\n".join(f"- {line}" for line in matched)
        )
    elif matched:
        answer = (
            "현재 GPT 고급 분석 연결이 제한되어 문서 원문 기준으로 답변드립니다.\n"
            "관련 원문:\n"
            + "\n".join(f"- {line}" for line in matched)
        )
    else:
        answer = (
            "현재 GPT 고급 분석 연결이 제한되어 상세 추론 답변이 어렵습니다. "
            "질문에 포함할 키워드(문서명, 항목명, 날짜, 수치)를 더 구체적으로 입력해 주세요."
        )

    return ChatResponse(
        answer=answer,
        sources=[],
        confidence="low",
        notes="AI 엔진 호출 실패로 기본 응답을 반환했습니다.",
    )


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    message = req.message
    extracted_context = ""
    if req.file_url:
        extracted_context = _download_and_extract(req.file_url)
        if extracted_context:
            # Keep prompt size bounded.
            message = (
                "다음 문서를 참고해 답변해 주세요.\n\n"
                f"[문서 내용]\n{extracted_context[:20000]}\n\n"
                f"질문: {req.message}"
            )

    try:
        rag = get_rag_service()
    except Exception as e:
        logger.exception("RAG service initialization failed: %s", e)
        return _fallback_chat_response(req.message, extracted_context)

    try:
        return rag.answer(
            message,
            domain=req.domain.value,
            top_k=req.top_k,
            doc_name=req.doc_name,
            history=req.history,
        )
    except Exception as e:
        logger.exception("Chat processing failed: %s", e)
        return _fallback_chat_response(req.message, extracted_context)
