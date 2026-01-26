# app/db/session.py

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def esg_get_database_url() -> str:
    """
    DB 연결은 무조건 DATABASE_URL 한 줄로 통제한다.
    - 로컬: postgresql+psycopg2://esg:esg_pw@127.0.0.1:5433/esg_db
    - Azure: postgresql+psycopg2://...@...:5432/... ?sslmode=require
    """
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


DATABASE_URL = esg_get_database_url()
print(f"[DB] Using DATABASE_URL={DATABASE_URL.replace(DATABASE_URL.split(':')[2].split('@')[0], '***') if '@' in DATABASE_URL else DATABASE_URL}")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def esg_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()