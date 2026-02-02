from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter  # ✅ 추가됨

from app.services.retriever import Retriever
from app.utils.hash import sha256_text


def ingest_manual_pdfs(*, manuals_dir: str, domain: str = "all") -> dict:
    r = Retriever()
    upserted_count = 0  # 변수명 명확하게 변경

    base = Path(manuals_dir)
    if not base.exists():
        return {"upserted": 0, "reason": "manuals_dir_not_found"}

    # ✅ [핵심 1] 법률/매뉴얼 문서에 최적화된 자르기 설정
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,      # 한 덩어리의 크기 (글자수)
        chunk_overlap=100,   # 앞뒤로 겹치게 할 글자수 (맥락 유지용)
        separators=[         # 우선순위대로 자름
            "\n제",          # "제1조" 같은 조항 시작 부분 (가장 중요)
            "\n\n",          # 문단 바뀔 때
            ". ",            # 문장 끝날 때
            "\n",            # 줄바꿈
            " ",             # 띄어쓰기
            ""               # 글자 단위
        ]
    )

    for pdf in base.rglob("*.pdf"):
        doc = fitz.open(pdf)
        print(f"Processing {pdf.name}...")  # 진행 상황 출력

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_text = page.get_text("text").strip()
            
            if not page_text:
                continue

            # ✅ [핵심 2] 페이지 통째로 넣는 게 아니라, 쪼개서 넣기
            chunks = text_splitter.split_text(page_text)

            for i, chunk_text in enumerate(chunks):
                # 텍스트가 너무 짧으면 무시 (노이즈 제거)
                if len(chunk_text) < 10:
                    continue

                h = sha256_text(chunk_text)
                
                # ID에 청크 번호(chunk_idx) 추가하여 구분
                source_id = f"manual:{pdf.name}:p{page_idx+1}:c{i}:{h[:8]}"
                
                meta = {
                    "source_id": source_id,
                    "type": "manual",
                    "category": "manual",
                    "doc_name": pdf.name,
                    "title": pdf.name,
                    "path": str(pdf),
                    "domain": domain,
                    "page": page_idx + 1,      # 몇 페이지인지 정보 유지
                    "chunk_index": i,          # 몇 번째 조각인지
                    "total_len": len(page_text)
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