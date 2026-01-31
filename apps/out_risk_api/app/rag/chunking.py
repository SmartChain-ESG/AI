#AI/apps/out_risk_api/app/rag/chunking.py

# 20260131 이종헌 신규: 문서 텍스트를 chunk_size 기준으로 청킹(LC 있으면 splitter 사용, 없으면 fallback)
from __future__ import annotations

from typing import Any, Dict, List, Tuple

try:
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    _LC_AVAILABLE = True
except Exception:
    Document = None
    RecursiveCharacterTextSplitter = None
    _LC_AVAILABLE = False


def esg_chunk_documents(text_items: List[Dict[str, Any]], chunk_size: int) -> List[Dict[str, Any]]:
    """
    text_items: [{"text": "...", "metadata": {...}}, ...]
    return: [{"text": "chunk...", "metadata": {...}}, ...]
    """
    chunk_size = max(200, int(chunk_size or 800))

    if not text_items:
        return []

    if _LC_AVAILABLE and RecursiveCharacterTextSplitter is not None and Document is not None:
        splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=80)

        docs: List[Document] = []
        for item in text_items:
            docs.append(Document(page_content=item.get("text", "") or "", metadata=item.get("metadata", {}) or {}))

        split_docs = splitter.split_documents(docs)

        out: List[Dict[str, Any]] = []
        for d in split_docs:
            out.append({"text": d.page_content, "metadata": dict(d.metadata)})
        return out

    # fallback: 단순 슬라이스
    out2: List[Dict[str, Any]] = []
    for item in text_items:
        text = (item.get("text", "") or "").strip()
        meta = item.get("metadata", {}) or {}
        if not text:
            continue

        i = 0
        while i < len(text):
            out2.append({"text": text[i : i + chunk_size], "metadata": meta})
            i += max(1, chunk_size - 80)
    return out2
