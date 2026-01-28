"""파일 다운로드 — SAS URL 또는 로컬 경로 지원."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import FILE_FETCH_TIMEOUT
from app.core.errors import FileFetchError


def _is_local_path(uri: str) -> bool:
    parsed = urlparse(uri)
    if parsed.scheme in ("", "file"):
        return True
    # Windows 드라이브 경로 (C:/...)
    if len(parsed.scheme) == 1 and parsed.scheme.isalpha():
        return True
    return False


async def download_file(uri: str) -> bytes:
    """storage_uri에서 파일 바이트를 가져온다. 로컬 경로와 HTTP URL 모두 지원."""
    if _is_local_path(uri):
        # file:// 스킴 제거
        path = uri
        if path.startswith("file:///"):
            path = path[8:]
        elif path.startswith("file://"):
            path = path[7:]
        try:
            return Path(path).read_bytes()
        except (FileNotFoundError, OSError) as exc:
            raise FileFetchError(uri, detail=str(exc))

    try:
        async with httpx.AsyncClient(timeout=FILE_FETCH_TIMEOUT) as client:
            resp = await client.get(uri)
            resp.raise_for_status()
            return resp.content
    except httpx.HTTPError as exc:
        raise FileFetchError(uri, detail=str(exc))
