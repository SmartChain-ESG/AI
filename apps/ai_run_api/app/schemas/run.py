"""기획서 §3 기준 — preview / submit 공통 스키마."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Domain = Literal["safety", "compliance", "esg"]
Verdict = Literal["PASS", "NEED_FIX", "NEED_CLARIFY"]
RiskLevel = Literal["HIGH", "LOW"]
SlotStatusEnum = Literal["SUBMITTED", "MISSING"]


# ── Shared ──────────────────────────────────────────────
class FileRef(BaseModel):
    file_id: str
    storage_uri: str
    file_name: str = ""


class SlotHint(BaseModel):
    file_id: str
    slot_name: str
    confidence: float = Field(default=1.0, ge=0, le=1)
    match_reason: str = "filename_keyword"


class SlotStatus(BaseModel):
    slot_name: str
    status: SlotStatusEnum


# ── Preview ─────────────────────────────────────────────
class PreviewRequest(BaseModel):
    domain: Domain
    period_start: date
    period_end: date
    package_id: str | None = None
    added_files: list[FileRef]


class PreviewResponse(BaseModel):
    package_id: str
    slot_hint: list[SlotHint]
    required_slot_status: list[SlotStatus]
    missing_required_slots: list[str]


# ── Submit ──────────────────────────────────────────────
class SubmitRequest(BaseModel):
    package_id: str
    domain: Domain
    period_start: date
    period_end: date
    files: list[FileRef]
    slot_hint: list[SlotHint]


class SlotResult(BaseModel):
    slot_name: str
    verdict: Verdict
    reasons: list[str] = []
    file_ids: list[str] = []
    file_names: list[str] = []
    extras: dict[str, str] = Field(default_factory=dict)


class Clarification(BaseModel):
    slot_name: str
    message: str
    file_ids: list[str] = []


class SubmitResponse(BaseModel):
    package_id: str
    risk_level: RiskLevel
    verdict: Verdict
    why: str
    slot_results: list[SlotResult]
    clarifications: list[Clarification] = []
    extras: dict[str, str] = Field(default_factory=dict)
