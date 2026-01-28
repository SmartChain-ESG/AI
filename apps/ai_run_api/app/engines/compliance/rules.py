"""Compliance 도메인 — 검증 룰 (기획서 §5.2). 담당자 확정 후 채울 것."""

from __future__ import annotations

EXPECTED_HEADERS: dict[str, list[str]] = {
    "compliance.contract.sample": ["조항", "내용"],
    "compliance.contract.status": ["성명", "계약일", "상태"],
    "compliance.privacy.policy": ["항목", "내용", "개정일"],
    "compliance.education.status": ["교육내용", "교육일", "참석자"],
}

REASON_CODES: dict[str, str] = {
    "MISSING_SLOT": "필수 슬롯 누락",
    "KEYWORD_MISSING": "필수 조항(키워드) 누락",
    "HIGH_CONTRACT_GAP": "계약 누락 비율 높음",
    "POLICY_OUTDATED": "정책 개정일 오래됨",
    "LOW_EDUCATION_RATE": "교육 이수율 기준 미달",
}
