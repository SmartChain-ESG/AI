"""SAS URL 기반 파일 다운로드 (기획서 §2.1)."""

from __future__ import annotations

import httpx

from app.core.config import FILE_FETCH_TIMEOUT
from app.core.errors import FileFetchError


async def download_file(uri: str) -> bytes:
    """storage_uri (SAS URL)에서 파일 바이트를 다운로드한다."""
    try:
        async with httpx.AsyncClient(timeout=FILE_FETCH_TIMEOUT) as client:
            resp = await client.get(uri)
            resp.raise_for_status()
            return resp.content
    except httpx.HTTPError as exc:
        raise FileFetchError(uri, detail=str(exc))
