# AI/apps/out_risk_api/app/rag/chroma.py

# 20260203 이종헌 수정: Chroma RAG 준비상태/업서트/리트리브 주석 보강
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core import config
from app.rag.chunking import esg_chunk_documents

logger = logging.getLogger("esg_rag")


# 1. 라이브러리 가용성 체크 (Import Isolation)
_LC_IMPORT_ERROR = ""
try:
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings
    from langchain_core.documents import Document
    _LC_AVAILABLE = True
except Exception as e:
    Chroma = None
    OpenAIEmbeddings = None
    Document = None
    _LC_AVAILABLE = False
    _LC_IMPORT_ERROR = str(e)


# 2. RAG 핵심 클래스
# 20260131 이종헌 신규: Chroma 기반 외부문서 임시 코퍼스 RAG 래퍼
class esg_ChromaRag:
    def __init__(self, persist_dir: str, collection: str) -> None:
        self.persist_dir = persist_dir
        self.collection = collection
        self._vs = None

    def esg_ready(self) -> bool:
        """가동 가능 상태 확인 (API 키 및 라이브러리 체크)"""
        return bool(
            _LC_AVAILABLE and 
            config.OPENAI_API_KEY and 
            Chroma is not None and 
            OpenAIEmbeddings is not None
        )

    def esg_debug_ready(self) -> Dict[str, Any]:
        """진단용 상세 상태 (배시 헬스체크 및 UI 연동용)"""
        return {
            "lc_available": bool(_LC_AVAILABLE),
            "openai_key_loaded": bool(config.OPENAI_API_KEY),
            "chroma_class_ok": Chroma is not None,
            "embeddings_class_ok": OpenAIEmbeddings is not None,
            "import_error": _LC_IMPORT_ERROR,
            "persist_dir": self.persist_dir,
            "collection": self.collection,
            "heartbeat": self.esg_heartbeat(),
        }

    def esg_heartbeat(self) -> bool:
        """Chroma DB 연결 상태 실시간 확인 (WARN 방지 핵심 로직)"""
        if self._vs is None:
            # 아직 초기화되지 않았다면, 연결 시도 없이 False 반환
            return False
        try:
            # 하부 chromadb 클라이언트의 heartbeat 호출
            return self._vs._client.heartbeat() > 0
        except Exception:
            return False

# 20260203 이종헌 수정: lazy init + readiness check 기반으로 RAG 안전 실행
    def esg_get_store(self) -> Any:
        """벡터스토어 인스턴스 지연 로딩 (Lazy Loading)"""
        if self._vs is not None:
            return self._vs

        if not self.esg_ready():
            logger.error(f"RAG 준비 실패: {_LC_IMPORT_ERROR}")
            return None

        try:
            # 임베딩 생성 (API 키 명시적 주입으로 Azure 환경 대응)
            embeddings = OpenAIEmbeddings(openai_api_key=config.OPENAI_API_KEY)
            
            self._vs = Chroma(
                collection_name=self.collection,
                persist_directory=self.persist_dir,
                embedding_function=embeddings,
            )
            return self._vs
        except Exception as e:
            logger.error(f"Chroma Store 초기화 실패: {e}")
            return None

# 20260203 이종헌 수정: 문서 청크를 벡터DB에 저장하는 업서트 경로
    def esg_upsert(self, docs: List[Dict[str, Any]], chunk_size: int = 0) -> int:
        """
        문서 리스트를 청킹하여 벡터 DB에 추가
        docs: [{"text": "...", "metadata": {...}}, ...]
        """
        if not self.esg_ready():
            return 0

        # 청크 사이즈 결정 (전달 인자 우선, 없으면 config 기본값)
        c_size = chunk_size if chunk_size > 0 else config.RAG_CHUNK_SIZE_DEFAULT
        
        chunks = esg_chunk_documents(docs, chunk_size=c_size)
        if not chunks:
            return 0

        vs = self.esg_get_store()
        if vs is None:
            return 0

        try:
            lc_docs = [
                Document(
                    page_content=c.get("text", "") or "", 
                    metadata=c.get("metadata", {}) or {}
                ) 
                for c in chunks if c.get("text")
            ]
            
            if not lc_docs:
                return 0

            vs.add_documents(lc_docs)
            return len(lc_docs)
        except Exception as e:
            logger.error(f"Chroma Upsert 에러: {e}")
            return 0

# 20260203 이종헌 수정: query 기반 top_k 검색 결과 반환
    def esg_retrieve(self, query: str, top_k: int = 0) -> List[Dict[str, Any]]:
        """유사도 검색 수행"""
        if not self.esg_ready():
            return []

        vs = self.esg_get_store()
        if vs is None:
            return []

        q = (query or "").strip()
        if not q:
            return []

        # top_k 결정
        k = top_k if top_k > 0 else config.RAG_TOP_K_DEFAULT

        try:
            hits = vs.similarity_search(q, k=max(1, int(k)))
            out: List[Dict[str, Any]] = []
            for h in hits:
                out.append({
                    "text": h.page_content, 
                    "metadata": dict(h.metadata)
                })
            return out
        except Exception as e:
            logger.error(f"Chroma Retrieval 에러: {e}")
            return []


# 3. 인스턴스 팩토리 함수
# 20260203 이종헌 수정: 전역 RAG 인스턴스 지연 초기화/재사용 진입점
def esg_get_rag() -> esg_ChromaRag:
    """RAG 객체 싱글톤/팩토리 획득"""
    return esg_ChromaRag(
        persist_dir=config.CHROMA_PERSIST_DIR,
        collection=config.CHROMA_COLLECTION,
    )
