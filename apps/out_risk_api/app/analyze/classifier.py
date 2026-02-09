# AI/apps/out_risk_api/app/analyze/classifier.py
# 20260131 이종헌 수정: 외부 기사 텍스트에서 카테고리/기본 심각도 추정 규칙 주석 보강

from typing import List, Tuple, Set
from dataclasses import dataclass, field
from app.schemas.risk import DocItem, Signal, Category

@dataclass
# 20260131 이종헌 신규: ESG 외부 문서 분류 결과를 담는 카테고리/심각도 컨테이너
class GuestCategoryResult:
    category: Category
    severity: int
    tags: Set[str] = field(default_factory=set)

# 20260131 이종헌 수정: 키워드 기반 1차 카테고리 추정 함수
def esg_guess_category(text: str) -> GuestCategoryResult:
    t = text.lower()
    if any(k in t for k in ["사고", "사망", "재해", "안전"]):
        return GuestCategoryResult(Category.SAFETY_ACCIDENT, 4, {"safety"})
    if any(k in t for k in ["제재", "과징금", "법위반", "구속"]):
        return GuestCategoryResult(Category.LEGAL_SANCTION, 5, {"legal"})
    return GuestCategoryResult(Category.LEGAL_SANCTION, 0, set())

# 20260131 이종헌 신규: 회사 문서 묶음을 단일 signal 점수로 축약
def esg_classify_and_score(company_name: str, docs: List[DocItem]) -> Tuple[float, List[Signal]]:
    if not docs: return 0.0, []
    
    combined_text = " ".join([d.title for d in docs[:5]])
    res = esg_guess_category(combined_text)
    
    if res.severity == 0: return 0.0, []
    
    # 20260131 이종헌 수정: 추정 결과를 Signal 스키마로 변환
    signal = Signal(
        category=res.category,
        severity=res.severity,
        score=float(res.severity) * 1.2,
        title=f"{company_name} 관련 이슈 감지",
        summary_ko=f"{res.category.value} 관련 리스크 신호가 확인되었습니다.",
        why="최근 수집된 문서에서 부정적 키워드가 식별됨",
        published_at=docs[0].published_at if docs else ""
    )
    return signal.score, [signal]
