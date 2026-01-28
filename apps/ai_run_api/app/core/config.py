from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

CLOVA_INVOKE_URL: str = os.getenv("CLOVA_INVOKE_URL", "")
CLOVA_OCR_SECRET: str = os.getenv("CLOVA_OCR_SECRET", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL_LIGHT: str = os.getenv("OPENAI_MODEL_LIGHT", "gpt-4o-mini")
OPENAI_MODEL_HEAVY: str = os.getenv("OPENAI_MODEL_HEAVY", "gpt-4o")

FILE_FETCH_TIMEOUT: int = 30
MAX_PARALLEL_WORKERS: int = 10
