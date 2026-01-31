# AI/apps/out_rick_api/app/search/provider.py

# 20260131 이종헌 신규: search.enabled=true일 때 외부 문서 수집(2일 MVP: stub, 나중에 구현)
from __future__ import annotations

from typing import List

from app.schemas.risk import DocItem, ExternalRiskDetectRequest


def esg_search_documents(req: ExternalRiskDetectRequest) -> List[DocItem]:
    """
    2일 MVP에서는 검색기를 강제하지 않기 위해 기본은 빈 리스트.
    실제 연동 시:
    - req.search.query / req.company.name
    - req.time_window_days
    - req.search.sources, req.search.max_results, req.search.lang
    를 사용해 DocItem 리스트를 만들어 반환하면 됨.
    """
    return []
