# AI/apps/out_risk_api/app/core/config.py

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# 로거 설정 (디버깅용)
logger = logging.getLogger("esg_config")

# 1. 경로 설정: config.py 기준으로 5단계 위가 AI(루트) 폴더
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

# 2. .env 로드 로직
if ENV_PATH.exists():
    # override=True: 로컬 테스트 시 시스템 변수보다 .env를 우선 (개발 편의성)
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    # logger.info(f".env loaded from: {ENV_PATH}")
else:
    # 예비책: 현재 작업 디렉토리 기준 탐색
    load_dotenv()
    # logger.warning(".env not found at root, using default system environment variables.")

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