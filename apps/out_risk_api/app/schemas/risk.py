#AI/apps/out_risk_api/app/schemas/risk.py

# 20260131 이종헌 신규: 외부 위험 감지 API 스키마(요구사항 동결 버전)
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

Category = Literal[
    "SAFETY_ACCIDENT",
    "LEGAL_SANCTION",
    "LABOR_DISPUTE",
    "ENV_COMPLAINT",
    "FINANCE_LITIGATION",
]

RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class Company(BaseModel):
    name: str
    biz_no: Optional[str] = None
    vendor_id: Optional[str] = None


class SearchConfig(BaseModel):
    enabled: bool = True
    query: str = ""
    max_results: int = 20
    sources: List[str] = Field(default_factory=lambda: ["news", "gov", "court", "public_db"])
    lang: str = "ko"


class DocItem(BaseModel):
    doc_id: str
    title: str
    source: str
    published_at: str  # YYYY-MM-DD
    url: str
    text: str = ""
    snippet: str = ""


class RagConfig(BaseModel):
    enabled: bool = True
    top_k: int = 6
    chunk_size: int = 800


class Options(BaseModel):
    strict_grounding: bool = True
    return_evidence_text: bool = True


class ExternalRiskDetectRequest(BaseModel):
    company: Company
    time_window_days: int = 90
    categories: List[Category] = Field(
        default_factory=lambda: [
            "SAFETY_ACCIDENT",
            "LEGAL_SANCTION",
            "LABOR_DISPUTE",
            "ENV_COMPLAINT",
            "FINANCE_LITIGATION",
        ]
    )
    search: SearchConfig = Field(default_factory=SearchConfig)
    documents: List[DocItem] = Field(default_factory=list)
    rag: RagConfig = Field(default_factory=RagConfig)
    options: Options = Field(default_factory=Options)


class Offset(BaseModel):
    start: int = 0
    end: int = 0


class EvidenceItem(BaseModel):
    doc_id: str
    source: str
    url: str
    quote: str
    offset: Offset


class Signal(BaseModel):
    category: Category
    severity: int = 0  # 0~5
    score: float = 0.0
    title: str = ""
    summary_ko: str = ""
    why: str = ""
    published_at: str = ""
    evidence: List[EvidenceItem] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    is_estimated: bool = False


class RetrievalMeta(BaseModel):
    search_used: bool = False
    rag_used: bool = False
    docs_count: int = 0
    top_sources: List[str] = Field(default_factory=list)


class ExternalRiskDetectResponse(BaseModel):
    external_risk_level: RiskLevel
    total_score: float
    signals: List[Signal] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    disclaimer: str = ""
    retrieval_meta: RetrievalMeta