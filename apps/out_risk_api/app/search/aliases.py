# AI/apps/out_risk_api/app/search/aliases.py

# 신규: 회사명 별칭(alias) 테이블(검색 확장용)
esg_COMPANY_ALIASES = {
    "SK하이닉스": ["SK Hynix", "에스케이하이닉스", "하이닉스"],
    "SK이노베이션": ["SK Innovation", "에스케이이노베이션", "SK이노"],
    "삼성SDI": ["Samsung SDI", "삼성 SDI"],
    "성광벤드": ["성광밴드", "성광벤드", "성광 벤드", "성광_벤드"]
}

# 신규: 회사명으로 검색어 후보를 만든다(회사명 + alias)
def esg_expand_company_terms(company_name: str) -> list[str]:
    base = (company_name or "").strip()
    if not base:
        return []

    # 신규: alias 가져오기
    aliases = esg_COMPANY_ALIASES.get(base, [])

    # 신규: 중복 제거
    terms = [base] + [a.strip() for a in aliases if a and a.strip()]
    uniq: list[str] = []
    seen: set[str] = set()
    for t in terms:
        if t in seen:
            continue
        seen.add(t)
        uniq.append(t)
    return uniq
