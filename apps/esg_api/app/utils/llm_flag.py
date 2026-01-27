# app/utils/llm_flag.py

import os
from typing import Any, Dict, Optional

def esg_is_llm_enabled() -> bool:
    mode = (os.getenv("LLM_MODE") or "off").strip().lower()
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    return (mode == "on") and bool(key)

def esg_llm_trace_init() -> Dict[str, Any]:
    return {"enabled": esg_is_llm_enabled(), "calls": []}

def esg_llm_trace_record(
    trace: Dict[str, Any],
    *,
    node: str,
    used: bool,
    fallback: bool,
    error: Optional[str] = None,
) -> None:
    trace["calls"].append({"node": node, "used": used, "fallback": fallback, "error": error})