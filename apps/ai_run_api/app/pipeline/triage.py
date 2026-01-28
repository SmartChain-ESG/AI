"""Submit Phase 1 — TRIAGE (기획서 §4.2 단계 1).

파일 확장자/종류 분류 + 열 수 있는지 최소 체크.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from app.schemas.run import FileRef


SUPPORTED_EXTENSIONS = {
    "pdf": [".pdf"],
    "xlsx": [".xls", ".xlsx", ".csv"],
    "image": [".jpg", ".jpeg", ".png"],
}

ALL_SUPPORTED = {ext for exts in SUPPORTED_EXTENSIONS.values() for ext in exts}


def get_ext(uri: str) -> str:
    return PurePosixPath(uri.split("?")[0]).suffix.lower()


def get_file_type(ext: str) -> str | None:
    """확장자 → 'pdf' | 'xlsx' | 'image' | None."""
    for ftype, exts in SUPPORTED_EXTENSIONS.items():
        if ext in exts:
            return ftype
    return None


def triage_files(files: list[FileRef]) -> list[dict]:
    """각 파일을 분류하고, 지원하지 않는 확장자는 건너뛴다.

    Returns list of dicts: {file: FileRef, ext: str, file_type: str}
    """
    results: list[dict] = []
    for f in files:
        ext = get_ext(f.storage_uri)
        ftype = get_file_type(ext)
        if ftype:
            results.append({"file": f, "ext": ext, "file_type": ftype})
    return results
