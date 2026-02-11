# AI/apps/out_risk_api/app/analyze/summarizer.py

# 20260203 이종헌 수정: reason 요약/why 생성 및 LLM fallback 규칙 주석 보강
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("out_risk.summarizer")

try:
    from langchain_openai import ChatOpenAI

    _LC_AVAILABLE = True
except Exception:
    ChatOpenAI = None
    _LC_AVAILABLE = False


# 20260211 이종헌 수정: 요약 결과 컨테이너 유지(파이프라인 공통 재사용)
@dataclass
class esg_SummaryResult:
    summary_ko: str
    why: str
    is_estimated: bool


# 20260203 이종헌 수정: 근거 본문 길이 기반 추정 판정 보조
def esg_is_evidence_weak(text: str) -> bool:
    return len((text or "").strip()) < 40


# 20260203 이종헌 수정: strict_grounding 시 추정 문구 prefix 강제
def esg_prefix_if_needed(strict: bool, is_estimated: bool, text: str) -> str:
    if strict and is_estimated and not (text or "").startswith("추정"):
        return "추정: " + (text or "")
    return text or ""


# 20260211 이종헌 수정: category 타입을 문자열로 정리하고 프롬프트/파싱 안정화
def esg_summarize_and_why(
    text: str,
    category: str,
    severity: int,
    strict_grounding: bool,
    model: Optional[str] = None,
) -> esg_SummaryResult:
    base = (text or "").strip()
    category_name = (category or "GENERAL").strip() or "GENERAL"
    safe_severity = max(0, int(severity or 0))

    if not base:
        return esg_SummaryResult(
            summary_ko="추정: 분석할 외부 근거 문서가 존재하지 않습니다.",
            why="데이터 부재",
            is_estimated=True,
        )

    weak = esg_is_evidence_weak(base)
    api_key = os.getenv("OPENAI_API_KEY")

    if _LC_AVAILABLE and api_key:
        try:
            target_model = model or os.getenv("OPENAI_MODEL_LIGHT", "gpt-4o-mini")
            llm = ChatOpenAI(model=target_model, temperature=0, openai_api_key=api_key)

            prompt = (
                f"당신은 ESG 전문 분석가입니다. 아래 텍스트에서 {category_name} 이슈를 한 줄로 요약하세요.\n"
                f"심각도 참고값: {safe_severity}\n"
                "없는 사실은 만들지 말고 아래 형식을 지키세요.\n\n"
                "[결과 형식]\n"
                "summary_ko: 핵심 요약\n"
                "why: 근거 문장\n"
                "is_estimated: true/false\n\n"
                "[텍스트]\n" + f"{base[:3000]}"
            )

            msg = llm.invoke(prompt)
            out = str(getattr(msg, "content", msg))

            m1 = re.search(r"summary_ko:\s*(.*)", out)
            m2 = re.search(r"why:\s*(.*)", out)
            m3 = re.search(r"is_estimated:\s*(true|false)", out, re.IGNORECASE)

            summary = m1.group(1).strip() if m1 else base[:180].replace("\n", " ")
            why = m2.group(1).strip() if m2 else "원문 내용 참조"
            is_estimated = (m3.group(1).lower() == "true") if m3 else weak

            summary = esg_prefix_if_needed(strict_grounding, is_estimated, summary)
            return esg_SummaryResult(summary_ko=summary, why=why, is_estimated=is_estimated)
        except Exception as e:
            logger.error("LLM Error: %s", e)

    snippet = base[:180].replace("\n", " ")
    return esg_SummaryResult(
        summary_ko=esg_prefix_if_needed(strict_grounding, True, f"{category_name} 관련 신호 감지: {snippet}"),
        why=snippet,
        is_estimated=True,
    )
