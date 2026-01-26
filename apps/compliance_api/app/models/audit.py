# app/models/audit.py
from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.db.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255))
    risk_score = Column(Integer)
    summary = Column(Text)
    feedback_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)