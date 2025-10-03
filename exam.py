from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func, text
from enum import Enum
from database import Base
from question import Question

class ExamType(str, Enum):
    WAEC = "WAEC"
    NECO = "NECO"
    JAMB = "JAMB"
    PREPQUIZ = "PREPQUIZ"

class Exam(Base):
    __tablename__ = "exams"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    exam_type = Column(SQLEnum(ExamType), nullable=False)
    subject = Column(String(100), nullable=False)
    year = Column(Integer, nullable=True)
    title = Column(String(255), nullable=True)
    duration = Column(Integer, nullable=True)  # in minutes
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Exam(id={self.id}, type={self.exam_type}, subject={self.subject}, year={self.year}, title={self.title})>"