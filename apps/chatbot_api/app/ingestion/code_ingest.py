from __future__ import annotations

from pathlib import Path

# ✅ LangChain의 강력한 파이썬 전용 스플리터 도입
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from app.services.retriever import Retriever
from app.utils.hash import sha256_text


def ingest_ai_run_code(
    *,
    repo_root: str,
    relative_targets: list[str] | None = None,
) -> dict:
    """
    ai_run_api 코드를 읽어 VectorDB에 적재.
    - LangChain Python Splitter를 사용하여 함수/클래스 단위 보존
    """
    if relative_targets is None:
        relative_targets = [
            "apps/ai_run_api/app/engines",
            "apps/ai_run_api/app/pipeline",
            "apps/ai_run_api/app/llm",
        ]

    r = Retriever()
    upserted_count = 0

    # ✅ 파이썬 문법(class, def, if 등)을 인식해서 자르는 설정
    splitter = RecursiveCharacterTextSplitter.from_language(
        language=Language.PYTHON,
        chunk_size=1000,      # 코드 덩어리 크기
        chunk_overlap=200,    # 겹치는 부분 (맥락 유지)
    )

    for rel in relative_targets:
        base = Path(repo_root) / rel
        if not base.exists():
            continue

        for p in base.rglob("*.py"):
            # 파일 읽기
            content = p.read_text(encoding="utf-8", errors="ignore")
            if not content.strip():
                continue

            # domain 추정 로직 (기존 유지)
            domain = "all"
            parts = p.as_posix().split("/")
            if "engines" in parts:
                i = parts.index("engines")
                if i + 1 < len(parts):
                    domain = parts[i + 1]

            # ✅ LangChain으로 청킹 실행
            # create_documents를 쓰면 메타데이터 관리도 편함
            docs = splitter.create_documents([content])

            for i, doc in enumerate(docs):
                chunk_text = doc.page_content
                
                # 너무 짧은 코드 조각은 무시 (import 구문 등 노이즈 제거)
                if len(chunk_text) < 20:
                    continue

                h = sha256_text(chunk_text)
                
                # 소스 ID 생성 (파일경로:순서:해시)
                source_id = f"code:{p.name}:c{i}:{h[:12]}"
                
                meta = {
                    "source_id": source_id,
                    "type": "code",
                    "title": p.name,
                    "path": str(p),
                    "domain": domain,
                    "chunk_index": i
                }

                emb = r.embed(chunk_text)
                
                r.collection.upsert(
                    ids=[source_id],
                    embeddings=[emb],
                    documents=[chunk_text],
                    metadatas=[meta],
                )
                upserted_count += 1

    return {"upserted": upserted_count}