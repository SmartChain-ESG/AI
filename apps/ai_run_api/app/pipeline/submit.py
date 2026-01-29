# app/pipeline/submit.py

"""
Submit 파이프라인 — 6단계 (기획서 §4.2).

(1) TRIAGE — 파일 분류 + 열 수 있는지 체크
(2) SLOT APPLY — slot_hint 적용
(3) EXTRACT — 파싱/OCR
(4) VALIDATE — 룰 검증 → slot_results (verdict + reasons)
(5) CROSS_VALIDATE - 두 파일간 룰 검증
(6) CLARIFY — PASS 아닌 것 → 보완요청 문장 생성
(7) FINAL AGGREGATE — 전체 verdict/risk/why
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
    get_prompt,
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
            raw = await ask_llm(get_prompt(PDF_ANALYSIS, domain), extracted["text"][:4000], heavy=False)
            llm = json.loads(raw)
            for d in llm.get("dates", []):
                if d not in extracted["dates"]:
                    extracted["dates"].append(d)
            if not extracted["signature_detected"] and llm.get("has_signature"):
                extracted["signature_detected"] = True
                extracted["reasons"] = [r for r in extracted["reasons"] if r != "SIGNATURE_MISSING"]
            # anomalies → reason + extras 반영
            anomalies = llm.get("anomalies", [])
            if anomalies:
                extracted.setdefault("reasons", []).append("LLM_ANOMALY_DETECTED")
                extras["anomalies"] = "; ".join(str(a) for a in anomalies)
            if llm.get("summary"):
                extras["summary"] = str(llm["summary"])
            extras.update({k: str(v) for k, v in llm.get("extras", {}).items()})
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
            raw = await ask_llm_vision(get_prompt(IMAGE_VISION, domain), get_prompt(IMAGE_VISION_USER, domain), data, fmt)
            vision = json.loads(raw)
            for d in vision.get("dates", []):
                if d not in extracted["dates"]:
                    extracted["dates"].append(d)
            # violations → reason 반영
            violations = vision.get("violations", [])
            if violations:
                extracted.setdefault("reasons", []).append("VIOLATION_DETECTED")
                extras["violations"] = "; ".join(str(v) for v in violations)
            # person_count → extras
            if vision.get("person_count") is not None:
                extras["person_count"] = str(vision["person_count"])
            # detected_objects → extras
            objects = vision.get("detected_objects", []) or vision.get("safety_objects", [])
            if objects:
                extras["detected_objects"] = ", ".join(str(o) for o in objects)
            # anomalies → reason 반영
            anomalies = vision.get("anomalies", [])
            if anomalies:
                extracted.setdefault("reasons", []).append("LLM_ANOMALY_DETECTED")
                extras["anomalies"] = "; ".join(str(a) for a in anomalies)
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
            raw = await ask_llm(get_prompt(DATA_ANALYSIS, domain), extracted["df_preview"], heavy=False)
            llm = json.loads(raw)
            for d in llm.get("dates", []):
                if d not in extracted["dates"]:
                    extracted["dates"].append(d)
            # missing_fields → reason 반영
            missing = llm.get("missing_fields", [])
            if missing:
                extracted.setdefault("reasons", []).append("LLM_MISSING_FIELDS")
                extras["missing_fields"] = ", ".join(str(f) for f in missing)
            # anomalies → reason 반영
            anomalies = llm.get("anomalies", [])
            if anomalies:
                extracted.setdefault("reasons", []).append("LLM_ANOMALY_DETECTED")
                extras["anomalies"] = "; ".join(str(a) for a in anomalies)
            extras.update({k: str(v) for k, v in llm.get("extras", {}).items()})
        except Exception:
            pass
        result.update(extracted)
        result["extras"] = extras

    # ── 도메인 화이트리스트 필터링 (해당 도메인에 정의된 reason만 유지) ──
    rules_mod = get_rules_module(domain)
    allowed_reasons = set(getattr(rules_mod, "REASON_CODES", {}).keys())
    if allowed_reasons and "reasons" in result:
        result["reasons"] = [r for r in result["reasons"] if r in allowed_reasons]

    # ── 슬롯별 세부 검증 (도메인 validators) ──
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

        # extras에서 구체적 내용 추출
        detail_lines: list[str] = []
        if sr.extras.get("anomalies"):
            detail_lines.append(f"- 이상 징후 상세: {sr.extras['anomalies']}")
        if sr.extras.get("missing_fields"):
            detail_lines.append(f"- 누락 항목: {sr.extras['missing_fields']}")
        if sr.extras.get("violations"):
            detail_lines.append(f"- 위반 사항: {sr.extras['violations']}")
        if sr.extras.get("summary"):
            detail_lines.append(f"- 문서 요약: {sr.extras['summary']}")
        if sr.extras.get("detected_objects"):
            detail_lines.append(f"- 감지된 객체: {sr.extras['detected_objects']}")
        detail_block = "\n".join(detail_lines) if detail_lines else ""

        # REASON_CODES 한국어 매핑 전달
        from app.engines.registry import get_rules_module as _get_rules
        try:
            _rc = getattr(_get_rules(sr.slot_name.split(".")[0]), "REASON_CODES", {})
        except Exception:
            _rc = {}
        rc_text = "\n".join(f"  {k}: {v}" for k, v in _rc.items() if k in sr.reasons)

        try:
            user_msg = (
                f"슬롯: {sr.slot_name}\n"
                f"사유 코드: {reason_text}\n"
                f"REASON_CODES 매핑:\n{rc_text}\n"
                f"파일: {file_text}\n"
            )
            if detail_block:
                user_msg += f"구체적 발견 내용:\n{detail_block}\n"
            user_msg += "위 내용을 바탕으로 한국어로 협력사에게 보낼 보완요청 문장을 작성해주세요. 구체적으로 어떤 항목이 문제인지, 무엇을 수정해야 하는지 명시해주세요."
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
    domain: str,
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
        line = f"[{sr.slot_name}] verdict={sr.verdict}, reasons={sr.reasons}"
        # extras 상세 내용도 판정에 포함
        details = []
        for key in ("anomalies", "violations", "missing_fields", "summary"):
            if sr.extras.get(key):
                details.append(f"{key}: {sr.extras[key]}")
        if details:
            line += f" | details: {'; '.join(details)}"
        summary_lines.append(line)
    judge_input = "\n".join(summary_lines)

    try:
        raw = await ask_llm(get_prompt(JUDGE_FINAL, domain), judge_input, heavy=True)
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

    # (4.5) 도메인별 교차 검증 (슬롯 간 1:1 비교)
    try:
        import importlib
        cross_mod = importlib.import_module(f"app.engines.{req.domain}.cross_validators")
        cross_results = cross_mod.cross_validate_slot(dict(slot_groups))
        for cr in cross_results:
            slot_results.append(SlotResult(
                slot_name=cr["slot_name"],
                verdict=cr.get("verdict", "NEED_FIX"),
                reasons=cr.get("reasons", []),
                file_ids=[],
                file_names=[],
                extras=cr.get("extras", {}),
            ))
    except (ModuleNotFoundError, AttributeError):
        pass
    except Exception:
        pass

    # (5) CLARIFY
    clarifications = await _generate_clarifications(slot_results)

    # (6) FINAL AGGREGATE
    return await _final_aggregate(
        package_id=req.package_id,
        domain=req.domain,
        slot_results=slot_results,
        missing_slots=missing,
        clarifications=clarifications,
    )
