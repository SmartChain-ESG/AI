# AI/apps/out_risk_api/app/core/config.py  

# 20260131 이종헌 신규: out_risk_api 환경변수 설정 로더
import os


def esg_env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def esg_env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except Exception:
        return default


OPENAI_API_KEY = esg_env("OPENAI_API_KEY", "")
OPENAI_MODEL_LIGHT = esg_env("OPENAI_MODEL_LIGHT", "gpt-4o-mini")

CHROMA_PERSIST_DIR = esg_env("CHROMA_PERSIST_DIR", "./.chroma_out_risk")
CHROMA_COLLECTION = esg_env("CHROMA_COLLECTION", "out_risk")

RAG_TOP_K_DEFAULT = esg_env_int("RAG_TOP_K_DEFAULT", 6)
RAG_CHUNK_SIZE_DEFAULT = esg_env_int("RAG_CHUNK_SIZE_DEFAULT", 800)