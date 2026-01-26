# app/db/repo.py

from __future__ import annotations

from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.db.models import EsgRun, EsgFile


def esg_db_get_run(db: Session, run_id: str) -> EsgRun | None:
    stmt = select(EsgRun).where(EsgRun.run_id == run_id)
    return db.execute(stmt).scalars().first()


def esg_db_get_latest_run_by_draft(db: Session, draft_id: str) -> EsgRun | None:
    stmt = (
        select(EsgRun)
        .where(EsgRun.draft_id == draft_id)
        .order_by(desc(EsgRun.created_at))
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
    result_json: dict,
) -> EsgRun:
    run = EsgRun(
        run_id=run_id,
        draft_id=draft_id,
        prev_run_id=prev_run_id,
        status=status,
        result_json=result_json,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def esg_db_save_files(db: Session, *, run_id: str, files: list[dict]) -> None:
    rows: list[EsgFile] = []
    for f in files:
        rows.append(
            EsgFile(
                run_id=run_id,
                file_id=str(f.get("file_id", "")),
                file_name=str(f.get("file_name", "")),
                file_path=str(f.get("file_path", "")),
                ext=str(f.get("ext", "")),
                kind=str(f.get("kind", "")),
            )
        )
    db.add_all(rows)
    db.commit()