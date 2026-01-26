# app/db/models.py

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.session import Base


class EsgRun(Base):
    """
    AI 엔진 실행 1회 = 1 run
    result_json에 최종 응답(메인+부가서비스 결과)을 그대로 저장(JSONB)
    """
    __tablename__ = "esg_run"

    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)  # uuid hex
    draft_id: Mapped[str] = mapped_column(String(128), index=True)
    prev_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(8), index=True)  # OK/WARN/FAIL

    # 최종 결과(응답) 통째로 저장
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    files: Mapped[list["EsgFile"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class EsgFile(Base):
    """
    run에 포함된 업로드 파일 메타 저장(실제 파일은 로컬/스토리지에 있음)
    """
    __tablename__ = "esg_file"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    run_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("esg_run.run_id", ondelete="CASCADE"),
        index=True,
    )

    file_id: Mapped[str] = mapped_column(String(32), index=True)
    file_name: Mapped[str] = mapped_column(Text)
    file_path: Mapped[str] = mapped_column(Text)
    ext: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(16))

    run: Mapped["EsgRun"] = relationship(back_populates="files")


Index("ix_esg_run_draft_created", EsgRun.draft_id, EsgRun.created_at)
Index("ix_esg_file_run_fileid", EsgFile.run_id, EsgFile.file_id)