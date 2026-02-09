# AI/apps/out_risk_api/app/scoring/rules.py

# 20260203 이종헌 수정: 점수/등급 변환 규칙 주석 형식 통일
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.schemas.risk import RiskLevel


# 20260131 이종헌 신규: YYYY-MM-DD 문자열 날짜 파싱 유틸
def esg_parse_date_ymd(s: str) -> Optional[datetime]:
    try:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return None


# 20260203 이종헌 수정: 최근성 가중치(30/90/180일) 계산 규칙
def esg_recency_weight(published_at: str) -> float:
    dt = esg_parse_date_ymd(published_at)
    if not dt:
        return 1.0

    now = datetime.now(timezone.utc)
    days = (now - dt).days

    if days <= 30:
        return 1.5
    if days <= 90:
        return 1.0
    if days <= 180:
        return 0.7
    return 0.5


# 20260203 이종헌 수정: total_score를 LOW/MEDIUM/HIGH로 매핑
def esg_level_from_total(total_score: float) -> RiskLevel:
    if total_score >= 10:
        return "HIGH"
    if total_score >= 5:
        return "MEDIUM"
    return "LOW"
