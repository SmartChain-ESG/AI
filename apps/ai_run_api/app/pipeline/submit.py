# app/pipeline/submit.py

"""
Submit ?뚯씠?꾨씪????6?④퀎 (湲고쉷??짠4.2).

(1) TRIAGE ???뚯씪 遺꾨쪟 + ?????덈뒗吏 泥댄겕
(2) SLOT APPLY ??slot_hint ?곸슜
(3) EXTRACT ???뚯떛/OCR
(4) VALIDATE ??猷?寃利???slot_results (verdict + reasons)
(5) CROSS_VALIDATE - ???뚯씪媛?猷?寃利?
(6) CLARIFY ??PASS ?꾨땶 寃???蹂댁셿?붿껌 臾몄옣 ?앹꽦
(7) FINAL AGGREGATE ???꾩껜 verdict/risk/why
"""

from __future__ import annotations

import asyncio
import ast
import json
import re as _re
from datetime import date

from app.engines.registry import get_rules_module, get_slots_module
from app.extractors.ocr.ocr_router import extract_image
from app.extractors.pdf_text import extract_pdf
from app.extractors.xlsx import extract_xlsx
from app.llm.client import ask_llm, ask_llm_vision
from app.llm.prompts import (
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


def _safe_json(raw: str) -> dict:
    """LLM ?묐떟?먯꽌 JSON???덉쟾?섍쾶 ?뚯떛. 留덊겕?ㅼ슫 肄붾뱶釉붾줉 ?쒓굅."""
    text = raw.strip()
    # ```json ... ``` ?먮뒗 ``` ... ``` ?쒓굅
    m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


# ?꾨찓?몃퀎 ?щ’ 寃利??붿뒪?⑥튂
_DOMAIN_VALIDATORS: dict[str, object] = {}


def _get_slot_validator(domain: str):
    """?꾨찓?몃퀎 validators 紐⑤뱢??lazy-load."""
    if domain not in _DOMAIN_VALIDATORS:
        try:
            import importlib
            mod = importlib.import_module(f"app.engines.{domain}.validators")
            _DOMAIN_VALIDATORS[domain] = mod
        except ModuleNotFoundError:
            _DOMAIN_VALIDATORS[domain] = None
    return _DOMAIN_VALIDATORS[domain]


def _get_reason_map(domain: str) -> dict[str, str]:
    try:
        rules_mod = get_rules_module(domain)
        return getattr(rules_mod, "REASON_CODES", {}) or {}
    except Exception:
        return {}


def _reason_descriptions(reason_codes: list[str], domain: str) -> list[str]:
    reason_map = _get_reason_map(domain)
    fallback = {
        "E_MSDS_MISSING_REQUIRED": "유해물질 목록 대비 필수 MSDS 누락",
        "E_MSDS_MISSING_OPTIONAL": "유해물질 목록 대비 선택 MSDS 누락",
        "E_WASTE_EVIDENCE_MISSING": "폐기물 처리 목록 대비 증빙 문서 누락",
        "E_WASTE_EVIDENCE_FIELDS_WEAK": "폐기물 처리 증빙의 필수 항목 부족",
        "E_WASTE_NAME_MISMATCH": "폐기물 목록과 증빙 문서의 물질명이 불일치",
        "BASELINE_2024_MISSING": "전년도 기준 데이터가 없어 피크 비교 불가",
        "BASELINE_INVALID": "전년도 기준 데이터 품질 부족",
        "E_PEAK_SPIKE_WARN": "전년 대비 사용량 피크 급증/급감(주의)",
        "E_PEAK_SPIKE_FAIL": "전년 대비 사용량 피크 급증/급감(위험)",
        "E3_BILL_FIELDS_MISSING": "고지서에서 월 사용량/기간 정보를 추출하지 못함",
        "E1_UNIT_MISSING": "사용량 단위 정보 누락",
        "E2_SPIKE_WARN": "최근 사용량 급증/급감(주의)",
        "E2_SPIKE_FAIL": "최근 사용량 급증/급감(위험)",
        "G_IMAGE_BLURRY": "이미지가 흐려 판독 신뢰도가 낮음",
        "CROSS_HEADCOUNT_MISMATCH": "출석 인원과 사진 인원이 불일치",
        "CROSS_ATTENDANCE_PARSE_FAILED": "출석부 인원 파싱 실패",
        "CROSS_PHOTO_COUNT_FAILED": "사진 인원 감지 실패",
    }
    out: list[str] = []
    seen: set[str] = set()
    for code in reason_codes:
        desc = str(reason_map.get(code) or fallback.get(code) or code).strip()
        if desc and desc not in seen:
            seen.add(desc)
            out.append(desc)
    return out


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    raw = str(value).strip()
    if not raw:
        return []
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(raw)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
        except Exception:
            pass
    chunks = _re.split(r"[|,/;]", raw)
    return [c.strip() for c in chunks if c.strip()]


def _to_ko_text(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    # Lightweight normalizer for mixed EN/KR model outputs.
    months = {
        "January": "1월",
        "February": "2월",
        "March": "3월",
        "April": "4월",
        "May": "5월",
        "June": "6월",
        "July": "7월",
        "August": "8월",
        "September": "9월",
        "October": "10월",
        "November": "11월",
        "December": "12월",
    }
    for en, ko in months.items():
        s = s.replace(en, ko)
    replacements = {
        "Gas bill": "도시가스 요금 고지서",
        "Water bill": "수도 요금 고지서",
        "Electricity bill": "전기 요금 고지서",
        "usage": "사용량",
        "document": "문서",
        "details": "상세",
        "summary": "요약",
        "Missing supplier information": "공급업체 정보 누락",
        "No data on exposure limits": "노출 기준 정보 누락",
        "No data on health hazards": "건강 유해성 정보 누락",
        "for SG BEND": "성광벤드 기준",
        "by SG BEND": "성광벤드 기준",
    }
    for en, ko in replacements.items():
        s = s.replace(en, ko)
    s = s.replace("SG BEND", "성광벤드")
    s = _re.sub(r"\bfor\s+(HZ-\d+(?:,\s*HZ-\d+)*)", r"(대상: \1)", s)
    s = s.replace(" for ", " ")
    s = s.replace(" by ", " ")
    s = s.replace("; ", " / ")
    s = s.replace("..", ".")
    return s
def _extract_hz_ids(text: str) -> list[str]:
    ids = _re.findall(r"HZ-\d+", str(text or ""))
    out: list[str] = []
    for i in ids:
        if i not in out:
            out.append(i)
    return out


def _service_issue_points(
    slot_name: str,
    reasons: list[str],
    extras: dict[str, str],
    domain: str,
    period_start: date,
    period_end: date,
) -> list[str]:
    points: list[str] = []
    reason_set = set(reasons)
    anomalies = _to_ko_text(extras.get("anomalies", ""))
    missing_fields = _to_ko_text(extras.get("missing_fields", ""))
    summary = _to_ko_text(extras.get("summary", ""))
    violations = _to_ko_text(extras.get("violations", ""))
    detail = _to_ko_text(extras.get("detail", ""))
    missing_required = _as_list(extras.get("missing_required"))
    missing_optional = _as_list(extras.get("missing_optional"))
    missing_names = _as_list(extras.get("missing_names"))

    if "HEADER_MISMATCH" in reason_set:
        points.append("필수 헤더(컬럼명)가 템플릿과 일치하지 않습니다.")
        points.append("표준 양식 컬럼명으로 수정 후 다시 제출해 주세요.")
    if "DATE_MISMATCH" in reason_set:
        points.append(f"문서 내 날짜가 제출기간({period_start} ~ {period_end})과 일치하지 않습니다.")
    if "OCR_FAILED" in reason_set or "G_OCR_UNREADABLE" in reason_set:
        points.append("문서 판독(OCR) 품질이 낮아 자동 검증이 어렵습니다. 더 선명한 원본 파일이 필요합니다.")
    if "G_IMAGE_BLURRY" in reason_set:
        points.append("이미지 초점이 흐려 텍스트/객체 판독 신뢰도가 낮습니다. 원본 또는 고해상도 파일이 필요합니다.")
    if "LLM_MISSING_FIELDS" in reason_set and missing_fields:
        points.append(f"필수 항목 누락: {missing_fields}")

    if "LLM_ANOMALY_DETECTED" in reason_set:
        hz_ids = _extract_hz_ids(anomalies)
        if slot_name == "esg.hazmat.inventory" and hz_ids:
            points.append(
                f"유해물질 목록에는 {', '.join(hz_ids)} 항목이 있으나, 해당 항목과 매칭되는 MSDS 파일이 없습니다."
            )
        elif (
            ("confirm" in anomalies.lower() and "headcount" in anomalies.lower())
            or ("확인완료" in anomalies and "대상인원" in anomalies)
            or ("합계" in anomalies and "일치하지" in anomalies)
        ):
            points.append("배포로그 인원 집계가 맞지 않습니다(확인완료 + 미확인 != 대상 인원).")
        elif anomalies:
            points.append(f"AI 감지 특이사항: {anomalies}")

    if "VIOLATION_DETECTED" in reason_set and violations:
        points.append(f"규정 위반 의심사항: {violations}")
    if "E3_BILL_MISMATCH" in reason_set:
        diff_pct = str(extras.get("diff_pct", "")).strip()
        tol_pct = str(extras.get("tol_pct", "")).strip()
        xlsx_total = str(extras.get("xlsx_total", "")).strip()
        bill_total = str(extras.get("bill_total", "")).strip()
        if diff_pct and tol_pct:
            points.append(
                f"사용량 집계와 고지서 합계가 불일치합니다(편차 {diff_pct}%, 허용 {tol_pct}%)."
            )
        else:
            points.append("사용량 합계와 고지서 합계가 일치하지 않습니다. 원본 값 대조가 필요합니다.")
        if xlsx_total and bill_total:
            points.append(f"집계값 {xlsx_total}, 고지서값 {bill_total}로 확인되었습니다.")

    if "E3_BILL_FIELDS_MISSING" in reason_set:
        points.append("고지서에서 월 사용량 또는 기간 필드를 읽지 못해 월별 대사가 불가능합니다.")

    if "E_MSDS_MISSING_REQUIRED" in reason_set and missing_required:
        points.append(
            f"유해물질 목록에는 {', '.join(missing_required)}가 있으나, 해당 물질에 대응하는 MSDS 파일이 없습니다."
        )
    if "E_MSDS_MISSING_OPTIONAL" in reason_set and missing_optional:
        points.append(f"권장 MSDS 확인 대상: {', '.join(missing_optional)}")

    if "E_WASTE_EVIDENCE_MISSING" in reason_set:
        points.append("폐기물 처리 목록은 있으나 이에 대응하는 처리 증빙 문서가 제출되지 않았습니다.")
    if "E_WASTE_NAME_MISMATCH" in reason_set and missing_names:
        points.append(f"폐기물 목록과 증빙 문서의 물질명이 불일치합니다: {', '.join(missing_names)}")

    if "BASELINE_2024_MISSING" in reason_set:
        points.append("전년도 기준 파일이 없어 2024 대비 2025 피크 비교를 수행할 수 없습니다.")
    if "E_PEAK_SPIKE_WARN" in reason_set or "E_PEAK_SPIKE_FAIL" in reason_set:
        ratio = str(extras.get("ratio", "")).strip()
        if ratio:
            points.append(f"전년 대비 사용량 피크 비율이 {ratio}배로 급변했습니다.")
        else:
            points.append("전년 대비 사용량 피크가 급변했습니다.")

    if "CROSS_HEADCOUNT_MISMATCH" in reason_set and detail:
        points.append(f"출석/사진 인원 불일치: {detail}")
    if "CROSS_ATTENDANCE_PARSE_FAILED" in reason_set:
        points.append("출석부 문서에서 인원수를 추출하지 못했습니다.")
    if "CROSS_PHOTO_COUNT_FAILED" in reason_set:
        points.append("사진/이미지에서 인원수를 안정적으로 감지하지 못했습니다.")

    if detail and detail not in points:
        points.append(f"검증 근거: {detail}")

    if not points:
        reason_desc = _reason_descriptions(reasons, domain)
        if reason_desc:
            points.append(f"확인 필요 사유: {', '.join(reason_desc)}")
        else:
            points.append("세부 사유 정보가 부족합니다. 원문 문서와 Raw Response를 함께 확인해 주세요.")

    if summary:
        points.append(f"문서 요약: {summary}")

    out: list[str] = []
    seen: set[str] = set()
    for p in points:
        p = p.strip()
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out[:4]


def _service_pass_points(slot_name: str, extras: dict[str, str]) -> list[str]:
    points: list[str] = []
    summary = _to_ko_text(extras.get("summary", ""))
    objects = _to_ko_text(extras.get("detected_objects", ""))
    person_count = str(extras.get("person_count", "")).strip()
    yolo_count = str(extras.get("person_count_yolo", "")).strip()
    llm_count = str(extras.get("person_count_llm", "")).strip()
    attendance_count = str(extras.get("attendance_count", "")).strip()
    photo_count = str(extras.get("photo_count", "")).strip()
    diff = str(extras.get("diff", "")).strip()
    tolerance = str(extras.get("tolerance", "")).strip()

    if attendance_count and photo_count:
        msg = f"출석부 인원 {attendance_count}명, 이미지 탐지 인원 {photo_count}명"
        if diff:
            msg += f", 차이 {diff}명"
        if tolerance:
            msg += f" (허용오차 {tolerance})"
        msg += "으로 PASS 기준을 충족했습니다."
        points.append(msg)
    elif person_count and slot_name.endswith(".image"):
        points.append(f"이미지에서 사람 {person_count}명을 탐지했으며, 검증 기준상 특이사항이 없어 PASS 처리되었습니다.")

    if yolo_count:
        if llm_count:
            points.append(f"인원 감지 결과(객체탐지/비전): {yolo_count}명 / {llm_count}명")
        else:
            points.append(f"인원 감지 결과(객체탐지): {yolo_count}명")

    if objects and slot_name.endswith(".image"):
        points.append(f"감지 객체: {objects}")
    if summary:
        points.append(f"문서 요약: {summary}")
    if not points:
        points.append("규칙 검증과 AI 점검에서 위반/이상 징후가 없어 PASS 처리되었습니다.")

    out: list[str] = []
    seen: set[str] = set()
    for p in points:
        p = p.strip()
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out[:3]


def _slot_analysis_message(
    sr: SlotResult,
    domain: str,
    period_start: date,
    period_end: date,
) -> tuple[str, list[str]]:
    if sr.verdict == "PASS":
        points = _service_pass_points(sr.slot_name, sr.extras)
        return f"적합 판정입니다. {' '.join(points)}", points

    points = _service_issue_points(
        slot_name=sr.slot_name,
        reasons=sr.reasons,
        extras=sr.extras,
        domain=domain,
        period_start=period_start,
        period_end=period_end,
    )
    if sr.verdict == "NEED_FIX":
        return f"수정/재제출이 필요합니다. {' '.join(points)}", points
    return f"추가 확인이 필요합니다. {' '.join(points)}", points


def _build_file_summary_why(
    slot_results: list[SlotResult],
    domain: str,
    period_start: date,
    period_end: date,
) -> str:
    lines: list[str] = []
    for sr in slot_results:
        _, points = _slot_analysis_message(sr, domain, period_start, period_end)
        primary = _to_ko_text(points[0]) if points else "세부 사유가 부족합니다."
        files = sr.file_names or [sr.display_name or sr.slot_name]
        for f in files:
            lines.append(f"[{f}]: {primary}")
    return "\n".join(lines)


def _build_llm_user_payload(
    slot_name: str,
    file_name: str,
    period_start: date,
    period_end: date,
    content_key: str,
    content: str,
) -> str:
    payload = {
        "slot_name": slot_name,
        "file_name": file_name,
        "period_start": str(period_start),
        "period_end": str(period_end),
        content_key: content,
    }
    return json.dumps(payload, ensure_ascii=False)


def _flatten_extra_value(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return " / ".join(str(x).strip() for x in v if str(x).strip())
    if isinstance(v, dict):
        parts = [f"{k}={vv}" for k, vv in v.items()]
        return ", ".join(parts)
    return str(v).strip()
async def _extract_and_analyse(
    file: FileRef,
    ext: str,
    file_type: str,
    slot_name: str,
    domain: str,
    period_start: date,
    period_end: date,
) -> dict:
    """?뚯씪 1媛쒕? ?ㅼ슫濡쒕뱶 ??異붿텧 ??LLM 蹂닿컯. Returns raw extraction dict."""
    data = await download_file(file.storage_uri)
    fname = file.file_name or file.storage_uri.rsplit("/", 1)[-1]

    result: dict = {"file_id": file.file_id, "file_name": fname, "slot_name": slot_name}

    if file_type == "pdf":
        extracted = await extract_pdf(data, period_start, period_end)
        # LLM 蹂닿컯 (GPT-4o-mini)
        extras: dict[str, str] = {}
        try:
            raw = await ask_llm(
                get_prompt(PDF_ANALYSIS, domain),
                _build_llm_user_payload(
                    slot_name=slot_name,
                    file_name=fname,
                    period_start=period_start,
                    period_end=period_end,
                    content_key="document_text",
                    content=extracted["text"][:4000],
                ),
                heavy=False,
            )
            llm = _safe_json(raw)
            for d in llm.get("dates", []):
                if d not in extracted["dates"]:
                    extracted["dates"].append(d)
            if not extracted["signature_detected"] and llm.get("has_signature"):
                extracted["signature_detected"] = True
                extracted["reasons"] = [r for r in extracted["reasons"] if r != "SIGNATURE_MISSING"]
            # anomalies ??reason + extras 諛섏쁺
            anomalies = _as_list(llm.get("anomalies", []))
            if anomalies:
                extracted.setdefault("reasons", []).append("LLM_ANOMALY_DETECTED")
                extras["anomalies"] = " / ".join(str(a) for a in anomalies)
            if llm.get("summary"):
                extras["summary"] = str(llm["summary"]).strip()
            extras.update({k: _flatten_extra_value(v) for k, v in (llm.get("extras", {}) or {}).items()})
        except Exception:
            pass
        result.update(extracted)
        result["extras"] = extras

    elif file_type == "image":
        fmt = "jpg" if ext in (".jpg", ".jpeg") else "png"
        extracted = await extract_image(data, fmt, period_start, period_end)
        # GPT-4o Vision 蹂닿컯
        extras = {}
        try:
            vision_user = (
                f"{get_prompt(IMAGE_VISION_USER, domain)}\n"
                f"slot_name: {slot_name}\n"
                f"file_name: {fname}\n"
                f"period_start: {period_start}\n"
                f"period_end: {period_end}\n"
            )
            raw = await ask_llm_vision(get_prompt(IMAGE_VISION, domain), vision_user, data, fmt)
            vision = _safe_json(raw)
            for d in vision.get("dates", []):
                if d not in extracted["dates"]:
                    extracted["dates"].append(d)
            # violations ??reason 諛섏쁺
            violations = _as_list(vision.get("violations", []))
            if violations:
                extracted.setdefault("reasons", []).append("VIOLATION_DETECTED")
                extras["violations"] = " / ".join(str(v) for v in violations)
            # person_count ??extras
            if vision.get("person_count") is not None:
                extras["person_count_llm"] = str(vision["person_count"])
                extras["person_count"] = str(vision["person_count"])
            # detected_objects ??extras
            objects = _as_list(vision.get("detected_objects", []) or vision.get("safety_objects", []))
            if objects:
                extras["detected_objects"] = ", ".join(str(o) for o in objects)
            # anomalies ??reason 諛섏쁺
            anomalies = _as_list(vision.get("anomalies", []))
            if anomalies:
                extracted.setdefault("reasons", []).append("LLM_ANOMALY_DETECTED")
                extras["anomalies"] = " / ".join(str(a) for a in anomalies)
            if vision.get("scene_description"):
                extras["scene_description"] = vision["scene_description"]
            extras.update({k: _flatten_extra_value(v) for k, v in (vision.get("extras", {}) or {}).items()})
        except Exception:
            pass
        # ?? YOLO person count (LLM 媛???뼱?곌린, ?ㅽ뙣 ??LLM ?대갚) ??
        try:
            from app.extractors.yolo.person_counter import count_persons
            yolo_count = count_persons(data)
            extras["person_count_yolo"] = str(yolo_count)
            extras["person_count"] = str(yolo_count)
            if extras.get("person_count_llm"):
                try:
                    gap = abs(int(extras["person_count_llm"]) - int(yolo_count))
                    extras["person_count_gap"] = str(gap)
                except Exception:
                    pass
        except Exception:
            pass
        result.update(extracted)
        result["extras"] = extras

    elif file_type == "xlsx":
        rules_mod = get_rules_module(domain)
        expected = rules_mod.EXPECTED_HEADERS.get(slot_name, [])
        extracted = await extract_xlsx(data, ext, expected, period_start, period_end)
        # LLM 蹂닿컯 (GPT-4o-mini)
        extras = {}
        try:
            raw = await ask_llm(
                get_prompt(DATA_ANALYSIS, domain),
                _build_llm_user_payload(
                    slot_name=slot_name,
                    file_name=fname,
                    period_start=period_start,
                    period_end=period_end,
                    content_key="table_preview",
                    content=extracted["df_preview"][:5000],
                ),
                heavy=False,
            )
            llm = _safe_json(raw)
            for d in llm.get("dates", []):
                if d not in extracted["dates"]:
                    extracted["dates"].append(d)
            # missing_fields ??reason 諛섏쁺
            missing = _as_list(llm.get("missing_fields", []))
            if missing:
                extracted.setdefault("reasons", []).append("LLM_MISSING_FIELDS")
                extras["missing_fields"] = ", ".join(str(f) for f in missing)
            # anomalies ??reason 諛섏쁺
            anomalies = _as_list(llm.get("anomalies", []))
            if anomalies:
                extracted.setdefault("reasons", []).append("LLM_ANOMALY_DETECTED")
                extras["anomalies"] = " / ".join(str(a) for a in anomalies)
            extras.update({k: _flatten_extra_value(v) for k, v in (llm.get("extras", {}) or {}).items()})
        except Exception:
            pass
        result.update(extracted)
        result["extras"] = extras

    # ?? ?꾨찓???붿씠?몃━?ㅽ듃 ?꾪꽣留?(?대떦 ?꾨찓?몄뿉 ?뺤쓽??reason留??좎?) ??
    rules_mod = get_rules_module(domain)
    allowed_reasons = set(getattr(rules_mod, "REASON_CODES", {}).keys())
    if allowed_reasons and "reasons" in result:
        result["reasons"] = [r for r in result["reasons"] if r in allowed_reasons]

    # ?? ?щ’蹂??몃? 寃利?(?꾨찓??validators) ??
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


# ?? (4) VALIDATE ???????????????????????????????????????
def _validate_slot(extractions: list[dict], slot_name: str, domain: str) -> SlotResult:
    """?щ’??留ㅽ븨??紐⑤뱺 ?뚯씪??異붿텧 寃곌낵瑜?醫낇빀?섏뿬 verdict瑜?寃곗젙."""
    all_reasons: list[str] = []
    file_ids: list[str] = []
    file_names: list[str] = []
    extras: dict[str, str] = {}

    for ex in extractions:
        file_ids.append(ex["file_id"])
        file_names.append(ex.get("file_name", ""))
        all_reasons.extend(ex.get("reasons", []))
        extras.update(ex.get("extras", {}))

    # reason 以묐났 ?쒓굅
    reasons = list(dict.fromkeys(all_reasons))

    # verdict 寃곗젙 ??湲고쉷??짠1 湲곗?
    # A. NEED_FIX: ?뚯씪 ?먯껜 臾몄젣 ??遺꾩꽍 遺덇?, ?ъ젣異??꾩슂
    _NEED_FIX_REASONS = {
        "MISSING_SLOT", "PARSE_FAILED", "HEADER_MISMATCH",
        "EMPTY_TABLE", "OCR_FAILED", "G_OCR_UNREADABLE", "G_IMAGE_BLURRY",
        "E3_BILL_FIELDS_MISSING",
        "E_MSDS_MISSING_REQUIRED",
        "E_WASTE_EVIDENCE_MISSING", "E_WASTE_EVIDENCE_FIELDS_WEAK", "E_WASTE_LIST_PARSE_FAILED",
    }
    # B. NEED_CLARIFY: ?댁슜 臾몄젣 ??遺꾩꽍? ?먯쑝???댁뒋 諛쒓껄, ?뚮챸 ?꾩슂
    _NEED_CLARIFY_REASONS = {
        "VIOLATION_DETECTED", "LOW_EDUCATION_RATE", "SIGNATURE_MISSING",
        "E2_SPIKE_DETECTED", "E2_SPIKE_WARN", "E2_SPIKE_FAIL",
        "E3_BILL_MISMATCH", "LLM_ANOMALY_DETECTED", "LLM_MISSING_FIELDS", "DATE_MISMATCH",
        "E_MSDS_MISSING_OPTIONAL", "E_WASTE_NAME_MISMATCH",
        "BASELINE_2024_MISSING", "BASELINE_INVALID", "E_PEAK_SPIKE_WARN", "E_PEAK_SPIKE_FAIL",
    }

    if any(r in _NEED_FIX_REASONS for r in reasons):
        verdict = "NEED_FIX"
    elif any(r in _NEED_CLARIFY_REASONS for r in reasons):
        verdict = "NEED_CLARIFY"
    elif reasons:
        # 湲고? reason? ?댁슜 臾몄젣濡?媛꾩＜
        verdict = "NEED_CLARIFY"
    else:
        verdict = "PASS"

    # display_name 議고쉶
    slots_mod = get_slots_module(domain)
    display_name_map = {s.name: s.display_name for s in slots_mod.SLOTS}
    display_name = display_name_map.get(slot_name, "")

    return SlotResult(
        slot_name=slot_name,
        display_name=display_name,
        verdict=verdict,
        reasons=reasons,
        file_ids=file_ids,
        file_names=file_names,
        extras=extras,
    )


# ?? (5) CLARIFY ???????????????????????????????????????
async def _generate_clarifications(
    slot_results: list[SlotResult],
    domain: str,
    period_start: date,
    period_end: date,
) -> list[Clarification]:
    """슬롯별 사용자 전달 문구 생성 (PASS 포함)."""
    clarifications: list[Clarification] = []
    for sr in slot_results:
        message, points = _slot_analysis_message(sr, domain, period_start, period_end)

        sr.extras["analysis_message"] = message
        sr.extras["analysis_detail"] = " / ".join(points)
        reason_desc = _reason_descriptions(sr.reasons, domain)
        sr.extras["reason_descriptions"] = ", ".join(reason_desc) if reason_desc else "특이사항 없음"
        if sr.verdict == "PASS":
            sr.extras["success_points"] = " | ".join(points)
        else:
            sr.extras["issue_points"] = " | ".join(points)

        clarifications.append(
            Clarification(
                slot_name=sr.slot_name,
                message=message,
                file_ids=sr.file_ids,
            )
        )
    return clarifications


async def _final_aggregate(
    package_id: str,
    domain: str,
    slot_results: list[SlotResult],
    missing_slots: list[str],
    clarifications: list[Clarification],
    period_start: date,
    period_end: date,
) -> SubmitResponse:
    """전체 verdict/risk 계산 + 서비스형 why 생성."""
    slots_mod = get_slots_module(domain)
    display_name_map = {s.name: s.display_name for s in slots_mod.SLOTS}

    for s in missing_slots:
        sr = SlotResult(
            slot_name=s,
            display_name=display_name_map.get(s, ""),
            verdict="NEED_FIX",
            reasons=["MISSING_SLOT"],
            file_ids=[],
            file_names=[],
            extras={},
        )
        message, points = _slot_analysis_message(sr, domain, period_start, period_end)
        sr.extras["analysis_message"] = message
        sr.extras["analysis_detail"] = " / ".join(points)
        sr.extras["reason_descriptions"] = ", ".join(_reason_descriptions(sr.reasons, domain))
        sr.extras["issue_points"] = " | ".join(points)
        slot_results.append(sr)
        clarifications.append(
            Clarification(
                slot_name=sr.slot_name,
                message=message,
                file_ids=[],
            )
        )

    verdicts = [sr.verdict for sr in slot_results]
    if "NEED_FIX" in verdicts:
        overall_verdict = "NEED_FIX"
        risk_level = "HIGH"
    elif "NEED_CLARIFY" in verdicts:
        overall_verdict = "NEED_CLARIFY"
        risk_level = "MEDIUM"
    else:
        overall_verdict = "PASS"
        risk_level = "LOW"

    why = _build_file_summary_why(slot_results, domain, period_start, period_end)

    extras: dict[str, str] = {}
    summary_lines = []
    for sr in slot_results:
        line = f"[{sr.slot_name}] verdict={sr.verdict}, reasons={sr.reasons}"
        details = []
        for key in ("anomalies", "violations", "missing_fields", "summary", "analysis_detail"):
            if sr.extras.get(key):
                details.append(f"{key}: {sr.extras[key]}")
        if details:
            line += f" | details: {'; '.join(details)}"
        summary_lines.append(line)
    judge_input = "\n".join(summary_lines)

    try:
        raw = await ask_llm(get_prompt(JUDGE_FINAL, domain), judge_input, heavy=True)
        llm_result = _safe_json(raw)
        extras = {k: _to_ko_text(str(v)) for k, v in llm_result.get("extras", {}).items()}
        if llm_result.get("why"):
            extras["ai_overall_comment"] = _to_ko_text(str(llm_result.get("why")))
    except Exception:
        pass

    extras.setdefault("service_why", why)

    return SubmitResponse(
        package_id=package_id,
        risk_level=risk_level,
        verdict=overall_verdict,
        why=why,
        slot_results=slot_results,
        clarifications=clarifications,
        extras=extras,
    )
async def run_submit(req: SubmitRequest) -> SubmitResponse:
    # (1) TRIAGE
    triaged = triage_files(req.files)

    # (2) SLOT APPLY ??hint_map 援ъ꽦
    hint_map: dict[str, str] = {h.file_id: h.slot_name for h in req.slot_hint}

    # (3) EXTRACT ??蹂묐젹 ?ㅽ뻾
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

    # (4) VALIDATE ???щ’蹂?洹몃９????寃利?
    from collections import defaultdict

    slot_groups: dict[str, list[dict]] = defaultdict(list)
    for ex in extractions:
        slot_groups[ex["slot_name"]].append(ex)

    slot_results = [_validate_slot(exs, sn, req.domain) for sn, exs in slot_groups.items()]

    # ?꾨씫 ?щ’ ?뺤씤
    slots_mod = get_slots_module(req.domain)
    required = slots_mod.get_required_slot_names()
    provided = {h.slot_name for h in req.slot_hint}
    missing = [s for s in required if s not in provided]

    # (4.5) ?꾨찓?몃퀎 援먯감 寃利?(?щ’ 媛?1:1 鍮꾧탳)
    # display_name 議고쉶??留ㅽ븨
    display_name_map = {s.name: s.display_name for s in slots_mod.SLOTS}
    try:
        import importlib
        cross_mod = importlib.import_module(f"app.engines.{req.domain}.cross_validators")
        cross_results: list[dict] = []
        if hasattr(cross_mod, "cross_validate_slot"):
            fn = cross_mod.cross_validate_slot
            try:
                cross_results = fn(dict(slot_groups), req.period_start, req.period_end)
            except TypeError:
                cross_results = fn(dict(slot_groups))
        elif hasattr(cross_mod, "esg_cross_checks"):
            cross_results = cross_mod.esg_cross_checks(dict(slot_groups), req.period_start, req.period_end)
        _CV_VERDICT_MAP = {
            "FAIL": "NEED_FIX",
            "WARN": "NEED_CLARIFY",
            "PASS": "PASS",
            "NEED_FIX": "NEED_FIX",
            "NEED_CLARIFY": "NEED_CLARIFY",
        }
        for cr in cross_results:
            raw_v = cr.get("verdict", "NEED_FIX")
            mapped_v = _CV_VERDICT_MAP.get(raw_v, raw_v)
            cr_extras = {k: _flatten_extra_value(v) for k, v in (cr.get("extras", {}) or {}).items()}
            slot_results.append(SlotResult(
                slot_name=cr["slot_name"],
                display_name=display_name_map.get(cr["slot_name"], ""),
                verdict=mapped_v,
                reasons=cr.get("reasons", []),
                file_ids=[],
                file_names=[],
                extras=cr_extras,
            ))
    except (ModuleNotFoundError, AttributeError):
        pass
    except Exception:
        pass

    # (5) CLARIFY
    clarifications = await _generate_clarifications(
        slot_results=slot_results,
        domain=req.domain,
        period_start=req.period_start,
        period_end=req.period_end,
    )

    # (6) FINAL AGGREGATE
    return await _final_aggregate(
        package_id=req.package_id,
        domain=req.domain,
        slot_results=slot_results,
        missing_slots=missing,
        clarifications=clarifications,
        period_start=req.period_start,
        period_end=req.period_end,
    )