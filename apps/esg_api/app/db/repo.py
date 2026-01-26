# app/db/repo.py
from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EsgRun, EsgFile


def esg_db_get_run(db: Session, run_id: str) -> EsgRun | None:
    stmt = select(EsgRun).where(EsgRun.run_id == run_id)
    return db.execute(stmt).scalars().first()


def esg_db_get_latest_run_by_draft(db: Session, draft_id: str) -> EsgRun | None:
    # ✅ updated_at 없는 스키마도 안전하게: created_at 기준 최신 1건
    stmt = (
        select(EsgRun)
        .where(EsgRun.draft_id == draft_id)
        .order_by(EsgRun.created_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def esg_db_save_run(
    db: Session,
    *,
    run_id: str,
    draft_id: str,
    prev_run_id: str | None,
    status: str,
    result_json: dict[str, Any],
) -> EsgRun:
    row = EsgRun(
        run_id=run_id,
        draft_id=draft_id,
        prev_run_id=prev_run_id,
        status=status,
        result_json=result_json,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def esg_db_save_files(db: Session, *, run_id: str, files: Iterable[dict[str, Any]]) -> list[EsgFile]:
    """
    files: [{file_id, file_name, file_path, ext, kind, ...}]
    ✅ DB 테이블(esg_file)에 created_at이 없으므로 넣지 않는다.
    """
    rows: list[EsgFile] = []
    for f in files:
        row = EsgFile(
            run_id=run_id,
            file_id=str(f.get("file_id", "")),
            file_name=str(f.get("file_name", "")),
            file_path=str(f.get("file_path", "")),
            ext=str(f.get("ext", "")),
            kind=str(f.get("kind", "")),
        )
        db.add(row)
        rows.append(row)

    db.commit()
    # refresh는 optional. 필요하면 살려도 됨.
    return rows