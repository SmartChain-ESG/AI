from __future__ import annotations

from openai import OpenAI

from app.core.config import settings


def _client() -> OpenAI:
    if settings.openai_base_url:
        return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    return OpenAI(api_key=settings.openai_api_key)


def generate_answer(system_prompt: str, user_prompt: str, *, use_heavy: bool = True) -> str:
    model = settings.openai_model_heavy if use_heavy else settings.openai_model_light

    client = _client()
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    # openai-python은 편의 속성 output_text를 제공
    text = getattr(resp, "output_text", None)
    if text:
        return text.strip()

    # fallback (SDK/응답 구조가 바뀌었을 때)
    try:
        return resp.output[0].content[0].text.strip()
    except Exception:
        return str(resp)
