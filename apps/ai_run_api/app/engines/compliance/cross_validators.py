# app/engines/compliance/cross_validators.py

"""
Compliance 교차 검증 — 1:1 슬롯 매칭.

cross_validate_slot(extractions_by_slot)
  - 교육 출석부(PDF 스캔) vs 교육일 사진(이미지)
  - 출석부에서 서명 인원수, 사진에서 감지된 인원수를 비교
"""

from __future__ import annotations

import re
from typing import Any


# ── 교차 검증 페어 정의 ──────────────────────────────────
CROSS_PAIRS: list[tuple[str, str]] = [
    ("compliance.education.attendance", "compliance.education.photo"),
]


def _count_attendance_names(extracted: dict) -> int | None:
    """출석부 PDF에서 서명/이름 행 수를 추정."""
    text = extracted.get("text", "") or ""
    if not text.strip():
        return None

    lines = text.strip().split("\n")
    count = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.search(r"[가-힣]{2,4}", line) and re.search(r"(서명|sign|O|✓|v|√|자필|참석)", line, re.IGNORECASE):
            count += 1
    return count if count > 0 else None


def _count_photo_people(extracted: dict) -> int | None:
    """교육사진 Vision 결과에서 인원수를 추출."""
    extras = extracted.get("extras", {}) or {}

    pc = extras.get("person_count")
    if pc is not None:
        try:
            return int(pc)
        except (ValueError, TypeError):
            pass

    obj_str = extras.get("detected_objects", "")
    if obj_str:
        person_mentions = re.findall(r"(?i)(person|사람|인원|people)", obj_str)
        if person_mentions:
            return len(person_mentions)

    scene = extras.get("scene_description", "")
    m = re.search(r"(\d+)\s*(?:명|인|people|persons)", scene, re.IGNORECASE)
    if m:
        return int(m.group(1))

    return None


def cross_validate_slot(
    extractions_by_slot: dict[str, list[dict]],
) -> list[dict[str, Any]]:
    """
    submit.py 4.5단계에서 호출.
    반환: 추가 슬롯결과 리스트 [{slot_name, reasons, verdict, extras}]
    """
    out: list[dict[str, Any]] = []

    for slot_a, slot_b in CROSS_PAIRS:
        exs_a = extractions_by_slot.get(slot_a) or []
        exs_b = extractions_by_slot.get(slot_b) or []

        if not exs_a or not exs_b:
            continue

        ext_a = exs_a[0]
        ext_b = exs_b[0]

        attendance_count = _count_attendance_names(ext_a)
        photo_count = _count_photo_people(ext_b)

        reasons: list[str] = []
        extras: dict[str, Any] = {}

        if attendance_count is None:
            reasons.append("CROSS_ATTENDANCE_PARSE_FAILED")
            extras["detail"] = "출석부에서 인원수를 추출하지 못했습니다."
        elif photo_count is None:
            reasons.append("CROSS_PHOTO_COUNT_FAILED")
            extras["detail"] = "교육사진에서 인원수를 감지하지 못했습니다."
        else:
            extras["attendance_count"] = attendance_count
            extras["photo_count"] = photo_count
            diff = abs(attendance_count - photo_count)
            if attendance_count <= 10:
                tolerance = 2
            else:
                tolerance = max(2, int(attendance_count * 0.2))

            if diff > tolerance:
                reasons.append("CROSS_HEADCOUNT_MISMATCH")
                extras["diff"] = diff
                extras["tolerance"] = tolerance
                extras["detail"] = (
                    f"출석부 {attendance_count}명 vs 사진 {photo_count}명 "
                    f"(차이 {diff}명, 허용 {tolerance}명)"
                )

        verdict = "NEED_FIX" if reasons else "PASS"
        out.append({
            "slot_name": f"{slot_a}__x__{slot_b}",
            "reasons": reasons,
            "verdict": verdict,
            "extras": extras,
        })

    return out