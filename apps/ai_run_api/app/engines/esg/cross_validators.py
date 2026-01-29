# app/engines/esg/cross_validators.py

"""
ESG 교차 검증 — 1:1 슬롯 매칭.

cross_validate_slot(extractions_by_slot)
  - 담당자가 3~4개 로직을 추가 예정
  - 현재는 빈 스켈레톤만 유지
"""

from __future__ import annotations

from typing import Any


def cross_validate_slot(
    extractions_by_slot: dict[str, list[dict]],
) -> list[dict[str, Any]]:
    """
    submit.py 4.5단계에서 호출.
    반환: 추가 슬롯결과 리스트 [{slot_name, reasons, verdict, extras}]

    TODO: 담당자가 아래와 같은 교차 검증 로직 추가 예정
      - 전기 사용량 xlsx vs 전기 고지서 pdf (합계 비교)
      - 가스 사용량 xlsx vs 가스 고지서 pdf (합계 비교)
      - 윤리강령 개정일 vs 서약서 서약일 (선후 관계)
      - 유해물질 목록 vs MSDS 제출 여부 매칭
    """
    return []