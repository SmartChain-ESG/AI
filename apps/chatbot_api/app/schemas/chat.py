from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Domain(str, Enum):
    safety = "safety"
    compliance = "compliance"
    esg = "esg"
    all = "all"


class SourceType(str, Enum):
    manual = "manual"
    law = "law"
    code = "code"


class SourceLoc(BaseModel):
    page: Optional[int] = None
    start: Optional[int] = None
    end: Optional[int] = None

    line_start: Optional[int] = None
    line_end: Optional[int] = None


class SourceItem(BaseModel):
    source_id: str
    title: str
    type: SourceType
    path: str
    loc: SourceLoc
    snippet: str
    score: float = Field(ge=0.0, le=1.0)


class ChatRequest(BaseModel):
    message: str
    file_url: Optional[str] = None
    session_id: Optional[str] = None
    domain: Domain = Domain.all
    top_k: int = Field(default=8, ge=1, le=30)
    doc_name: Optional[str] = None
    history: list[dict] = []

class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    confidence: Literal["low", "medium", "high"] = "medium"
    notes: str | None = None