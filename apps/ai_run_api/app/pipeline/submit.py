# app/pipeline/submit.py

"""
Submit 파이프라인 — 6단계 (기획서 §4.2).

(1) TRIAGE — 파일 분류 + 열 수 있는지 체크
(2) SLOT APPLY — slot_hint 적용
(3) EXTRACT — 파싱/OCR
(4) VALIDATE — 룰 검증 → slot_results (verdict + reasons)
(5) CLARIFY — PASS 아닌 것 → 보완요청 문장 생성
(6) FINAL AGGREGATE — 전체 verdict/risk/why
"""

from __future__ import annotations

import asyncio
import json
from datetime import date

from app.engines.registry import get_rules_module, get_slots_module
from app.extractors.ocr.ocr_router import extract_image
from app.extractors.pdf_text import extract_pdf
from app.extractors.xlsx import extract_xlsx
from app.llm.client import ask_llm, ask_llm_vision
from app.llm.prompts import (
    CLARIFICATION_TEMPLATE,
    DATA_ANALYSIS,
    IMAGE_VISION,
    IMAGE_VISION_USER,
    JUDGE_FINAL,
    PDF_ANALYSIS,
)
from app.pipeline.triage import triage_files
from app.schemas.run import (
    Clarification,
    FileRef,
    SlotHint,
    SlotResult,
    SubmitRequest,
    SubmitResponse,
)
from app.storage.downloader import download_file

# 도메인별 슬롯 검증 디스패치
_DOMAIN_VALIDATORS: dict[str, object] = {}


def _get_slot_validator(domain: str):
    """도메인별 validators 모듈을 lazy-load."""
    if domain not in _DOMAIN_VALIDATORS:
        try:
            import importlib
            mod = importlib.import_module(f"app.engines.{domain}.validators")
            _DOMAIN_VALIDATORS[domain] = mod
        except ModuleNotFoundError:
            _DOMAIN_VALIDATORS[domain] = None
    return _DOMAIN_VALIDATORS[domain]


# ── (3) EXTRACT + LLM 보강 ────────────────────────────────
async def _extract_and_analyse(
    file: FileRef,
    ext: str,
    file_type: str,
    slot_name: str,
    domain: str,
    period_start: date,
    period_end: date,
) -> dict:
    """파일 1개를 다운로드 → 추출 → LLM 보강. Returns raw extraction dict."""
    data = await download_file(file.storage_uri)
    fname = file.file_name or file.storage_uri.rsplit("/", 1)[-1]

    result: dict = {"file_id": file.file_id, "file_name": fname, "slot_name": slot_name}

    if file_type == "pdf":
        extracted = await extract_pdf(data, period_start, period_end)
        # LLM 보강 (GPT-4o-mini)
        extras: dict[str, str] = {}
        try:
            raw = await ask_llm(PDF_ANALYSIS, extracted["text"][:4000], heavy=False)
            llm = json.loads(raw)
            for d in llm.get("dates", []):
                if d not in extracted["dates"]:
                    extracted["dates"].append(d)
            if not extracted["signature_detected"] and llm.get("has_signature"):
                extracted["signature_detected"] = True
                extracted["reasons"] = [r for r in extracted["reasons"] if r != "SIGNATURE_MISSING"]
            extras = {k: str(v) for k, v in llm.get("extras", {}).items()}
        except Exception:
            pass
        result.update(extracted)
        result["extras"] = extras

    elif file_type == "image":
        fmt = "jpg" if ext in (".jpg", ".jpeg") else "png"
        extracted = await extract_image(data, fmt, period_start, period_end)
        # GPT-4o Vision 보강
        extras = {}
        try:
            raw = await ask_llm_vision(IMAGE_VISION, IMAGE_VISION_USER, data, fmt)
            vision = json.loads(raw)
            for d in vision.get("dates", []):
                if d not in extracted["dates"]:
                    extracted["dates"].append(d)
            if vision.get("violations"):
                extracted["reasons"].extend(["VIOLATION_DETECTED"] * 0)  # log only
            if vision.get("scene_description"):
                extras["scene_description"] = vision["scene_description"]
            extras.update({k: str(v) for k, v in vision.get("extras", {}).items()})
        except Exception:
            pass
        result.update(extracted)
        result["extras"] = extras

    elif file_type == "xlsx":
        rules_mod = get_rules_module(domain)
        expected = rules_mod.EXPECTED_HEADERS.get(slot_name, [])
        extracted = await extract_xlsx(data, ext, expected, period_start, period_end)
        # LLM 보강 (GPT-4o-mini)
        extras = {}
        try:
            raw = await ask_llm(DATA_ANALYSIS, extracted["df_preview"], heavy=False)
            llm = json.loads(raw)
            for d in llm.get("dates", []):
                if d not in extracted["dates"]:
                    extracted["dates"].append(d)
            extras = {k: str(v) for k, v in llm.get("extras", {}).items()}
        except Exception:
            pass
        result.update(extracted)
        result["extras"] = extras

    # ── 슬롯별 세부 검증 (도메인 validators) ── 
    # 250128 이종헌 reason 중복, extra_reasons None도 안전하게 처리
    validator = _get_slot_validator(domain)
    if validator is not None:
        try:
            extra_reasons = validator.validate_slot(slot_name, file_type, result) or []
            if extra_reasons:
                result.setdefault("reasons", [])
                for r in extra_reasons:
                    if r not in result["reasons"]:
                        result["reasons"].append(r)
        except Exception:
            pass       
    return result


# ── (4) VALIDATE ───────────────────────────────────────
def _validate_slot(extractions: list[dict], slot_name: str) -> SlotResult:
    """슬롯에 매핑된 모든 파일의 추출 결과를 종합하여 verdict를 결정."""
    all_reasons: list[str] = []
    file_ids: list[str] = []
    file_names: list[str] = []
    extras: dict[str, str] = {}

    for ex in extractions:
        file_ids.append(ex["file_id"])
        file_names.append(ex.get("file_name", ""))
        all_reasons.extend(ex.get("reasons", []))
        extras.update(ex.get("extras", {}))

    # reason 중복 제거
    reasons = list(dict.fromkeys(all_reasons))

    # verdict 결정
    if "OCR_FAILED" in reasons:
        verdict = "NEED_CLARIFY"
    elif any(r in reasons for r in ("DATE_MISMATCH", "SIGNATURE_MISSING", "HEADER_MISMATCH")):
        verdict = "NEED_FIX"
    elif reasons:
        verdict = "NEED_FIX"
    else:
        verdict = "PASS"

    return SlotResult(
        slot_name=slot_name,
        verdict=verdict,
        reasons=reasons,
        file_ids=file_ids,
        file_names=file_names,
        extras=extras,
    )


# ── (5) CLARIFY ───────────────────────────────────────
async def _generate_clarifications(
    slot_results: list[SlotResult],
) -> list[Clarification]:
    """PASS가 아닌 슬롯에 대해 보완요청 문장을 생성."""
    clarifications: list[Clarification] = []
    for sr in slot_results:
        if sr.verdict == "PASS":
            continue

        # 템플릿 기반 + LLM 다듬기
        reason_text = ", ".join(sr.reasons) if sr.reasons else "확인 필요"
        file_text = ", ".join(sr.file_names) if sr.file_names else "해당 파일"

        try:
            user_msg = (
                f"슬롯: {sr.slot_name}\n"
                f"사유 코드: {reason_text}\n"
                f"파일: {file_text}\n"
                f"한국어로 협력사에게 보낼 보완요청 문장을 작성해주세요."
            )
            message = await ask_llm(CLARIFICATION_TEMPLATE, user_msg, heavy=False)
        except Exception:
            # LLM 실패 시 기본 템플릿
            message = f"{file_text} 파일의 {sr.slot_name} 항목에서 문제가 발견되었습니다({reason_text}). 확인 후 재제출해 주세요."

        clarifications.append(
            Clarification(
                slot_name=sr.slot_name,
                message=message,
                file_ids=sr.file_ids,
            )
        )
    return clarifications


# ── (6) FINAL AGGREGATE ───────────────────────────────
async def _final_aggregate(
    package_id: str,
    slot_results: list[SlotResult],
    missing_slots: list[str],
    clarifications: list[Clarification],
) -> SubmitResponse:
    """전체 verdict = 슬롯 verdict 중 가장 나쁜 것. GPT-4o로 why 생성."""
    # 누락 슬롯도 slot_results에 추가
    for s in missing_slots:
        slot_results.append(
            SlotResult(
                slot_name=s,
                verdict="NEED_FIX",
                reasons=["MISSING_SLOT"],
                file_ids=[],
                file_names=[],
            )
        )

    # 가장 나쁜 verdict
    verdicts = [sr.verdict for sr in slot_results]
    if "NEED_FIX" in verdicts or "NEED_CLARIFY" in verdicts:
        overall_verdict = "NEED_FIX"
        risk_level = "HIGH"
    else:
        overall_verdict = "PASS"
        risk_level = "LOW"

    # GPT-4o로 why 생성
    extras: dict[str, str] = {}
    summary_lines = []
    for sr in slot_results:
        summary_lines.append(f"[{sr.slot_name}] verdict={sr.verdict}, reasons={sr.reasons}")
    judge_input = "\n".join(summary_lines)

    try:
        raw = await ask_llm(JUDGE_FINAL, judge_input, heavy=True)
        llm_result = json.loads(raw)
        why = llm_result.get("why", "")
        risk_level = llm_result.get("risk_level", risk_level)
        overall_verdict = llm_result.get("verdict", overall_verdict)
        extras = {k: str(v) for k, v in llm_result.get("extras", {}).items()}
    except Exception:
        why = "필수 항목이 부족하거나 확인이 어려운 파일이 있습니다." if risk_level == "HIGH" else "모든 항목이 정상 확인되었습니다."

    return SubmitResponse(
        package_id=package_id,
        risk_level=risk_level,
        verdict=overall_verdict,
        why=why,
        slot_results=slot_results,
        clarifications=clarifications,
        extras=extras,
    )


# ── MAIN ENTRY ────────────────────────────────────────
async def run_submit(req: SubmitRequest) -> SubmitResponse:
    # (1) TRIAGE
    triaged = triage_files(req.files)

    # (2) SLOT APPLY — hint_map 구성
    hint_map: dict[str, str] = {h.file_id: h.slot_name for h in req.slot_hint}

    # (3) EXTRACT — 병렬 실행
    tasks = [
        _extract_and_analyse(
            file=t["file"],
            ext=t["ext"],
            file_type=t["file_type"],
            slot_name=hint_map.get(t["file"].file_id, "unknown"),
            domain=req.domain,
            period_start=req.period_start,
            period_end=req.period_end,
        )
        for t in triaged
    ]
    extractions = list(await asyncio.gather(*tasks))

    # (4) VALIDATE — 슬롯별 그룹핑 후 검증
    from collections import defaultdict

    slot_groups: dict[str, list[dict]] = defaultdict(list)
    for ex in extractions:
        slot_groups[ex["slot_name"]].append(ex)

    slot_results = [_validate_slot(exs, sn) for sn, exs in slot_groups.items()]

    # 누락 슬롯 확인
    slots_mod = get_slots_module(req.domain)
    required = slots_mod.get_required_slot_names()
    provided = {h.slot_name for h in req.slot_hint}
    missing = [s for s in required if s not in provided]

    # (5) CLARIFY
    clarifications = await _generate_clarifications(slot_results)

    # (6) FINAL AGGREGATE
    return await _final_aggregate(
        package_id=req.package_id,
        slot_results=slot_results,
        missing_slots=missing,
        clarifications=clarifications,
    )
