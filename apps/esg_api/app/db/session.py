# app/db/session.py

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# uvicorn reload(서브프로세스)에서도 .env를 확실히 읽게 "경로 고정"
# session.py 위치: esg_api/app/db/session.py
# parents[2] == esg_api (프로젝트 루트)
_DOTENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_DOTENV_PATH, override=True)


class Base(DeclarativeBase):
    pass


def esg_get_database_url() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is missing. Put it in .env (project root) or export it.\n"
            "Example: postgresql+psycopg2://user:pw@127.0.0.1:5432/dbname"
        )
    return url


def _mask_url(url: str) -> str:
    # postgresql+psycopg2://user:pw@host/db -> pw만 마스킹
    if "://" not in url or "@" not in url:
        return url
    head, tail = url.split("://", 1)
    creds, rest = tail.split("@", 1)
    if ":" in creds:
        user, _pw = creds.split(":", 1)
        return f"{head}://{user}:***@{rest}"
    return url


def esg_make_engine():
    db_url = esg_get_database_url()
    echo = (os.getenv("DB_ECHO", "0").strip() == "1")

    pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))

    # ✅ 디버그: uvicorn이 실제로 어떤 DATABASE_URL을 쓰는지 확인
    print(f"[DB] Using DATABASE_URL={_mask_url(db_url)}")

    return create_engine(
        db_url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        future=True,
    )


ENGINE = esg_make_engine()

SessionLocal = sessionmaker(
    bind=ENGINE,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def esg_get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()