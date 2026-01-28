"""Compliance 도메인 — 실제 검증 로직 구현체.

데이터를 분석하여 위반 사항 코드(list[str])를 반환한다.
validate_slot 함수가 외부 진입점 역할을 한다.
"""

from __future__ import annotations

import io

import pandas as pd

# ---------------------------------------------------------
# 내부 상수 정의 (검증 기준값)
# ---------------------------------------------------------
_MANDATORY_CLAUSES = ["선급금", "지연이자", "목적물", "기성금"]  # [Source: 142]
_REQUIRED_COURSES = ["개인정보", "성희롱", "장애인", "산업안전"]
_EDU_FAIL_LIMIT = 20.0  # 미이수 허용치(%)


# ---------------------------------------------------------
# 내부 검증 함수 (Private Functions)
# ---------------------------------------------------------

def _validate_contract_text(text: str) -> list[str]:
    """표준 근로/하도급 계약서 텍스트 검증"""
    reasons = []
    
    # (1) 필수 조항 키워드 체크
    missing = [kw for kw in _MANDATORY_CLAUSES if kw not in text]
    if missing:
        reasons.append("KEYWORD_MISSING")

    # (2) 연도 체크
    if "2025" not in text:
        reasons.append("WRONG_YEAR")
        
    return reasons


def _validate_privacy_education(extracted: dict, file_type: str) -> list[str]:
    """개인정보 교육 이수율 검증 (Excel/PDF 공용 로직)"""
    reasons = []
    total_cnt = 0
    fail_cnt = 0

    # Case A: Excel (df_preview 사용)
    if file_type in ["xlsx", "xls", "csv"]:
        try:
            csv_data = extracted.get("df_preview", "")
            if csv_data:
                df = pd.read_csv(io.StringIO(csv_data))
                if df.empty: return ["EMPTY_TABLE"]

                status_cols = [c for c in df.columns if "이수" in str(c) or "여부" in str(c)]
                if status_cols:
                    col = status_cols[0]
                    total_cnt = len(df)
                    fail_cnt = df[col].astype(str).str.upper().apply(
                        lambda x: 1 if "N" in x or "미이수" in x else 0
                    ).sum()
        except Exception:
            pass

    # Case B: PDF (텍스트 기반 키워드 검색)
    elif file_type == "pdf":
        text = extracted.get("text", "")
        if text:
            for line in text.split("\n"):
                line_upper = line.strip().upper()
                if not line_upper:
                    continue
                if "이수" in line or "미이수" in line:
                    total_cnt += 1
                    if "미이수" in line or "N" in line_upper.split()[-1:]:
                        fail_cnt += 1

    if total_cnt == 0:
        return ["DATA_NOT_FOUND"]

    # 이수율 판정
    fail_rate = (fail_cnt / total_cnt) * 100
    if fail_rate > _EDU_FAIL_LIMIT:
        reasons.append("LOW_EDUCATION_RATE")

    return reasons


def _validate_fair_trade_checklist(extracted: dict) -> list[str]:
    """공정거래 점검표 검증 (xlsx df_preview 또는 PDF 텍스트 기반)."""
    reasons = []
    csv_data = extracted.get("df_preview", "")
    if csv_data:
        try:
            df = pd.read_csv(io.StringIO(csv_data))
            if df.empty:
                return reasons
            # 위험요소/조치완료 컬럼 탐색
            risk_cols = [c for c in df.columns if "위험" in str(c)]
            action_cols = [c for c in df.columns if "조치" in str(c) and "완료" in str(c)]
            if risk_cols and action_cols:
                for _, row in df.iterrows():
                    risk_val = str(row[risk_cols[0]]).strip().upper()
                    action_val = str(row[action_cols[0]]).strip().upper()
                    if "Y" in risk_val and "N" in action_val:
                        reasons.append("HIGH_RISK_DETECTED")
                        break
        except Exception:
            pass
    return reasons


def _validate_education_plan_text(text: str) -> list[str]:
    """교육 계획서 텍스트 검증"""
    reasons = []
    missing_cnt = 0
    
    for course in _REQUIRED_COURSES:
        if course not in text:
            missing_cnt += 1
            
    if missing_cnt >= 2:
        reasons.append("MISSING_MANDATORY_TRAINING")
        
    return reasons


# ---------------------------------------------------------
# 공개 디스패치 함수 (Public Entry Point)
# ---------------------------------------------------------

def validate_slot(
    slot_name: str,
    file_type: str,
    extracted: dict,
) -> list[str]:
    """
    슬롯명과 파일타입을 보고 내부 검증 함수(_validate_*)를 호출합니다.
    Return: 검증 실패 사유 코드 리스트 (list[str])
    """
    extra_reasons: list[str] = []

    # 텍스트 전처리 (리스트 -> 문자열)
    text = extracted.get("text", "")
    if isinstance(text, list): 
        text = "\n".join(text)

    # ── 1. 표준 근로/하도급 계약서 ──
    if slot_name == "compliance.contract.sample":
        extra_reasons = _validate_contract_text(text)

    # ── 2. 개인정보 교육 이수 현황 ──
    elif slot_name == "compliance.education.privacy":
        extra_reasons = _validate_privacy_education(extracted, file_type)

    # ── 3. 공정거래 자율 점검표 ──
    elif slot_name == "compliance.fair.trade":
        extra_reasons = _validate_fair_trade_checklist(extracted)

    # ── 4. 법정의무 교육 계획서 ──
    elif slot_name == "compliance.education.plan":
        extra_reasons = _validate_education_plan_text(text)

    # ── 5. 윤리경영 보고서 ──
    elif slot_name == "compliance.ethics.report":
        if "2025" not in text:
            extra_reasons.append("WRONG_YEAR")

    return list(dict.fromkeys(extra_reasons))