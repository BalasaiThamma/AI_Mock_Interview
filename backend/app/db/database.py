import json
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, Text, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from app.core.config import settings

def custom_json_serializer(obj):
    return json.dumps(obj, default=str)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    json_serializer=custom_json_serializer
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class InterviewSessionModel(Base):
    __tablename__ = "interview_sessions"

    interview_id = Column(String(64), primary_key=True, index=True)
    candidate_id = Column(String(64), index=True)
    job_id = Column(String(64), index=True)
    status = Column(String(32), default="CREATED", index=True)
    mode = Column(String(16), default="text")
    interview_type = Column(String(32), default="technical")
    config = Column(JSON, default=dict)
    candidate_context = Column(JSON, default=dict)
    job_context = Column(JSON, default=dict)
    state = Column(JSON, default=dict)
    questions = Column(JSON, default=list)
    answers = Column(JSON, default=list)
    evaluations = Column(JSON, default=list)
    report = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
