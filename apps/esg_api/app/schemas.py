# app/schemas.py

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Literal


class EsgFileInfo(BaseModel):
    file_id: str
    file_name: str
    file_path: str
    ext: str
    kind: str


class EsgTriageSummary(BaseModel):
    file_count: int
    kinds: list[str]
    exts: list[str]


class EsgSlotMapItem(BaseModel):
    file_id: str
    slot_name: str
    reason: str
    confidence: float


class EsgExtractedItem(BaseModel):
    file_id: str
    slot_name: str
    period_start: str
    period_end: str
    value: float
    unit: str
    evidence_ref: str
    meta: dict[str, Any] | None = None


class EsgValidationIssue(BaseModel):
    level: Literal["OK", "WARN", "FAIL"]
    code: str
    message: str
    file_id: str
    evidence_ref: str | None = None
    slot_name: str | None = None
    meta: dict[str, Any] | None = None


class EsgSummaryCard(BaseModel):
    audience: Literal["APPROVER", "PRIME"]
    lines: list[str]


class EsgAnomalyCandidate(BaseModel):
    slot_name: str
    title: str
    confidence: float
    rationale: str
    suggested_evidence: list[str]


class EsgResubmitDiff(BaseModel):
    has_previous: bool
    previous_status: str | None
    current_status: str | None
    delta_fail: int
    delta_warn: int
    fixed_issues: list[dict[str, Any]]
    new_issues: list[dict[str, Any]]
    note: str


class EsgRunResponse(BaseModel):
    # Day4 핵심: run_id/prev_run_id
    run_id: str = Field(..., description="AI 엔진 실행 식별자")
    prev_run_id: str | None = Field(default=None, description="이전 실행(run) 식별자(재제출 비교용)")
    draft_id: str

    status: Literal["OK", "WARN", "FAIL"]

    triage: EsgTriageSummary
    files: list[EsgFileInfo]

    slot_map: list[EsgSlotMapItem]
    extracted: list[EsgExtractedItem]
    issues: list[EsgValidationIssue]

    # A-2 보완요청서(문장)
    questions: list[str] = []

    # A-1 이상치 원인 후보
    anomaly_candidates: list[EsgAnomalyCandidate] = []

    # A-3 재제출 개선 비교
    resubmit_diff: EsgResubmitDiff | None = None

    summary_cards: list[EsgSummaryCard] = []