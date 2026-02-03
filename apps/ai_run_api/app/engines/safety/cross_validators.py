# app/engines/safety/cross_validators.py

"""
Safety 교차 검증 — 1:1 슬롯 매칭.

cross_validate_slot(slot_a, slot_b, extractions_by_slot)
  - 교육 출석부(PDF 스캔) vs 교육일 사진(이미지)
  - 출석부에서 서명 인원수, 사진에서 감지된 인원수를 비교
"""

from __future__ import annotations

import re
from typing import Any


# ── 교차 검증 페어 정의 ──────────────────────────────────
# (slot_a, slot_b): slot_a=출석부, slot_b=교육사진
CROSS_PAIRS: list[tuple[str, str]] = [
    ("safety.education.attendance", "safety.education.photo"),
]


def _count_attendance_names(extracted: dict) -> int | None:
    """출석부 PDF에서 서명/이름 행 수를 추정.

    전략:
    1) 전체 텍스트에서 한글 이름(2~4자)이 2회 연속 등장하는 패턴을 카운트
       (출석부에서 "이름 → ... → 서명(이름 반복)" 구조)
    2) 폴백: 숫자 번호(1, 2, 3...)로 시작하는 줄 → 행 번호 최대값
    3) 폴백: "N명" 패턴 직접 탐색
    """
    text = extracted.get("text", "") or ""
    if not text.strip():
        return None

    # 전략 1: 한글 이름(2~4자)이 텍스트에서 2회 이상 등장하는 고유 이름 수
    # 출석부는 이름이 "성명" 칸과 "서명" 칸에 2번 나옴
    name_pattern = re.findall(r"[가-힣]{2,4}", text)
    # 헤더 키워드 제외
    _HEADER_WORDS = {
        "안전보건", "교육", "출석부", "교육일자", "교육명", "번호",
        "성명", "부서", "출석", "확인", "서명", "생산", "품질관리",
        "설비기술", "안전관리", "공정기술", "물류", "외주관리",
    }
    filtered = [n for n in name_pattern if n not in _HEADER_WORDS]
    if filtered:
        from collections import Counter
        name_counts = Counter(filtered)
        # 2회 이상 등장한 이름 = 서명란에 이름이 반복된 것
        duplicates = [n for n, c in name_counts.items() if c >= 2]
        if duplicates:
            return len(duplicates)

    # 전략 2: 숫자 번호로 시작하는 줄의 최대값
    lines = text.strip().split("\n")
    max_num = 0
    for line in lines:
        line = line.strip()
        m = re.match(r"^(\d{1,3})$", line)
        if m:
            num = int(m.group(1))
            if 1 <= num <= 500:
                max_num = max(max_num, num)
    if max_num > 0:
        return max_num

    # 전략 3: "N명" 패턴
    m = re.search(r"(\d+)\s*명", text)
    if m:
        return int(m.group(1))

    return None


def _count_photo_people(extracted: dict) -> int | None:
    """교육사진 Vision 결과에서 인원수를 추출.

    extras["detected_objects"]나 extras["person_count"]에서 추출.
    Vision LLM이 "person_count": N 을 반환한다고 가정.
    """
    extras = extracted.get("extras", {}) or {}

    # 1) person_count 직접 반환된 경우
    pc = extras.get("person_count")
    if pc is not None:
        try:
            return int(pc)
        except (ValueError, TypeError):
            pass

    # 2) detected_objects에서 person/사람 카운트
    obj_str = extras.get("detected_objects", "")
    if obj_str:
        person_mentions = re.findall(r"(?i)(person|사람|인원|people)", obj_str)
        if person_mentions:
            return len(person_mentions)

    # 3) Vision scene_description에서 숫자+명 패턴
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

        # 두 슬롯 모두 파일이 있어야 교차 검증
        if not exs_a or not exs_b:
            continue

        ext_a = exs_a[0]  # 출석부
        ext_b = exs_b[0]  # 교육사진

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
            extras["attendance_count"] = str(attendance_count)
            extras["photo_count"] = str(photo_count)
            diff = abs(attendance_count - photo_count)
            # 허용 오차: 소규모(10명 이하)는 2명, 그 이상은 20%
            if attendance_count <= 10:
                tolerance = 2
            else:
                tolerance = max(2, int(attendance_count * 0.2))

            if diff > tolerance:
                reasons.append("CROSS_HEADCOUNT_MISMATCH")
                extras["diff"] = str(diff)
                extras["tolerance"] = str(tolerance)
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