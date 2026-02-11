# AI/apps/out_risk_api/app/scoring/rules.py

# 20260203 이종헌 수정: 점수/등급 변환 규칙 주석 형식 통일
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.schemas.risk import RiskLevel


# 20260211 이종헌 수정: ISO/Z 형식까지 파싱하도록 확장
def esg_parse_date_ymd(s: str) -> Optional[datetime]:
    value = (s or "").strip()
    if not value:
        return None
    try:
        if "T" in value and value.endswith("Z"):
            return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            return None


# 20260211 이종헌 수정: naive datetime UTC 보정 및 기본 가중치 정합화
def esg_recency_weight(published_at: str) -> float:
    dt = esg_parse_date_ymd(published_at)
    if not dt:
        return 0.7
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    days = (now - dt).days

    if days <= 30:
        return 1.5
    if days <= 90:
        return 1.0
    if days <= 180:
        return 0.7
    return 0.4


# 20260211 이종헌 수정: RiskLevel Enum 반환으로 타입 정합성 강화
def esg_level_from_total(total_score: float) -> RiskLevel:
    if total_score >= 10:
        return RiskLevel.HIGH
    if total_score >= 5:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
