"""
Utility functions for the Exam Annotation Tool
Handles database operations and helper functions
"""
import json
from typing import Dict, List, Optional
from datetime import datetime
import uuid
import os
from dotenv import load_dotenv
import streamlit as st

from exam import Exam, ExamType
from question import Question
from sqlalchemy import create_engine, select, text, func, delete
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

# Create SYNCHRONOUS database engine for Streamlit
DATABASE_URL = os.getenv("DATABASE_URL") or st.secrets.get("DATABASE_URL")
# Convert async URL to sync URL
if DATABASE_URL and DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

# Create sync engine
sync_engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,
)

# Create sync session maker
SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False
)


# Helper functions
def datetime_encoder(obj):
    """Custom JSON encoder for datetime objects"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def validate_question(question_data: Dict) -> List[str]:
    """Validate question data and return list of errors"""
    errors = []
    
    # Check if question text is provided in at least English
    if not question_data['question']['en'].strip():
        errors.append("Question text in English is required")
    
    # Check if all options are provided
    for option in ['A', 'B', 'C', 'D']:
        if not question_data['options'][option].strip():
            errors.append(f"Option {option} is required")
    
    # Check if answer is selected
    if not question_data['answer']:
        errors.append("Correct answer must be selected")
    
    # Check if explanation is provided in at least English
    if not question_data['explanation']['en'].strip():
        errors.append("Explanation in English is required")
    
    return errors


# Database operations
def save_exam_to_database(exam_data: Dict, questions: List[Dict]) -> Optional[str]:
    """Save exam and questions to database"""
    db = SyncSessionLocal()
    try:
        # Create exam
        exam = Exam(
            exam_type=ExamType(exam_data['exam_type']),
            subject=exam_data['subject'],
            year=exam_data['year'],
            title=exam_data['title'],
            duration=exam_data['duration']
        )
        
        db.add(exam)
        db.flush()  # Get the exam ID
        
        # Create questions
        for i, question_data in enumerate(questions, 1):
            question = Question(
                exam_id=exam.id,
                number=i,
                question=question_data['question'],
                options=question_data['options'],
                answer=question_data['answer'],
                explanation=question_data['explanation'],
                verbose=question_data['verbose']
            )
            db.add(question)
        
        db.commit()
        return str(exam.id)
            
    except Exception as e:
        db.rollback()
        st.error(f"Error saving to database: {str(e)}")
        return None
    finally:
        db.close()


def fetch_all_exams(
    exam_type: Optional[str] = None,
    subject: Optional[str] = None,
    year: Optional[int] = None,
    search_title: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict]:
    """Fetch all exams from database with optional filters"""
    db = SyncSessionLocal()
    try:
        query = select(Exam)
        
        # Apply filters
        if exam_type:
            query = query.where(Exam.exam_type == ExamType(exam_type))
        if subject:
            query = query.where(Exam.subject == subject)
        if year:
            query = query.where(Exam.year == year)
        if search_title:
            query = query.where(Exam.title.ilike(f"%{search_title}%"))
        
        # Order by created_at descending
        query = query.order_by(Exam.created_at.desc())
        
        # Apply pagination
        query = query.limit(limit).offset(offset)
        
        result = db.execute(query)
        exams = result.scalars().all()
        
        # Get question counts for each exam
        exam_list = []
        for exam in exams:
            # Count questions for this exam
            count_query = select(func.count(Question.id)).where(Question.exam_id == exam.id)
            count_result = db.execute(count_query)
            question_count = count_result.scalar() or 0
            
            exam_list.append({
                'id': str(exam.id),
                'exam_type': exam.exam_type.value if exam.exam_type else None,
                'subject': exam.subject,
                'year': exam.year,
                'title': exam.title,
                'duration': exam.duration,
                'created_at': exam.created_at.isoformat() if exam.created_at else None,
                'question_count': question_count
            })
        
        return exam_list
    except Exception as e:
        st.error(f"Error fetching exams: {str(e)}")
        return []
    finally:
        db.close()


def fetch_exam_by_id(exam_id: str) -> Optional[Dict]:
    """Fetch a single exam by ID"""
    db = SyncSessionLocal()
    try:
        query = select(Exam).where(Exam.id == uuid.UUID(exam_id))
        result = db.execute(query)
        exam = result.scalar_one_or_none()
        
        if exam:
            return {
                'id': str(exam.id),
                'exam_type': exam.exam_type.value if exam.exam_type else None,
                'subject': exam.subject,
                'year': exam.year,
                'title': exam.title,
                'duration': exam.duration,
                'created_at': exam.created_at.isoformat() if exam.created_at else None
            }
        return None
    except Exception as e:
        st.error(f"Error fetching exam: {str(e)}")
        return None
    finally:
        db.close()


def fetch_exam_questions(exam_id: str) -> List[Dict]:
    """Fetch all questions for a specific exam"""
    db = SyncSessionLocal()
    try:
        query = select(Question).where(Question.exam_id == uuid.UUID(exam_id)).order_by(Question.number)
        result = db.execute(query)
        questions = result.scalars().all()
        
        question_list = []
        for q in questions:
            question_list.append({
                'id': str(q.id),
                'number': q.number,
                'question': q.question if isinstance(q.question, dict) else json.loads(q.question) if isinstance(q.question, str) else {},
                'options': q.options if isinstance(q.options, dict) else json.loads(q.options) if isinstance(q.options, str) else {},
                'answer': q.answer,
                'explanation': q.explanation if isinstance(q.explanation, dict) else json.loads(q.explanation) if isinstance(q.explanation, str) else {},
                'verbose': q.verbose if isinstance(q.verbose, dict) else json.loads(q.verbose) if isinstance(q.verbose, str) else {}
            })
        
        return question_list
    except Exception as e:
        st.error(f"Error fetching questions: {str(e)}")
        return []
    finally:
        db.close()


def update_question_in_db(question_id: str, question_data: Dict) -> bool:
    """Update a single question in the database"""
    db = SyncSessionLocal()
    try:
        query = select(Question).where(Question.id == uuid.UUID(question_id))
        result = db.execute(query)
        question = result.scalar_one_or_none()
        
        if question:
            question.question = question_data['question']
            question.options = question_data['options']
            question.answer = question_data['answer']
            question.explanation = question_data.get('explanation', {})
            question.verbose = question_data.get('verbose', {})
            
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        st.error(f"Error updating question: {str(e)}")
        return False
    finally:
        db.close()


def update_exam_in_db(exam_id: str, exam_data: Dict, questions: List[Dict]) -> bool:
    """Update exam metadata and questions in the database"""
    db = SyncSessionLocal()
    try:
        # Update exam
        query = select(Exam).where(Exam.id == uuid.UUID(exam_id))
        result = db.execute(query)
        exam = result.scalar_one_or_none()
        
        if exam:
            exam.exam_type = ExamType(exam_data['exam_type'])
            exam.subject = exam_data['subject']
            exam.year = exam_data['year']
            exam.title = exam_data['title']
            exam.duration = exam_data['duration']
            
            # Delete existing questions
            db.execute(delete(Question).where(Question.exam_id == exam.id))
            
            # Add updated questions
            for i, question_data in enumerate(questions, 1):
                question = Question(
                    exam_id=exam.id,
                    number=i,
                    question=question_data['question'],
                    options=question_data['options'],
                    answer=question_data['answer'],
                    explanation=question_data['explanation'],
                    verbose=question_data['verbose']
                )
                db.add(question)
            
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        st.error(f"Error updating exam: {str(e)}")
        return False
    finally:
        db.close()


def delete_exam_from_db(exam_id: str) -> bool:
    """Delete an exam and all its questions from the database"""
    db = SyncSessionLocal()
    try:
        # Delete questions first (cascade should handle this, but being explicit)
        db.execute(delete(Question).where(Question.exam_id == uuid.UUID(exam_id)))
        
        # Delete exam
        db.execute(delete(Exam).where(Exam.id == uuid.UUID(exam_id)))
        
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        st.error(f"Error deleting exam: {str(e)}")
        return False
    finally:
        db.close()


def delete_question_from_db(question_id: str) -> bool:
    """Delete a single question from the database"""
    db = SyncSessionLocal()
    try:
        db.execute(delete(Question).where(Question.id == uuid.UUID(question_id)))
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        st.error(f"Error deleting question: {str(e)}")
        return False
    finally:
        db.close()


def add_question_to_exam(exam_id: str, question_data: Dict) -> bool:
    """Add a new question to an existing exam"""
    db = SyncSessionLocal()
    try:
        # Get the current max question number for this exam
        query = select(func.max(Question.number)).where(Question.exam_id == uuid.UUID(exam_id))
        result = db.execute(query)
        max_number = result.scalar() or 0
        
        # Create new question
        question = Question(
            exam_id=uuid.UUID(exam_id),
            number=max_number + 1,
            question=question_data['question'],
            options=question_data['options'],
            answer=question_data['answer'],
            explanation=question_data.get('explanation', {}),
            verbose=question_data.get('verbose', {})
        )
        
        db.add(question)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        st.error(f"Error adding question: {str(e)}")
        return False
    finally:
        db.close()


def test_database_connection() -> bool:
    """Test database connection"""
    db = SyncSessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        db.close()

