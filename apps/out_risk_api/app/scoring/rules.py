# AI/apps/out_risk_api/app/scoring/rules.py

#  20260131 이종헌 신규: 시간 가중치/총점/등급(LOW|MEDIUM|HIGH) 산출 규칙(명세 동결)
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.schemas.risk import RiskLevel


def esg_parse_date_ymd(s: str) -> Optional[datetime]:
    try:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return None


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


def esg_level_from_total(total_score: float) -> RiskLevel:
    if total_score >= 10:
        return "HIGH"
    if total_score >= 5:
        return "MEDIUM"
    return "LOW"
