# app/utils/diff.py
from __future__ import annotations

from typing import Any


def esg_issue_key(issue: dict[str, Any]) -> str:
    """
    code + slot 기준으로 “동일 이슈”를 식별하는 키 생성
    - issue 내 slot 키가 slot_name / slotName 등으로 섞일 수 있어 둘 다 대응
    """
    code = str(issue.get("code", "")).strip().upper()

    slot = issue.get("slot_name")
    if slot is None:
        slot = issue.get("slotName")
    slot = str(slot or "").strip()

    return f"{code}::{slot}"


def esg_count_levels(issues: list[dict[str, Any]]) -> tuple[int, int]:
    """issues 리스트에서 FAIL/WARN 개수 카운트"""
    fail = 0
    warn = 0
    for it in issues:
        lv = str(it.get("level", "")).strip().upper()
        if lv == "FAIL":
            fail += 1
        elif lv == "WARN":
            warn += 1
    return fail, warn


def esg_compute_resubmit_diff(prev_result: dict | None, current_result: dict) -> dict:
    """
    A-3 재제출 개선 비교
    - fixed_issues: 이전엔 있었는데 지금은 사라진 이슈
    - new_issues: 이전엔 없었는데 지금 생긴 이슈
    - delta_fail/warn: FAIL/WARN 건수 변화량
    """
    curr_issues = list(current_result.get("issues", []) or [])
    curr_fail, curr_warn = esg_count_levels(curr_issues)

    # 이전 실행이 없으면 비교 불가
    if not prev_result:
        return {
            "has_previous": False,
            "previous_status": None,
            "current_status": current_result.get("status"),
            "previous_counts": {"fail": 0, "warn": 0},
            "current_counts": {"fail": curr_fail, "warn": curr_warn},
            "delta_fail": 0,
            "delta_warn": 0,
            "fixed_issues": [],
            "new_issues": [],
            "note": "",
        }

    prev_issues = list(prev_result.get("issues", []) or [])
    prev_fail, prev_warn = esg_count_levels(prev_issues)

    prev_map = {esg_issue_key(i): i for i in prev_issues}
    curr_map = {esg_issue_key(i): i for i in curr_issues}

    fixed_keys = sorted(list(set(prev_map.keys()) - set(curr_map.keys())))
    new_keys = sorted(list(set(curr_map.keys()) - set(prev_map.keys())))

    # 최소 필드만 반환(필요하면 message/level까지 확장 가능)
    fixed_issues = [
        {
            "code": prev_map[k].get("code"),
            "slot_name": prev_map[k].get("slot_name") or prev_map[k].get("slotName"),
        }
        for k in fixed_keys
    ]
    new_issues = [
        {
            "code": curr_map[k].get("code"),
            "slot_name": curr_map[k].get("slot_name") or curr_map[k].get("slotName"),
        }
        for k in new_keys
    ]

    return {
        "has_previous": True,
        "previous_status": prev_result.get("status"),
        "current_status": current_result.get("status"),
        "previous_counts": {"fail": prev_fail, "warn": prev_warn},
        "current_counts": {"fail": curr_fail, "warn": curr_warn},
        "delta_fail": curr_fail - prev_fail,
        "delta_warn": curr_warn - prev_warn,
        "fixed_issues": fixed_issues,
        "new_issues": new_issues,
        "note": "이전 실행 결과와 비교한 개선/변경 내역입니다.",
    }