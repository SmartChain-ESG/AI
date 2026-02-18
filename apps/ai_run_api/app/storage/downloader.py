"""파일 다운로드 — SAS URL 또는 로컬 경로 지원."""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, urlunparse

import httpx

from app.core.config import FILE_FETCH_TIMEOUT
from app.core.errors import FileFetchError

logger = logging.getLogger(__name__)


def _is_local_path(uri: str) -> bool:
    parsed = urlparse(uri)
    if parsed.scheme in ("", "file"):
        return True
    # Windows 드라이브 경로 (C:/...)
    if len(parsed.scheme) == 1 and parsed.scheme.isalpha():
        return True
    return False


def _normalize_http_url(uri: str) -> str:
    """Keep query/signature intact, but normalize path encoding for non-ASCII filenames."""
    parsed = urlparse(uri)
    path = quote(unquote(parsed.path), safe="/%")
    return urlunparse(parsed._replace(path=path))


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
        target = _normalize_http_url(uri)
        async with httpx.AsyncClient(timeout=FILE_FETCH_TIMEOUT) as client:
            resp = await client.get(target)
            resp.raise_for_status()
            return resp.content
    except httpx.HTTPStatusError as exc:
        body = (exc.response.text or "")[:300]
        detail = f"status={exc.response.status_code}, body={body}"
        logger.error("File download HTTP status error: %s | uri=%s", detail, uri)
        raise FileFetchError(uri, detail=detail)
    except httpx.HTTPError as exc:
        logger.error("File download HTTP error: %s | uri=%s", exc, uri)
        raise FileFetchError(uri, detail=str(exc))
    except Exception as exc:
        logger.error("File download unexpected error: %s | uri=%s", exc, uri)
        raise FileFetchError(uri, detail=f"{type(exc).__name__}: {exc}")
