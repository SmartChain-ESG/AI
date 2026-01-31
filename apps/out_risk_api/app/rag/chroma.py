# AI/apps/out_risk_api/app/rag/chroma.py

# 20260131 이종헌 신규: Chroma(=chromadb) 기반 벡터 인덱싱/검색 모듈(LangChain wrapper)
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core import config
from app.rag.chunking import esg_chunk_documents

try:
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings

    _LC_AVAILABLE = True
except Exception:
    Chroma = None
    OpenAIEmbeddings = None
    _LC_AVAILABLE = False


class esg_ChromaRag:
    def __init__(self, persist_dir: str, collection: str) -> None:
        self.persist_dir = persist_dir
        self.collection = collection
        self._vs = None

    def esg_ready(self) -> bool:
        return bool(_LC_AVAILABLE and config.OPENAI_API_KEY and Chroma is not None and OpenAIEmbeddings is not None)

    def esg_get_store(self) -> Any:
        if self._vs is not None:
            return self._vs

        embeddings = OpenAIEmbeddings()
        self._vs = Chroma(
            collection_name=self.collection,
            persist_directory=self.persist_dir,
            embedding_function=embeddings,
        )
        return self._vs

    def esg_upsert(self, docs: List[Dict[str, Any]], chunk_size: int) -> int:
        """
        docs: [{"text": "...", "metadata": {...}}, ...]
        """
        if not self.esg_ready():
            return 0

        chunks = esg_chunk_documents(docs, chunk_size=chunk_size)
        if not chunks:
            return 0

        vs = self.esg_get_store()

        # add_documents는 내부에서 embeddings 생성
        # (2일 MVP: 중복 관리/ID 관리까지는 생략)
        from langchain_core.documents import Document

        lc_docs = []
        for c in chunks:
            lc_docs.append(Document(page_content=c.get("text", "") or "", metadata=c.get("metadata", {}) or {}))

        vs.add_documents(lc_docs)
        return len(lc_docs)

    def esg_retrieve(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        if not self.esg_ready():
            return []

        vs = self.esg_get_store()
        q = (query or "").strip()
        if not q:
            return []

        hits = vs.similarity_search(q, k=max(1, int(top_k or 6)))
        out: List[Dict[str, Any]] = []
        for h in hits:
            out.append({"text": h.page_content, "metadata": dict(h.metadata)})
        return out


def esg_get_rag() -> esg_ChromaRag:
    return esg_ChromaRag(
        persist_dir=config.CHROMA_PERSIST_DIR,
        collection=config.CHROMA_COLLECTION,
    )