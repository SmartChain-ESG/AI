"""Naver Clova OCR client."""

from __future__ import annotations

import base64
import time
import uuid

import httpx

from app.core.config import CLOVA_INVOKE_URL, CLOVA_OCR_SECRET


async def run_ocr(image_data: bytes, file_format: str = "png") -> str:
    """Send image bytes to Clova OCR and return concatenated text."""
    payload = {
        "version": "V2",
        "requestId": str(uuid.uuid4()),
        "timestamp": int(time.time() * 1000),
        "images": [
            {
                "format": file_format,
                "name": "image",
                "data": base64.b64encode(image_data).decode(),
            }
        ],
    }

    headers = {
        "X-OCR-SECRET": CLOVA_OCR_SECRET,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(CLOVA_INVOKE_URL, headers=headers, json=payload)
        resp.raise_for_status()

    result = resp.json()
    texts: list[str] = []
    for img in result.get("images", []):
        for field in img.get("fields", []):
            texts.append(field.get("inferText", ""))
    return " ".join(texts)
