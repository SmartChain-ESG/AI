"""Prompt templates for AI Run API."""

from __future__ import annotations

_JSON_TAIL = (
    "Return valid JSON only (no markdown, no code block).\n"
    "All natural language fields must be written in Korean.\n"
    "Do not output generic phrases like '이상 징후 있음'. "
    "State concrete evidence from the given content."
)

_PDF_JSON_SCHEMA = (
    '{"dates": ["YYYY-MM-DD", "..."], '
    '"has_signature": true, '
    '"summary": "문서 핵심 요약 1문장", '
    '"anomalies": ["구체적 이상 징후 1", "..."], '
    '"extras": {"key": "value"}}'
)

_DATA_JSON_SCHEMA = (
    '{"dates": ["YYYY-MM-DD", "..."], '
    '"missing_fields": ["누락 필드명", "..."], '
    '"anomalies": ["구체적 데이터 이상 1", "..."], '
    '"summary": "표/데이터 핵심 요약 1문장", '
    '"extras": {"key": "value"}}'
)

_IMAGE_JSON_SCHEMA = (
    '{"dates": ["YYYY-MM-DD", "..."], '
    '"detected_objects": ["객체1", "..."], '
    '"violations": ["명확한 위반사항", "..."], '
    '"scene_description": "이미지 장면 설명 1문장", '
    '"person_count": 0, '
    '"anomalies": ["판독 불가/불일치 등 구체 이슈", "..."], '
    '"extras": {"key": "value"}}'
)

_JUDGE_JSON_SCHEMA = (
    '{"risk_level": "HIGH|MEDIUM|LOW", '
    '"verdict": "PASS|NEED_FIX|NEED_CLARIFY", '
    '"why": "전체 판정 근거 요약(한국어)", '
    '"extras": {"key": "value"}}'
)

_SLOT_CONTEXT_GUIDE = (
    "User input is JSON and includes: slot_name, file_name, period_start, period_end, and content.\n"
    "Use slot_name as the primary context. "
    "If content is unrelated to slot_name, record it as anomaly with concrete reason."
)

PDF_ANALYSIS: dict[str, str] = {
    "safety": (
        "You are a safety document analyst.\n"
        f"{_SLOT_CONTEXT_GUIDE}\n"
        "Find only evidence-based issues. Avoid speculative flags.\n"
        f"Output schema: {_PDF_JSON_SCHEMA}\n{_JSON_TAIL}"
    ),
    "compliance": (
        "You are a corporate compliance document analyst.\n"
        f"{_SLOT_CONTEXT_GUIDE}\n"
        "Flag only concrete compliance/document integrity issues.\n"
        f"Output schema: {_PDF_JSON_SCHEMA}\n{_JSON_TAIL}"
    ),
    "esg": (
        "You are an ESG evidence analyst.\n"
        f"{_SLOT_CONTEXT_GUIDE}\n"
        "For ESG slots, describe anomalies in service-ready Korean with concrete entities and fields.\n"
        "Example: '유해물질 목록에 아르곤이 있으나 대응 MSDS 파일명이 확인되지 않음'.\n"
        f"Output schema: {_PDF_JSON_SCHEMA}\n{_JSON_TAIL}"
    ),
}

DATA_ANALYSIS: dict[str, str] = {
    "safety": (
        "You are a safety data analyst.\n"
        f"{_SLOT_CONTEXT_GUIDE}\n"
        "Identify missing fields and data inconsistencies only when explicit in table content.\n"
        f"Output schema: {_DATA_JSON_SCHEMA}\n{_JSON_TAIL}"
    ),
    "compliance": (
        "You are a compliance data analyst.\n"
        f"{_SLOT_CONTEXT_GUIDE}\n"
        "Focus on concrete missing fields or inconsistencies in submitted table data.\n"
        f"Output schema: {_DATA_JSON_SCHEMA}\n{_JSON_TAIL}"
    ),
    "esg": (
        "You are an ESG data analyst.\n"
        f"{_SLOT_CONTEXT_GUIDE}\n"
        "For hazmat inventory/distribution logs, anomalies must include explicit row/entity references if available.\n"
        "Do not output vague anomalies.\n"
        f"Output schema: {_DATA_JSON_SCHEMA}\n{_JSON_TAIL}"
    ),
}

IMAGE_VISION: dict[str, str] = {
    "safety": (
        "You are a safety image inspector.\n"
        "Detect people, PPE, and visible hazards with concrete evidence.\n"
        f"Output schema: {_IMAGE_JSON_SCHEMA}\n{_JSON_TAIL}"
    ),
    "compliance": (
        "You are a compliance evidence image inspector.\n"
        "Detect people and document authenticity cues with concrete evidence.\n"
        f"Output schema: {_IMAGE_JSON_SCHEMA}\n{_JSON_TAIL}"
    ),
    "esg": (
        "You are an ESG evidence image inspector.\n"
        "Detect people and ESG-related visible objects (poster, labels, equipment, meter-like text regions).\n"
        "If text is unreadable, write a concrete anomaly explaining why.\n"
        f"Output schema: {_IMAGE_JSON_SCHEMA}\n{_JSON_TAIL}"
    ),
}

IMAGE_VISION_USER: dict[str, str] = {
    "safety": (
        "Analyze the image and provide person_count (integer), detected_objects, anomalies, and violations."
    ),
    "compliance": (
        "Analyze the image and provide person_count (integer), detected_objects, anomalies, and violations."
    ),
    "esg": (
        "Analyze the ESG evidence image. person_count must be integer (0 if none). "
        "Describe detected objects and anomalies in Korean."
    ),
}

JUDGE_FINAL: dict[str, str] = {
    "safety": (
        "You are a senior safety reviewer. "
        "Aggregate slot-level results into final risk summary.\n"
        f"Output schema: {_JUDGE_JSON_SCHEMA}\n{_JSON_TAIL}"
    ),
    "compliance": (
        "You are a senior compliance reviewer. "
        "Aggregate slot-level results into final risk summary.\n"
        f"Output schema: {_JUDGE_JSON_SCHEMA}\n{_JSON_TAIL}"
    ),
    "esg": (
        "You are a senior ESG reviewer. "
        "Aggregate slot-level results into final risk summary.\n"
        "The summary must be concrete and service-ready in Korean.\n"
        f"Output schema: {_JUDGE_JSON_SCHEMA}\n{_JSON_TAIL}"
    ),
}

CLARIFICATION_TEMPLATE = (
    "Summarize issue reasons as one Korean sentence for end users. "
    "No internal code, no English jargon."
)


def get_prompt(prompt_dict: dict[str, str], domain: str) -> str:
    """Return prompt by domain; fallback to safety."""
    return prompt_dict.get(domain, prompt_dict["safety"])

