# app/db/models.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB


class Base(DeclarativeBase):
    """모든 ORM 모델이 상속받는 Base 클래스"""
    pass


class EsgRun(Base):
    """
    한 번의 '검증 실행(run)' 결과를 저장하는 테이블.
    - /ai/agent/run 호출 1회 = EsgRun 1행
    - result_json에 그래프 실행 결과 전체를 JSON으로 보관
    """
    __tablename__ = "esg_runs"

    # 식별자
    run_id: Mapped[str] = mapped_column(String(32), primary_key=True)     # uuid hex[:12] 같은 값도 들어가므로 32로 넉넉히
    draft_id: Mapped[str] = mapped_column(String(128), index=True)        # 사용자가 주는 draft 식별자
    prev_run_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # 상태
    status: Mapped[str] = mapped_column(String(16), index=True)           # OK/WARN/FAIL 등

    # 결과 JSON (PostgreSQL JSONB)
    result_json: Mapped[dict] = mapped_column(JSONB)

    # 타임스탬프
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # 관계: 한 Run은 여러 파일을 가짐
    files: Mapped[list[EsgFile]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # 최신 실행 조회가 많으니 (draft_id, created_at) 인덱스가 유리
        Index("ix_esg_runs_draft_created", "draft_id", "created_at"),
    )


class EsgFile(Base):
    """
    업로드된 원본 파일 메타데이터를 저장하는 테이블.
    - /ai/agent/run에서 저장한 saved_files를 행(row)로 저장
    - 실제 파일 bytes는 디스크(tmp_uploads/...)에 있고, DB엔 경로/이름/종류만 저장
    """
    __tablename__ = "esg_files"

    # 내부 PK (있으면 관리/삭제 편함)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 어떤 run에서 올라온 파일인지
    run_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("esg_runs.run_id", ondelete="CASCADE"),
        index=True,
    )

    # 파일 식별/메타
    file_id: Mapped[str] = mapped_column(String(32), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(1024))
    ext: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(16))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # 관계: 파일은 한 Run에 속함
    run: Mapped[EsgRun] = relationship(back_populates="files")