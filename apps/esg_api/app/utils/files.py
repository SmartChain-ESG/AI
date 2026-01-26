# app/utils/files.py
from __future__ import annotations
from pathlib import Path
from fastapi import UploadFile
import uuid
import hashlib

def esg_guess_kind(ext: str) -> str:
    ext = (ext or "").lower().lstrip(".")
    if ext in ["xlsx", "xls"]:
        return "XLSX"
    if ext in ["pdf"]:
        return "PDF"
    if ext in ["png", "jpg", "jpeg"]:
        return "IMG" 
    return "UNKNOWN"

def esg_get_upload_dir() -> Path:
    out_dir = Path("tmp_uploads")
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir

def esg_save_uploads(files: list[UploadFile]) -> list[dict]:
    out_dir = esg_get_upload_dir()
    saved: list[dict] = []

    for f in files:
        file_id = uuid.uuid4().hex[:12]
        name = f.filename or f"{file_id}.bin"
        ext = (Path(name).suffix or "").lower().lstrip(".")
        kind = esg_guess_kind(ext)

        path = out_dir / f"{file_id}_{name}"

        try:
            f.file.seek(0)
        except Exception:
            pass

        content = f.file.read()
        with path.open("wb") as w:
            w.write(content)

        sha256 = hashlib.sha256(content).hexdigest()

        saved.append({
            "file_id": file_id,
            "file_name": name,
            "file_path": str(path),
            "ext": ext,
            "kind": kind,
            "sha256": sha256,
        })

    print(f"[upload] saved {len(saved)} file(s) into: {out_dir.resolve()}")
    return saved 