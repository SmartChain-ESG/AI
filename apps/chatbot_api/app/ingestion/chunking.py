from __future__ import annotations

from dataclasses import dataclass

# ✅ LangChain 라이브러리 활용
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter


@dataclass(frozen=True)
class Chunk:
    text: str
    meta: dict


def chunk_python_code(path: str, content: str, *, domain: str) -> list[Chunk]:
    """
    LangChain을 사용한 고도화된 코드 청킹:
    - Python 문법(class, def, decorator 등)을 이해하고 분리
    """
    if not content.strip():
        return []

    # 1. 파이썬 전용 스플리터 생성
    splitter = RecursiveCharacterTextSplitter.from_language(
        language=Language.PYTHON,
        chunk_size=1000,
        chunk_overlap=200,
    )

    # 2. 자르기 수행
    docs = splitter.create_documents([content])
    
    chunks: list[Chunk] = []
    for i, doc in enumerate(docs):
        block = doc.page_content
        
        # 너무 짧은 코드는 버림 (노이즈 제거)
        if len(block) < 20:
            continue

        chunks.append(
            Chunk(
                text=block,
                meta={
                    "path": path,
                    "domain": domain,
                    "type": "code",
                    "title": path,
                    # LangChain은 라인 번호를 자동으로 주지 않으므로 
                    # 순서(chunk_index)로 대체하여 관리
                    "chunk_index": i, 
                },
            )
        )
            
    return chunks