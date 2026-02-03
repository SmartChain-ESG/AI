# AI/apps/out_risk_api/app/core/config.py

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# 로거 설정 (디버깅용)
logger = logging.getLogger("esg_config")

# 1. 경로 설정: config.py 기준으로 5단계 위가 AI(루트) 폴더
# 변경 (위로 올라가며 .env 찾기)
def _find_env_path(start: Path) -> Path | None:
    for p in start.parents:
        candidate = p / ".env"
        if candidate.exists():
            return candidate
    return None

ENV_PATH = _find_env_path(Path(__file__).resolve())
BASE_DIR = ENV_PATH.parent if ENV_PATH else Path(__file__).resolve().parents[4]


# 2. .env 로드 로직
if ENV_PATH and ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)
else:
    load_dotenv()


# 3. 라이브러리 가용성 체크 (Pylance 에러 방지 및 런타임 안정성)
_LC_IMPORT_ERROR = ""
try:
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings
    _LC_AVAILABLE = True
except Exception as e:
    Chroma = None
    OpenAIEmbeddings = None
    _LC_AVAILABLE = False
    _LC_IMPORT_ERROR = str(e)

# 4. 환경 변수 래퍼 함수
def esg_env(key: str, default: str = "") -> str:
    return os.getenv(key, default)

def esg_env_int(key: str, default: int) -> int:
    try:
        val = os.getenv(key)
        return int(val) if val is not None else default
    except (ValueError, TypeError):
        return default

# 5. 전역 설정 변수
OPENAI_API_KEY = esg_env("OPENAI_API_KEY", "")
OPENAI_MODEL_LIGHT = esg_env("OPENAI_MODEL_LIGHT", "gpt-4o-mini")

# Chroma 관련 설정 (경로는 프로젝트 루트 기준 혹은 절대경로 권장)
CHROMA_PERSIST_DIR = esg_env("CHROMA_PERSIST_DIR", str(BASE_DIR / "data" / "chroma_db"))
CHROMA_COLLECTION = esg_env("CHROMA_COLLECTION", "out_risk")

RAG_TOP_K_DEFAULT = esg_env_int("RAG_TOP_K_DEFAULT", 6)
RAG_CHUNK_SIZE_DEFAULT = esg_env_int("RAG_CHUNK_SIZE_DEFAULT", 800)

# Azure 이관 시 팁: Azure App Service 환경 설정에 OPENAI_API_KEY를 등록하면 
# .env 파일 없이도 위 코드가 동일하게 작동합니다.
