from __future__ import annotations

from typing import Any, Dict, Optional

import chromadb
from openai import OpenAI

from app.core.config import settings
from rank_bm25 import BM25Okapi


def _openai_client() -> OpenAI:
    if settings.openai_base_url:
        return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    return OpenAI(api_key=settings.openai_api_key)


class Retriever:
    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(path=settings.chroma_path)
        self.collection = self.client.get_or_create_collection(name=settings.chroma_collection)
        self.oa = _openai_client()

    def embed(self, text: str) -> list[float]:
        emb = self.oa.embeddings.create(
            model=settings.openai_embedding_model,
            input=text,
        )
        return emb.data[0].embedding

    def search(self, query: str, *, top_k: int, domain: str = "all", doc_name: str | None = None) -> list[dict]:
        where: Dict[str, Any] = {}
        
        # 1. 문서명 필터가 최우선 (특정 문서를 지정했으면 도메인 상관없이 검색)
        if doc_name:
            where = {"doc_name": doc_name}
        # 2. 도메인 필터 (선택한 도메인 + 전체 공개 도메인 'all')
        elif domain and domain != "all":
            where = {
                "$or": [
                    {"domain": domain},
                    {"domain": "all"}
                ]
            }

        q_emb = self.embed(query)

        # 1. 후보군 확대 (Hybrid Reranking을 위해 top_k의 3배수 검색)
        candidate_k = top_k * 3

        res = self.collection.query(
            query_embeddings=[q_emb],
            n_results=candidate_k,
            where=where if where else None,  # 조건이 없으면 None 전달
            include=["documents", "metadatas", "distances"],
        )

        docs = []
        for i in range(len(res["documents"][0])):
            doc_text = res["documents"][0][i]
            meta = res["metadatas"][0][i] or {}
            dist = res["distances"][0][i]

            # distance -> score(0~1) 간단 변환 (코사인 기반이 아니면 조정 필요)
            score = float(max(0.0, min(1.0, 1.0 - dist)))

            docs.append({"text": doc_text, "meta": meta, "score": score})
        
        # 2. BM25 Reranking (키워드 매칭 보정)
        if BM25Okapi and docs:
            # 간단한 공백 토크나이저 (한국어는 형태소 분석기 권장)
            tokenized_query = query.split()
            tokenized_corpus = [doc["text"].split() for doc in docs]
            
            bm25 = BM25Okapi(tokenized_corpus)
            bm25_scores = bm25.get_scores(tokenized_query)
            
            # 점수 정규화 (0~1) 및 결합
            if len(bm25_scores) > 0:
                min_s = min(bm25_scores)
                max_s = max(bm25_scores)
                
                for i, doc in enumerate(docs):
                    bm25_score = bm25_scores[i]
                    # 정규화 (분모 0 방지)
                    norm_bm25 = (bm25_score - min_s) / (max_s - min_s) if max_s > min_s else 0.0
                    
                    # 가중치 결합: Vector(0.7) + BM25(0.3)
                    doc["score"] = (doc["score"] * 0.7) + (norm_bm25 * 0.3)
            
            # 재정렬
            docs.sort(key=lambda x: x["score"], reverse=True)

        return docs[:top_k]
