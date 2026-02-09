# AI/apps/out_risk_api/app/analyze/summarizer.py

# 20260203 이종헌 수정: reason 요약/why 생성 및 LLM fallback 규칙 주석 보강
from __future__ import annotations
import os
import re
import logging
from dataclasses import dataclass
from typing import Optional
from app.schemas.risk import Category

logger = logging.getLogger("out_risk.summarizer")

try:
    from langchain_openai import ChatOpenAI
    _LC_AVAILABLE = True
except Exception:
    ChatOpenAI = None
    _LC_AVAILABLE = False

@dataclass
# 20260131 이종헌 신규: 요약 결과 스키마(summary/why/추정여부) 컨테이너
class esg_SummaryResult:
    summary_ko: str
    why: str
    is_estimated: bool

# 20260203 이종헌 수정: 근거 본문 길이 기반 추정 판정 보조, 근거 부족 판단 시 추정(prefix) 처리
def esg_is_evidence_weak(text: str) -> bool:
    return len((text or "").strip()) < 40

# 20260203 이종헌 수정: strict_grounding 시 추정 문구 prefix 강제
def esg_prefix_if_needed(strict: bool, is_estimated: bool, text: str) -> str:
    if strict and is_estimated and not (text or "").startswith("추정"):
        return "추정: " + (text or "")
    return text or ""

# 20260203 이종헌 수정: LLM 요약 실패 시 규칙 기반 문구로 안전 fallback
def esg_summarize_and_why(
    text: str,
    category: Category,
    severity: int,
    strict_grounding: bool,
    model: Optional[str] = None,
) -> esg_SummaryResult:
    base = (text or "").strip()
    
    # [방어] 입력 데이터 부재 시
    if not base:
        return esg_SummaryResult(
            summary_ko="추정: 분석할 외부 근거 문서가 존재하지 않습니다.",
            why="데이터 부재",
            is_estimated=True,
        )

    weak = esg_is_evidence_weak(base)
    api_key = os.getenv("OPENAI_API_KEY")

    # 1. LLM 수행
    if _LC_AVAILABLE and api_key:
        try:
            target_model = model or os.getenv("OPENAI_MODEL_LIGHT", "gpt-4o-mini")
            llm = ChatOpenAI(model=target_model, temperature=0, openai_api_key=api_key)

            prompt = (
                f"당신은 ESG 전문 분석 위원입니다. 아래 텍스트에서 {category} 리스크를 요약하세요.\n"
                "반드시 아래 형식을 지키고, 없는 사실은 지어내지 마세요.\n\n"
                "[결과 형식]\n"
                "summary_ko: 핵심 요약\n"
                "why: 근거 문장\n"
                "is_estimated: true/false\n\n"
                "[텍스트]\n" + f"{base[:3000]}"
            )

            msg = llm.invoke(prompt)
            out = str(getattr(msg, "content", msg))

            # [강화] 파싱 로직: 캡처 그룹 실패 시 None 방지
            m1 = re.search(r"summary_ko:\s*(.*)", out)
            m2 = re.search(r"why:\s*(.*)", out)
            m3 = re.search(r"is_estimated:\s*(true|false)", out, re.IGNORECASE)

            summary = m1.group(1).strip() if m1 else base[:180].replace("\n", " ")
            why = m2.group(1).strip() if m2 else "원문 내용 참조"
            is_estimated = (m3.group(1).lower() == "true") if m3 else weak

            summary = esg_prefix_if_needed(strict_grounding, is_estimated, summary)
            return esg_SummaryResult(summary_ko=summary, why=why, is_estimated=is_estimated)

        except Exception as e:
            logger.error(f"LLM Error: {e}")
            # LLM 에러 발생 시 Fallback으로 이동

    # 2. Fallback: Rule-based (LLM 불가 상황)
    snippet = base[:180].replace("\n", " ")
    return esg_SummaryResult(
        summary_ko=esg_prefix_if_needed(strict_grounding, True, f"{category} 관련 신호 감지: {snippet}"),
        why=snippet,
        is_estimated=True
    )
