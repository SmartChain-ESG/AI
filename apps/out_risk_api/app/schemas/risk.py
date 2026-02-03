# AI/apps/out_risk_api/app/schemas/risk.py

from __future__ import annotations

from enum import Enum  # 신규: RiskLevel을 Enum으로 통일해 런타임/검증 혼선을 제거
from pydantic import BaseModel, Field
from typing import List, Optional


# 수정: Literal 대신 Enum(str)로 정의해 RiskLevel.LOW 사용/문자열 반환 모두 안전하게 처리
class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RagConfig(BaseModel):
    enabled: bool = False  # 수정: 기본 OFF(타임아웃 안정화 목적)


class DocItem(BaseModel):
    doc_id: str
    title: str
    url: str
    source: str
    published_at: Optional[str] = None
    snippet: Optional[str] = None


class ExternalRiskDetectVendorResult(BaseModel):
    vendor: str
    external_risk_level: RiskLevel
    total_score: float = Field(ge=0)
    docs_count: int = Field(ge=0)
    reason_3lines: List[str] = Field(default_factory=list)
    evidence: List[DocItem] = Field(default_factory=list)


class ExternalRiskDetectBatchRequest(BaseModel):
    vendors: List[str]
    rag: RagConfig = Field(default_factory=RagConfig)


class ExternalRiskDetectBatchResponse(BaseModel):
    results: List[ExternalRiskDetectVendorResult] = Field(default_factory=list)


class SearchPreviewRequest(BaseModel):
    vendor: str
    gdelt_url: Optional[str] = None
    rag: RagConfig = Field(default_factory=RagConfig)


class SearchPreviewResponse(BaseModel):
    vendor: str
    used: bool
    docs_count: int
    documents: List[DocItem] = Field(default_factory=list)
