# AI/apps/out_risk_api/app/search/aliases.py

from __future__ import annotations

# 협력사명 별칭(alias) 테이블
esg_COMPANY_ALIASES = {
    "포스코홀딩스": ["POSCO Holdings", "POSCO홀딩스", "포스코 홀딩스", "POSCO"],
    "현대제철": ["Hyundai Steel", "현대 제철", "HSC", "HYUNDAI STEEL"],
    "성광벤드": ["SUNGKWANG BEND", "SungKwang Bend", "성광 벤드"],
    "동국제강": ["Dongkuk Steel", "동국 제강", "DKC"],
    "HD현대일렉트릭": ["HD Hyundai Electric", "현대일렉트릭", "HD현대 일렉트릭"],
}


# 회사명으로 검색어 후보를 만든다 (회사명 + alias)
# 20260202 이종헌 수정: 회사명 기준 별칭 확장으로 검색 recall 보강
def esg_expand_company_terms(company_name: str) -> list[str]:
    base = (company_name or "").strip()
    if not base:
        return []

    aliases = esg_COMPANY_ALIASES.get(base, [])
    terms = [base] + [a.strip() for a in aliases if a and a.strip()]

    uniq: list[str] = []
    seen: set[str] = set()
    for t in terms:
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)
    return uniq
