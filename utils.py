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


def _get_env(name: str) -> Optional[str]:
    """Get env var from os.environ or Streamlit secrets."""
    v = os.getenv(name)
    if not v and hasattr(st, "secrets"):
        try:
            v = st.secrets.get(name, None)
        except Exception:
            v = None
    if v and str(v).strip():
        return str(v).strip()
    return None


# R2 (Cloudflare) – same var names as backend; used for direct upload from annotation tool
CLOUDFLARE_ACCESS_KEY_ID = _get_env("CLOUDFLARE_ACCESS_KEY_ID")
CLOUDFLARE_SECRET_ACCESS_KEY = _get_env("CLOUDFLARE_SECRET_ACCESS_KEY")
CLOUDFLARE_BUCKET_NAME = _get_env("CLOUDFLARE_BUCKET_NAME")
CLOUDFLARE_URL = _get_env("CLOUDFLARE_URL")
CLOUDFLARE_PUBLIC_URL = _get_env("CLOUDFLARE_PUBLIC_URL")


def r2_configured() -> bool:
    """True when required R2 env vars are set so image uploads work (same set as prepquiz_generator)."""
    return bool(
        _get_env("CLOUDFLARE_ACCESS_KEY_ID")
        and _get_env("CLOUDFLARE_SECRET_ACCESS_KEY")
        and _get_env("CLOUDFLARE_BUCKET_NAME")
        and _get_env("CLOUDFLARE_URL")
        and _get_env("CLOUDFLARE_PUBLIC_URL")
    )


# Create SYNCHRONOUS database engine for Streamlit
DATABASE_URL = os.getenv("DATABASE_URL") or (getattr(st, "secrets", None) or {}).get("DATABASE_URL")
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


def _parse_option_image_urls(val):
    """Parse option_image_urls from DB (dict, str, or None)."""
    if val is None:
        return None
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (TypeError, ValueError):
            return None
    return None


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
        
        # Create questions (include image fields so they persist in DB)
        for i, question_data in enumerate(questions, 1):
            q_img = (question_data.get('question_image_url') or '').strip() or None
            opt_urls_raw = question_data.get('option_image_urls') or {}
            opt_urls = {str(k): (v if isinstance(v, str) else str(v)).strip() for k, v in opt_urls_raw.items() if v and (v if isinstance(v, str) else str(v)).strip()}
            question = Question(
                exam_id=exam.id,
                number=i,
                question=question_data['question'],
                options=question_data['options'],
                answer=question_data['answer'],
                explanation=question_data['explanation'],
                verbose=question_data.get('verbose', {}) if ExamType(exam_data['exam_type']) == ExamType.PREPQUIZ else None,
                verbose_audio=question_data.get('verbose_audio') if ExamType(exam_data['exam_type']) == ExamType.PREPQUIZ else None,
                question_image_url=q_img,
                option_image_urls=opt_urls if opt_urls else None,
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
            q_img = getattr(q, 'question_image_url', None)
            opt_urls = _parse_option_image_urls(getattr(q, 'option_image_urls', None)) or {}
            # Normalize option_image_urls to string keys and non-empty values for display
            opt_urls = {str(k): (v if isinstance(v, str) else str(v)).strip() for k, v in opt_urls.items() if v}
            v_audio = getattr(q, 'verbose_audio', None)
            if isinstance(v_audio, str):
                try:
                    v_audio = json.loads(v_audio)
                except (TypeError, ValueError):
                    v_audio = None
            if not isinstance(v_audio, dict):
                v_audio = v_audio or {}
            question_list.append({
                'id': str(q.id),
                'number': q.number,
                'question': q.question if isinstance(q.question, dict) else json.loads(q.question) if isinstance(q.question, str) else {},
                'options': q.options if isinstance(q.options, dict) else json.loads(q.options) if isinstance(q.options, str) else {},
                'answer': q.answer,
                'explanation': q.explanation if isinstance(q.explanation, dict) else json.loads(q.explanation) if isinstance(q.explanation, str) else {},
                'verbose': q.verbose if isinstance(q.verbose, dict) else json.loads(q.verbose) if isinstance(q.verbose, str) else {},
                'verbose_audio': v_audio,
                'question_image_url': (q_img or '').strip() or None,
                'option_image_urls': opt_urls,
            })
        
        return question_list
    except Exception as e:
        st.error(f"Error fetching questions: {str(e)}")
        return []
    finally:
        db.close()


def update_question_in_db(question_id: str, question_data: Dict) -> bool:
    """Update a single question in the database."""
    db = SyncSessionLocal()
    try:
        query = select(Question).where(Question.id == uuid.UUID(question_id))
        result = db.execute(query)
        question = result.scalar_one_or_none()

        if question:
            # Determine exam type for this question
            exam_type = db.execute(
                select(Exam.exam_type).where(Exam.id == question.exam_id)
            ).scalar_one_or_none()

            question.question = question_data['question']
            question.options = question_data['options']
            question.answer = question_data['answer']
            question.explanation = question_data.get('explanation', {})

            # For PREPQUIZ questions, keep existing verbose/verbose_audio as-is.
            # For official exams (WAEC/NECO/JAMB), clear them to NULL.
            if exam_type != ExamType.PREPQUIZ:
                question.verbose = None
                question.verbose_audio = None

            q_img = (question_data.get('question_image_url') or '').strip() or None
            opt_urls_raw = question_data.get('option_image_urls') or {}
            opt_urls = {
                str(k): (v if isinstance(v, str) else str(v)).strip()
                for k, v in opt_urls_raw.items()
                if v and (v if isinstance(v, str) else str(v)).strip()
            }
            question.question_image_url = q_img
            question.option_image_urls = opt_urls if opt_urls else None

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
            
            # Fetch existing questions' verbose_audio (by number) before delete, so we can preserve when incoming is empty
            existing_query = select(Question.number, Question.verbose_audio).where(
                Question.exam_id == exam.id
            ).order_by(Question.number)
            existing_rows = db.execute(existing_query).all()
            existing_verbose_audio = {}
            for num, v_audio in existing_rows:
                if v_audio and isinstance(v_audio, dict) and v_audio:
                    existing_verbose_audio[num] = v_audio
                elif v_audio and isinstance(v_audio, str):
                    try:
                        parsed = json.loads(v_audio)
                        if isinstance(parsed, dict) and parsed:
                            existing_verbose_audio[num] = parsed
                    except (TypeError, ValueError):
                        pass
            
            # Delete existing questions
            db.execute(delete(Question).where(Question.exam_id == exam.id))
            
            # Add updated questions (include image + verbose_audio so they persist)
            for i, question_data in enumerate(questions, 1):
                q_img = (question_data.get('question_image_url') or '').strip() or None
                opt_urls_raw = question_data.get('option_image_urls') or {}
                opt_urls = {str(k): (v if isinstance(v, str) else str(v)).strip() for k, v in opt_urls_raw.items() if v and (v if isinstance(v, str) else str(v)).strip()}
                # Preserve existing verbose_audio when incoming is empty (avoid overwriting with {})
                verbose_audio = question_data.get('verbose_audio')
                if exam.exam_type == ExamType.PREPQUIZ:
                    if not verbose_audio or (isinstance(verbose_audio, dict) and not verbose_audio):
                        verbose_audio = existing_verbose_audio.get(i)
                else:
                    verbose_audio = None
                question = Question(
                    exam_id=exam.id,
                    number=i,
                    question=question_data['question'],
                    options=question_data['options'],
                    answer=question_data['answer'],
                    explanation=question_data['explanation'],
                    verbose=question_data.get('verbose', {}) if exam.exam_type == ExamType.PREPQUIZ else None,
                    verbose_audio=verbose_audio,
                    question_image_url=q_img,
                    option_image_urls=opt_urls if opt_urls else None,
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
        
        # Create new question (include image fields so they persist in DB)
        q_img = (question_data.get('question_image_url') or '').strip() or None
        opt_urls_raw = question_data.get('option_image_urls') or {}
        opt_urls = {str(k): (v if isinstance(v, str) else str(v)).strip() for k, v in opt_urls_raw.items() if v and (v if isinstance(v, str) else str(v)).strip()}
        question = Question(
            exam_id=uuid.UUID(exam_id),
            number=max_number + 1,
            question=question_data['question'],
            options=question_data['options'],
            answer=question_data['answer'],
            explanation=question_data.get('explanation', {}),
            verbose=question_data.get('verbose', {}),
            question_image_url=q_img,
            option_image_urls=opt_urls if opt_urls else None,
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


async def _upload_media_to_r2_async(
    file_paths_with_meta: List[tuple],
    endpoint_url: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    public_url_base: str,
) -> Optional[List[str]]:
    """
    Async upload to R2 — same as prepquiz_generator/storage.py: aioboto3, upload_file, head_object.
    file_paths_with_meta: list of (file_path, content_type, object_name).
    """
    import aioboto3

    session = aioboto3.Session()
    async with session.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    ) as s3:
        urls = []
        for file_path, content_type, object_name in file_paths_with_meta:
            await s3.upload_file(
                file_path,
                bucket,
                object_name,
                ExtraArgs={
                    "ContentType": content_type,
                    "ACL": "public-read",
                },
            )
            await s3.head_object(Bucket=bucket, Key=object_name)
            public_url = f"{public_url_base}/{bucket}/{object_name}"
            urls.append(public_url)
        return urls


def upload_media_to_r2(files: List) -> Optional[List[str]]:
    """
    Upload files to Cloudflare R2 — same as prepquiz_generator/storage.py (async aioboto3).
    Writes to temp files, runs async upload via asyncio.run(), returns public URLs or None.
    """
    import asyncio
    import tempfile

    CLOUDFLARE_URL = _get_env("CLOUDFLARE_URL")
    CLOUDFLARE_ACCESS_KEY_ID = _get_env("CLOUDFLARE_ACCESS_KEY_ID")
    CLOUDFLARE_SECRET_ACCESS_KEY = _get_env("CLOUDFLARE_SECRET_ACCESS_KEY")
    CLOUDFLARE_BUCKET_NAME = _get_env("CLOUDFLARE_BUCKET_NAME")
    CLOUDFLARE_PUBLIC_URL = _get_env("CLOUDFLARE_PUBLIC_URL")

    required = [CLOUDFLARE_URL, CLOUDFLARE_ACCESS_KEY_ID, CLOUDFLARE_SECRET_ACCESS_KEY, CLOUDFLARE_BUCKET_NAME, CLOUDFLARE_PUBLIC_URL]
    if not all(required):
        try:
            st.session_state["upload_error"] = "Missing R2 config: set all CLOUDFLARE_* env vars (same as prepquiz_generator)."
        except Exception:
            pass
        return None

    file_paths_with_meta = []
    temp_paths = []
    try:
        for i, f in enumerate(files):
            if hasattr(f, "read"):
                name = getattr(f, "name", None) or getattr(f, "filename", None) or f"file_{i}"
                if hasattr(f, "seek"):
                    f.seek(0)
                content = f.read()
                if not isinstance(content, bytes):
                    content = bytes(content) if content else b""
                if not content:
                    try:
                        st.session_state["upload_error"] = f"File '{name}' was empty."
                    except Exception:
                        pass
                    return None
            elif isinstance(f, (list, tuple)) and len(f) >= 2:
                name, content = f[0], f[1]
                if not isinstance(content, bytes):
                    content = bytes(content) if content else b""
            else:
                continue

            ext = ""
            if name and "." in str(name):
                ext = "." + str(name).rsplit(".", 1)[-1].lower()
            object_name = f"media/{uuid.uuid4()}{ext}"

            content_type = "image/png"
            if ext in (".jpg", ".jpeg"):
                content_type = "image/jpeg"
            elif ext == ".gif":
                content_type = "image/gif"
            elif ext == ".webp":
                content_type = "image/webp"

            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(content)
                file_path = tmp.name
            temp_paths.append(file_path)
            file_paths_with_meta.append((file_path, content_type, object_name))

        if not file_paths_with_meta:
            return None

        urls = asyncio.run(
            _upload_media_to_r2_async(
                file_paths_with_meta,
                CLOUDFLARE_URL,
                CLOUDFLARE_ACCESS_KEY_ID,
                CLOUDFLARE_SECRET_ACCESS_KEY,
                CLOUDFLARE_BUCKET_NAME,
                CLOUDFLARE_PUBLIC_URL.rstrip("/"),
            )
        )
        return urls
    except Exception as e:
        try:
            st.session_state["upload_error"] = f"{type(e).__name__}: {e}"
        except Exception:
            pass
        return None
    finally:
        for path in temp_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass


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



