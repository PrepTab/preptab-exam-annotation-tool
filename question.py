from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func, text
from database import Base

class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    exam_id = Column(UUID(as_uuid=True), ForeignKey("exams.id"), nullable=False)
    number = Column(Integer, nullable=False)
    question = Column(JSONB, nullable=False)  # {"en": "...", "ha": "...", ...}
    options = Column(JSONB, nullable=False)   # {"A": "...", "B": "...", ...}
    answer = Column(Text, nullable=False)     # e.g., "A"
    explanation = Column(JSONB, nullable=True) # {"en": "...", ...}
    verbose = Column(JSONB, nullable=True) # {"en": "...", "ha": "...", ...}
    verbose_audio = Column(JSONB, nullable=True) # {"en": <BLOB>, "ha": <BLOB>, ...}
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Question(id={self .id}, number={self.number}, answer={self.answer})>"