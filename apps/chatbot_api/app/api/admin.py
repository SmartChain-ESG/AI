from __future__ import annotations

from pathlib import Path

# BackgroundTasks 추가됨
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import APIKeyHeader

from app.core.config import settings
from app.ingestion.code_ingest import ingest_ai_run_code
from app.ingestion.pdf_ingest import ingest_manual_pdfs
from app.services.retriever import Retriever

router = APIRouter(prefix="/api/admin", tags=["admin"])

api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

# ✅ 경로 설정 (그대로 유지)
APP_DIR = Path(__file__).resolve().parents[1]
MANUALS_DIR = APP_DIR / "manuals"
REPO_ROOT = APP_DIR.parents[2]


def require_admin_key(api_key: str | None = Depends(api_key_header)) -> None:
    if not api_key or api_key != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


# ✅ [새로 추가] 백그라운드에서 오래 걸리는 작업을 수행할 함수
def run_sync_logic():
    print("\n>>> [Background] 동기화 작업 시작: PDF 및 코드 적재 중...")
    try:
        # 실제 적재 로직 실행
        code_res = ingest_ai_run_code(repo_root=str(REPO_ROOT))
        pdf_res = ingest_manual_pdfs(manuals_dir=str(MANUALS_DIR), domain="all")
        print(f">>> [Background] 동기화 완료! (Code: {code_res}, PDF: {pdf_res})\n")
    except Exception as e:
        print(f">>> [Background] 동기화 중 에러 발생: {e}\n")


# ✅ [수정] BackgroundTasks를 파라미터로 받고, 작업을 예약한 뒤 즉시 리턴
@router.post("/sync")
def sync(background_tasks: BackgroundTasks, _: None = Depends(require_admin_key)) -> dict:
    """
    - 오래 걸리는 적재 작업을 백그라운드로 넘기고
    - 사용자에게는 즉시 '시작되었습니다' 응답을 보냄 (타임아웃 방지)
    """
    background_tasks.add_task(run_sync_logic)
    
    return {
        "status": "accepted",
        "message": "동기화 작업이 백그라운드에서 시작되었습니다. 완료될 때까지 터미널 로그를 확인해주세요."
    }


@router.get("/inspect")
def inspect_db(_: None = Depends(require_admin_key)) -> dict:
    """Vector DB에 저장된 문서 현황(개수, 샘플) 조회"""
    r = Retriever()
    count = r.collection.count()
    peek = r.collection.peek(limit=10)

    samples = []
    if peek and peek.get("metadatas"):
        for meta in peek["metadatas"]:
            # 안전하게 필드 가져오기
            m_type = meta.get('type', 'unknown')
            m_title = meta.get('title', 'no title')
            m_id = meta.get('source_id', 'no id')
            samples.append(f"[{m_type}] {m_title} (ID: {m_id})")

    return {"total_documents": count, "samples": samples}