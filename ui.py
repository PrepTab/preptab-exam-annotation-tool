import streamlit as st
import json
from typing import Dict, List, Optional
from datetime import datetime

# Import from local modules
from exam import ExamType
from utils import (
    datetime_encoder,
    validate_question,
    save_exam_to_database,
    fetch_all_exams,
    fetch_exam_by_id,
    fetch_exam_questions,
    update_question_in_db,
    update_exam_in_db,
    delete_exam_from_db,
    delete_question_from_db,
    add_question_to_exam,
    test_database_connection,
    upload_media_to_r2,
    r2_configured,
)

# Import localStorage functionality
from streamlit_local_storage import LocalStorage

# Page configuration
st.set_page_config(
    page_title="Exam Annotation Tool",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize LocalStorage
if 'localS' not in st.session_state:
    st.session_state.localS = LocalStorage()

# LocalStorage keys
EXAM_DATA_KEY = "preptab_exam_data"
QUESTIONS_KEY = "preptab_questions"

# Available subjects
SUBJECTS = [
    "Mathematics",
    "English",
    "Physics",
    "Chemistry",
    "Biology",
    "Government",
    "Computer Science",
    "Agricultural Science",
    "History",
    "Animal Husbandry",
    "Data Processing",
    "Economics",
    "Civic Education",
    "Geography",
    "Literature in English"
]

# Available years (2015 to 2025)
EXAM_YEARS = list(range(2015, 2026))  # 2015 to 2025 inclusive

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2c3e50;
        margin-top: 2rem;
        margin-bottom: 1rem;
        border-bottom: 2px solid #3498db;
        padding-bottom: 0.5rem;
    }
    .question-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        background-color: #f8f9fa;
    }
    .success-message {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem;
        border-radius: 4px;
        margin: 1rem 0;
    }
    .error-message {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 1rem;
        border-radius: 4px;
        margin: 1rem 0;
    }
    .auto-save-indicator {
        font-size: 0.85rem;
        color: #6c757d;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions for localStorage
def generate_exam_title():
    """Generate exam title from exam_type, subject, and year"""
    exam_type = st.session_state.exam_data.get('exam_type', '')
    subject = st.session_state.exam_data.get('subject', '')
    year = st.session_state.exam_data.get('year', '')
    
    if exam_type and subject and year:
        return f"{exam_type} {subject} {year}"
    return ""

def update_exam_title():
    """Update exam title when exam details change"""
    st.session_state.exam_data['title'] = generate_exam_title()

def save_exam_to_storage():
    """Save exam data and questions to localStorage"""
    try:
        # Update title before saving
        update_exam_title()
        
        # Set flag to trigger save on next render
        st.session_state.auto_saved = True
        st.session_state.needs_save = True
        
        # Store last save time for debugging
        st.session_state.last_save_time = datetime.now().isoformat()
        
    except Exception as e:
        # Log error but don't break the app
        st.session_state.storage_error = str(e)
        pass

def load_exam_from_storage():
    """Load exam data and questions from localStorage"""
    try:
        # Use unique keys for each getItem call
        # The library stores results in session_state with the key parameter
        exam_data_key = f"load_{EXAM_DATA_KEY}"
        questions_key = f"load_{QUESTIONS_KEY}"
        
        # Call getItem - the value will be stored in session_state after component renders
        # Based on library docs, getItem(itemKey, key="session_state_key")
        # But if key parameter doesn't work, we'll use a different approach
        exam_data_result = st.session_state.localS.getItem(EXAM_DATA_KEY)
        questions_result = st.session_state.localS.getItem(QUESTIONS_KEY)
        
        # Check if we got results directly or need to check session_state
        exam_data_loaded = False
        questions_loaded = False
        
        # Try direct result first
        if exam_data_result:
            try:
                if isinstance(exam_data_result, str) and exam_data_result.strip() and exam_data_result != "null":
                    exam_data = json.loads(exam_data_result)
                    st.session_state.exam_data = exam_data
                    exam_data_loaded = True
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
        
        if questions_result:
            try:
                if isinstance(questions_result, str) and questions_result.strip() and questions_result != "null":
                    questions = json.loads(questions_result)
                    st.session_state.questions = questions
                    questions_loaded = True
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
        
        return exam_data_loaded or questions_loaded
    except Exception as e:
        # Silently fail if localStorage is unavailable or data is invalid
        pass
    return False

def clear_exam_storage():
    """Clear exam-related data from localStorage"""
    try:
        # Use unique keys to ensure the clear components render
        if 'clear_counter' not in st.session_state:
            st.session_state.clear_counter = 0
        st.session_state.clear_counter += 1
        
        # Clear by setting empty strings - these need to render to work
        st.session_state.localS.setItem(EXAM_DATA_KEY, "", key=f"clear_exam_{st.session_state.clear_counter}")
        st.session_state.localS.setItem(QUESTIONS_KEY, "", key=f"clear_questions_{st.session_state.clear_counter}")
    except Exception as e:
        # Silently fail if localStorage is unavailable
        pass

# Initialize session state - set defaults first
if 'exam_data' not in st.session_state:
    # Default year to 2025 (most recent in range) or current year if in range
    default_year = min(datetime.now().year, max(EXAM_YEARS)) if datetime.now().year <= max(EXAM_YEARS) else max(EXAM_YEARS)
    st.session_state.exam_data = {
        'exam_type': None,
        'subject': '',
        'year': default_year,
        'title': '',
        'duration': 60
    }

if 'questions' not in st.session_state:
    st.session_state.questions = []

if 'current_question' not in st.session_state:
    st.session_state.current_question = {
        'question': {'en': '', 'ha': '', 'ig': '', 'yo': ''},
        'options': {'A': '', 'B': '', 'C': '', 'D': ''},
        'answer': 'A',
        'explanation': {'en': '', 'ha': '', 'ig': '', 'yo': ''},
        'verbose': {'en': '', 'ha': '', 'ig': '', 'yo': ''},
        'question_image_url': None,
        'option_image_urls': {},
    }

# Initialize editing state
if 'editing_exam_id' not in st.session_state:
    st.session_state.editing_exam_id = None

if 'viewing_exam_id' not in st.session_state:
    st.session_state.viewing_exam_id = None

# Key for file uploaders; bump after save/update so widgets remount and clear
if 'file_upload_key' not in st.session_state:
    st.session_state.file_upload_key = 0

# Helper functions
def reset_current_question():
    """Reset the current question form"""
    st.session_state.current_question = {
        'question': {'en': '', 'ha': '', 'ig': '', 'yo': ''},
        'options': {'A': '', 'B': '', 'C': '', 'D': ''},
        'answer': 'A',
        'explanation': {'en': '', 'ha': '', 'ig': '', 'yo': ''},
        'verbose': {'en': '', 'ha': '', 'ig': '', 'yo': ''},
        'question_image_url': None,
        'option_image_urls': {},
    }
    # Clear upload tracking so next question can upload fresh
    st.session_state.pop("_q_img_uploaded", None)
    for opt in ["A", "B", "C", "D"]:
        st.session_state.pop(f"_opt_img_uploaded_{opt}", None)

# Main interface
def main():
    # Initialize localStorage components (they need to render to work)
    # Call getItem to load data from localStorage - it returns the value directly
    if 'localstorage_initialized' not in st.session_state:
        # Try to load data from localStorage
        try:
            exam_data_result = st.session_state.localS.getItem(EXAM_DATA_KEY)
            questions_result = st.session_state.localS.getItem(QUESTIONS_KEY)
            
            # Process exam_data
            if exam_data_result and isinstance(exam_data_result, str) and exam_data_result.strip() and exam_data_result != "null":
                try:
                    exam_data = json.loads(exam_data_result)
                    if exam_data and exam_data != st.session_state.get('exam_data'):
                        st.session_state.exam_data = exam_data
                        if 'data_restored_shown' not in st.session_state:
                            st.session_state.data_restored_shown = True
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Process questions
            if questions_result and isinstance(questions_result, str) and questions_result.strip() and questions_result != "null":
                try:
                    questions = json.loads(questions_result)
                    if questions and questions != st.session_state.get('questions'):
                        st.session_state.questions = questions
                        if 'data_restored_shown' not in st.session_state:
                            st.session_state.data_restored_shown = True
                except (json.JSONDecodeError, TypeError):
                    pass
            
            st.session_state.localstorage_initialized = True
        except Exception as e:
            # Silently fail if localStorage is unavailable
            st.session_state.localstorage_initialized = True
            pass
    
    # Show restoration message if data was loaded from localStorage
    if st.session_state.get('data_restored_shown', False) and not st.session_state.get('restore_message_shown', False):
        st.info("📥 Restored exam data from browser storage. You can continue where you left off!")
        st.session_state.restore_message_shown = True
        st.session_state.data_restored_shown = False  # Reset flag
    
    st.markdown('<h1 class="main-header">📝 Exam Annotation Tool</h1>', unsafe_allow_html=True)
    
    # Setup navigation using st.navigation
    pages = [
        st.Page(create_exam_page, title="Create Exam"),
        st.Page(browse_exams_page, title="Browse Exams"),
        st.Page(view_questions_page, title="View Questions"),
        st.Page(database_status_page, title="Database Status")
    ]
    
    pg = st.navigation(pages, position="sidebar")
    pg.run()

def create_exam_page():
    # Save to localStorage at the start if needed (before any UI that might cause rerun)
    if st.session_state.get('needs_save', False):
        try:
            update_exam_title()
            exam_data_json = json.dumps(st.session_state.exam_data, default=datetime_encoder)
            questions_json = json.dumps(st.session_state.questions, default=datetime_encoder)
            
            if 'save_counter' not in st.session_state:
                st.session_state.save_counter = 0
            st.session_state.save_counter += 1
            
            st.session_state.localS.setItem(
                EXAM_DATA_KEY, 
                exam_data_json, 
                key=f"save_exam_{st.session_state.save_counter}"
            )
            st.session_state.localS.setItem(
                QUESTIONS_KEY, 
                questions_json, 
                key=f"save_questions_{st.session_state.save_counter}"
            )
            st.session_state.needs_save = False
        except Exception:
            pass
    
    # Show editing mode indicator
    if st.session_state.get('editing_exam_id'):
        st.info(f"📝 **Editing Mode:** You are editing an existing exam. Changes will update the exam in the database.")
        if st.button("❌ Cancel Editing", type="secondary"):
            st.session_state.editing_exam_id = None
            default_year = min(datetime.now().year, max(EXAM_YEARS)) if datetime.now().year <= max(EXAM_YEARS) else max(EXAM_YEARS)
            st.session_state.exam_data = {
                'exam_type': None,
                'subject': '',
                'year': default_year,
                'title': '',
                'duration': 60
            }
            st.session_state.questions = []
            reset_current_question()
            st.rerun()
    
    st.markdown('<h2 class="section-header">Exam Details</h2>', unsafe_allow_html=True)
    
    # Exam details form
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Get current exam_type index
        exam_type_options = [e.value for e in ExamType]
        current_exam_type = st.session_state.exam_data.get('exam_type')
        exam_type_index = exam_type_options.index(current_exam_type) if current_exam_type in exam_type_options else 0
        
        exam_type = st.selectbox(
            "Exam Type",
            options=exam_type_options,
            index=exam_type_index,
            help="Select the type of exam you're creating",
            on_change=save_exam_to_storage
        )
        st.session_state.exam_data['exam_type'] = exam_type
    
    with col2:
        # Get current subject index
        current_subject = st.session_state.exam_data.get('subject', '')
        subject_index = SUBJECTS.index(current_subject) if current_subject in SUBJECTS else 0
        
        subject = st.selectbox(
            "Subject",
            options=SUBJECTS,
            index=subject_index,
            help="Select the subject for this exam",
            on_change=save_exam_to_storage
        )
        st.session_state.exam_data['subject'] = subject
    
    with col3:
        # Get current year index
        default_year = min(datetime.now().year, max(EXAM_YEARS)) if datetime.now().year <= max(EXAM_YEARS) else max(EXAM_YEARS)
        current_year = st.session_state.exam_data.get('year', default_year)
        year_index = EXAM_YEARS.index(current_year) if current_year in EXAM_YEARS else len(EXAM_YEARS) - 1
        
        year = st.selectbox(
            "Year",
            options=EXAM_YEARS,
            index=year_index,
            help="Select the year for this exam",
            on_change=save_exam_to_storage
        )
        st.session_state.exam_data['year'] = year
    
    # Auto-generate and display title
    exam_title = generate_exam_title()
    st.session_state.exam_data['title'] = exam_title
    
    if exam_title:
        st.info(f"**Exam Title:** {exam_title}")
    
    # Duration
    duration = st.number_input(
        "Duration (minutes)",
        min_value=15,
        max_value=300,
        value=st.session_state.exam_data.get('duration', 60),
        help="Enter the duration in minutes",
        on_change=save_exam_to_storage
    )
    st.session_state.exam_data['duration'] = duration
    
    # Auto-save indicator
    if st.session_state.get('auto_saved', False):
        st.markdown('<p class="auto-save-indicator">💾 Auto-saved to browser storage</p>', unsafe_allow_html=True)
    
    # Always render localStorage save components when data changes
    # Streamlit components need to be in the render flow to work
    if st.session_state.get('needs_save', False):
        try:
            exam_data_json = json.dumps(st.session_state.exam_data, default=datetime_encoder)
            questions_json = json.dumps(st.session_state.questions, default=datetime_encoder)
            
            # Use a counter to ensure unique keys for each render (required for components)
            if 'save_counter' not in st.session_state:
                st.session_state.save_counter = 0
            st.session_state.save_counter += 1
            
            # Render the localStorage components - they need to be in the UI flow
            with st.container():
                # These will render invisibly but will save to localStorage
                st.session_state.localS.setItem(
                    EXAM_DATA_KEY, 
                    exam_data_json, 
                    key=f"persist_exam_{st.session_state.save_counter}"
                )
                st.session_state.localS.setItem(
                    QUESTIONS_KEY, 
                    questions_json, 
                    key=f"persist_questions_{st.session_state.save_counter}"
                )
            
            # Reset the flag after rendering
            st.session_state.needs_save = False
        except Exception as e:
            # Silently handle errors
            st.session_state.needs_save = False
            pass
    
    st.markdown('<h2 class="section-header">Add Question</h2>', unsafe_allow_html=True)
    
    # Show success message if question was just added
    if st.session_state.get('question_added_success', False):
        total_questions = len(st.session_state.questions)
        st.success(f"✅ Question {total_questions} added successfully! Total questions: {total_questions}")
        st.session_state.question_added_success = False  # Reset flag after showing
    
    # Images: upload → URL stored for question payload (internal tool, minimal labels)
    if st.session_state.get("upload_error"):
        st.error("Upload failed: " + st.session_state["upload_error"])
    if not r2_configured():
        st.caption("Set CLOUDFLARE_* env vars to enable image uploads.")
    MAX_FILE_BYTES = 300 * 1024  # 300 KB
    _uk = st.session_state.file_upload_key
    q_upload = st.file_uploader(
        "Q",
        type=["png", "jpg", "jpeg", "gif", "webp"],
        key=f"q_img_upload_{_uk}",
        help="",
    )
    if q_upload is not None and r2_configured():
        if getattr(q_upload, "size", 0) > MAX_FILE_BYTES:
            st.session_state["upload_error"] = "File must be 300 KB or smaller."
        else:
            last = st.session_state.get("_q_img_uploaded")
            if last != q_upload.name:
                with st.spinner("Uploading..."):
                    urls = upload_media_to_r2([q_upload])
                if urls and urls[0]:
                    st.session_state.current_question["question_image_url"] = urls[0]
                    st.session_state["_q_img_uploaded"] = q_upload.name
                    st.session_state.pop("upload_error", None)
                    # Don't rerun: allow form submit (Add/Update) to process in same run
            # else: upload_error already set; shown at top above
    if st.session_state.current_question.get("question_image_url"):
        col_img, col_clear = st.columns([3, 1])
        with col_img:
            st.image(st.session_state.current_question["question_image_url"], width=180)
        with col_clear:
            if st.button("Clear", key="rm_q_img"):
                st.session_state.current_question["question_image_url"] = None
                st.session_state.pop("_q_img_uploaded", None)
                st.rerun()

    opt_uploads = {}
    c1, c2, c3, c4 = st.columns(4)
    for i, opt in enumerate(["A", "B", "C", "D"]):
        with [c1, c2, c3, c4][i]:
            opt_uploads[opt] = st.file_uploader(
                opt,
                type=["png", "jpg", "jpeg", "gif", "webp"],
                key=f"opt_upload_{opt}_{_uk}",
                help="",
            )
    if r2_configured():
        for opt in ["A", "B", "C", "D"]:
            f = opt_uploads.get(opt)
            if f is not None:
                if getattr(f, "size", 0) > MAX_FILE_BYTES:
                    st.session_state["upload_error"] = f"Option {opt}: file must be 300 KB or smaller."
                else:
                    last = st.session_state.get(f"_opt_img_uploaded_{opt}")
                    if last != f.name:
                        with st.spinner("Uploading..."):
                            urls = upload_media_to_r2([f])
                        if urls and urls[0]:
                            if "option_image_urls" not in st.session_state.current_question:
                                st.session_state.current_question["option_image_urls"] = {}
                            st.session_state.current_question["option_image_urls"][opt] = urls[0]
                            st.session_state[f"_opt_img_uploaded_{opt}"] = f.name
                            st.session_state.pop("upload_error", None)
                            # Don't rerun: allow form submit (Add/Update) to process in same run
                    # else: upload_error already set; shown at top
    # Show option thumbnails in a row
    opt_urls = st.session_state.current_question.get("option_image_urls") or {}
    if any(opt_urls.get(o) for o in ["A", "B", "C", "D"]):
        o1, o2, o3, o4 = st.columns(4)
        for i, opt in enumerate(["A", "B", "C", "D"]):
            with [o1, o2, o3, o4][i]:
                if opt_urls.get(opt):
                    st.image(opt_urls[opt], caption=opt, width=100)
                    if st.button("Clear", key=f"rm_opt_{opt}"):
                        st.session_state.current_question.setdefault("option_image_urls", {}).pop(opt, None)
                        st.session_state.pop(f"_opt_img_uploaded_{opt}", None)
                        st.rerun()
    
    st.markdown("**Question details**")
    # Question form
    with st.form("question_form", clear_on_submit=True):
        
        question_en = st.text_area(
            "Question",
            value=st.session_state.current_question['question']['en'],
            placeholder="Enter the question",
            height=100,
            help="Enter the question text"
        )
        st.session_state.current_question['question']['en'] = question_en
        
        col1, col2 = st.columns(2)
        
        with col1:
            option_a = st.text_input(
                "Option A",
                value=st.session_state.current_question['options']['A'],
                placeholder="Enter option A"
            )
            st.session_state.current_question['options']['A'] = option_a
            
            option_b = st.text_input(
                "Option B",
                value=st.session_state.current_question['options']['B'],
                placeholder="Enter option B"
            )
            st.session_state.current_question['options']['B'] = option_b
        
        with col2:
            option_c = st.text_input(
                "Option C",
                value=st.session_state.current_question['options']['C'],
                placeholder="Enter option C"
            )
            st.session_state.current_question['options']['C'] = option_c
            
            option_d = st.text_input(
                "Option D",
                value=st.session_state.current_question['options']['D'],
                placeholder="Enter option D"
            )
            st.session_state.current_question['options']['D'] = option_d
        
        # Correct answer
        st.markdown("**Correct Answer**")
        correct_answer = st.pills(
            "Select the correct answer",
            options=['A', 'B', 'C', 'D'],
            default=st.session_state.current_question['answer'],
            selection_mode="single",
            help="Select the correct answer",
            label_visibility="collapsed"
        )
        if correct_answer:
            st.session_state.current_question['answer'] = correct_answer
        else:
            st.session_state.current_question['answer'] = 'A'  # Default to 'A' if None
        
        explanation_en = st.text_area(
            "Explanation",
            value=st.session_state.current_question['explanation']['en'],
            placeholder="Explain why this answer is correct",
            height=100,
            help="Enter the explanation for the correct answer"
        )
        st.session_state.current_question['explanation']['en'] = explanation_en

        # Form buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            add_question = st.form_submit_button("➕ Add Question", type="primary")
        
        with col2:
            clear_form = st.form_submit_button("🗑️ Clear Form")
        
        with col3:
            if st.session_state.get('editing_exam_id'):
                save_exam = st.form_submit_button("🔄 Update Exam in Database", type="primary")
            else:
                save_exam = st.form_submit_button("💾 Save Exam to Database", type="secondary")
        
        # Handle form submissions
        if add_question:
            # Validate question
            errors = validate_question(st.session_state.current_question)
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                # Add question to list (preserve verbose_audio if present, e.g. after load-for-edit)
                question_copy = {
                    'question': st.session_state.current_question['question'].copy(),
                    'options': st.session_state.current_question['options'].copy(),
                    'answer': st.session_state.current_question['answer'],
                    'explanation': st.session_state.current_question['explanation'].copy(),
                    'verbose': (st.session_state.current_question.get('verbose') or {}).copy() if isinstance(st.session_state.current_question.get('verbose'), dict) else {},
                    'verbose_audio': dict(st.session_state.current_question.get('verbose_audio') or {}),
                    'question_image_url': st.session_state.current_question.get('question_image_url'),
                    'option_image_urls': dict(st.session_state.current_question.get('option_image_urls') or {}),
                }
                st.session_state.questions.append(question_copy)
                save_exam_to_storage()  # Auto-save after adding question
                reset_current_question()
                st.session_state.file_upload_key = st.session_state.get("file_upload_key", 0) + 1
                st.session_state.question_added_success = True
                st.rerun()
        
        if clear_form:
            reset_current_question()
            st.session_state.file_upload_key = st.session_state.get("file_upload_key", 0) + 1
            st.rerun()
        
        if save_exam:
            # Validate exam data
            if not st.session_state.exam_data['subject']:
                st.error("Please select a subject for the exam")
            elif not st.session_state.exam_data['exam_type']:
                st.error("Please select an exam type")
            elif not st.session_state.exam_data['year']:
                st.error("Please select a year for the exam")
            elif not st.session_state.questions:
                st.error("Please add at least one question before saving")
            else:
                # Ensure title is generated
                update_exam_title()
                
                # Check if updating existing exam or creating new one
                editing_exam_id = st.session_state.get('editing_exam_id')
                
                if editing_exam_id:
                    # Update existing exam
                    with st.spinner("Updating exam in database..."):
                        success = update_exam_in_db(
                            editing_exam_id,
                            st.session_state.exam_data,
                            st.session_state.questions
                        )
                    
                    if success:
                        st.success(f"🎉 Exam updated successfully! Exam ID: {editing_exam_id}")
                        # Reset editing state
                        st.session_state.editing_exam_id = None
                        # Reset session state
                        default_year = min(datetime.now().year, max(EXAM_YEARS)) if datetime.now().year <= max(EXAM_YEARS) else max(EXAM_YEARS)
                        st.session_state.exam_data = {
                            'exam_type': None,
                            'subject': '',
                            'year': default_year,
                            'title': '',
                            'duration': 60
                        }
                        st.session_state.questions = []
                        reset_current_question()
                        st.session_state.file_upload_key = st.session_state.get("file_upload_key", 0) + 1
                        st.session_state.auto_saved = False
                        # Mark that localStorage should be cleared
                        st.session_state.should_clear_storage = True
                        st.rerun()
                    else:
                        st.error("❌ Failed to update exam in database")
                else:
                    # Create new exam
                    with st.spinner("Saving exam to database..."):
                        exam_id = save_exam_to_database(
                        st.session_state.exam_data,
                        st.session_state.questions
                        )
                
                if exam_id:
                    st.success(f"🎉 Exam saved successfully! Exam ID: {exam_id}")
                    # Reset session state first
                    default_year = min(datetime.now().year, max(EXAM_YEARS)) if datetime.now().year <= max(EXAM_YEARS) else max(EXAM_YEARS)
                    st.session_state.exam_data = {
                        'exam_type': None,
                        'subject': '',
                        'year': default_year,
                        'title': '',
                        'duration': 60
                    }
                    st.session_state.questions = []
                    reset_current_question()
                    st.session_state.file_upload_key = st.session_state.get("file_upload_key", 0) + 1
                    st.session_state.auto_saved = False
                    # Mark that localStorage should be cleared
                    st.session_state.should_clear_storage = True
                    st.rerun()
                else:
                    st.error("❌ Failed to save exam to database")
    
    # Clear localStorage if exam was successfully saved to database
    if st.session_state.get('should_clear_storage', False):
        try:
            # Use unique keys to ensure the clear components render
            if 'clear_counter' not in st.session_state:
                st.session_state.clear_counter = 0
            st.session_state.clear_counter += 1
            
            # Render clear components - they need to be in UI flow to work
            st.session_state.localS.setItem(EXAM_DATA_KEY, "", key=f"clear_exam_{st.session_state.clear_counter}")
            st.session_state.localS.setItem(QUESTIONS_KEY, "", key=f"clear_questions_{st.session_state.clear_counter}")
            st.session_state.should_clear_storage = False
        except Exception:
            st.session_state.should_clear_storage = False
            pass
    
    # Always save to localStorage at the end of the page if we have questions
    # This ensures data persists even if other saves didn't trigger
    if 'questions' in st.session_state and len(st.session_state.questions) > 0:
        try:
            update_exam_title()
            exam_data_json = json.dumps(st.session_state.exam_data, default=datetime_encoder)
            questions_json = json.dumps(st.session_state.questions, default=datetime_encoder)
            
            # Use a stable key pattern that updates each render
            if 'final_save_counter' not in st.session_state:
                st.session_state.final_save_counter = 0
            st.session_state.final_save_counter += 1
            
            # Render components at end to ensure they execute
            st.session_state.localS.setItem(
                EXAM_DATA_KEY, 
                exam_data_json, 
                key=f"final_save_exam_{st.session_state.final_save_counter}"
            )
            st.session_state.localS.setItem(
                QUESTIONS_KEY, 
                questions_json, 
                key=f"final_save_questions_{st.session_state.final_save_counter}"
            )
        except Exception:
            pass

def view_questions_page():
    st.markdown('<h2 class="section-header">Current Questions</h2>', unsafe_allow_html=True)
    
    if not st.session_state.questions:
        st.info("No questions added yet. Go to 'Create Exam' to add questions.")
        return
    
    # Display exam summary
    st.markdown("### Exam Summary")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Exam Type", st.session_state.exam_data.get('exam_type', 'Not set'))
    
    with col2:
        st.metric("Subject", st.session_state.exam_data.get('subject', 'Not set'))
    
    with col3:
        st.metric("Year", st.session_state.exam_data.get('year', 'Not set'))
    
    with col4:
        st.metric("Questions", len(st.session_state.questions))
    
    # Bulk actions
    st.markdown("### Bulk Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🗑️ Clear All Questions", type="secondary"):
            st.session_state.questions = []
            save_exam_to_storage()  # Auto-save after clearing
            st.success("All questions cleared!")
            st.rerun()
    
    with col2:
        if st.button("📋 Duplicate Last Question", type="secondary"):
            if st.session_state.questions:
                last_question = st.session_state.questions[-1].copy()
                st.session_state.questions.append(last_question)
                save_exam_to_storage()  # Auto-save after duplicating
                st.success("Last question duplicated!")
                st.rerun()
            else:
                st.warning("No questions to duplicate")
    
    with col3:
        if st.button("🔄 Reorder Questions", type="secondary"):
            st.session_state.show_reorder = not st.session_state.get('show_reorder', False)
            st.rerun()
    
    # Reorder interface
    if st.session_state.get('show_reorder', False):
        st.markdown("### Reorder Questions")
        st.info("Drag and drop to reorder questions. Click 'Save Order' when done.")
        
        # Create a simple reorder interface
        for i, question in enumerate(st.session_state.questions):
            col1, col2, col3 = st.columns([1, 8, 1])
            with col1:
                st.write(f"**{i+1}**")
            with col2:
                st.write(f"{question['question']['en'][:80]}...")
            with col3:
                if st.button("⬆️", key=f"up_{i}", disabled=(i == 0)):
                    # Move question up
                    if i > 0:
                        st.session_state.questions[i], st.session_state.questions[i-1] = st.session_state.questions[i-1], st.session_state.questions[i]
                        save_exam_to_storage()  # Auto-save after reordering
                        st.rerun()
                if st.button("⬇️", key=f"down_{i}", disabled=(i == len(st.session_state.questions)-1)):
                    # Move question down
                    if i < len(st.session_state.questions)-1:
                        st.session_state.questions[i], st.session_state.questions[i+1] = st.session_state.questions[i+1], st.session_state.questions[i]
                        save_exam_to_storage()  # Auto-save after reordering
                        st.rerun()
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Save Order", type="primary"):
                st.session_state.show_reorder = False
                st.success("Question order saved!")
                st.rerun()
        with col2:
            if st.button("❌ Cancel", type="secondary"):
                st.session_state.show_reorder = False
                st.rerun()
    
    # Display questions with delete functionality
    st.markdown("### Questions List")
    for i, question in enumerate(st.session_state.questions):
        with st.container():
            # Question header with delete button
            col1, col2 = st.columns([8, 1])
            
            with col1:
                question_preview = question['question']['en'][:50] + "..." if len(question['question']['en']) > 50 else question['question']['en']
                st.markdown(f"**Question {i+1}:** {question_preview}")
            
            with col2:
                if st.button("🗑️", key=f"delete_{i}", help="Delete this question"):
                    st.session_state.questions.pop(i)
                    save_exam_to_storage()  # Auto-save after deleting
                    st.success(f"Question {i+1} deleted!")
                    st.rerun()
            
            # Question details in expander
            with st.expander(f"View Details - Question {i+1}", expanded=False):
                st.markdown("**Question:**")
                st.write(question['question']['en'])
                q_img_url = (question.get('question_image_url') or '').strip()
                if q_img_url:
                    st.image(q_img_url, caption="Question image", width=200)
                st.markdown("**Options:**")
                col1, col2 = st.columns(2)
                opt_imgs = question.get('option_image_urls') or {}
                with col1:
                    for option in ['A', 'B']:
                        marker = "✅" if option == question['answer'] else "⚪"
                        st.write(f"{marker} {option}: {question['options'][option]}")
                        if (opt_imgs.get(option) or '').strip():
                            st.image((opt_imgs.get(option) or '').strip(), caption=option, width=120)
                with col2:
                    for option in ['C', 'D']:
                        marker = "✅" if option == question['answer'] else "⚪"
                        st.write(f"{marker} {option}: {question['options'][option]}")
                        if (opt_imgs.get(option) or '').strip():
                            st.image((opt_imgs.get(option) or '').strip(), caption=option, width=120)
                
                st.markdown("**Explanation:**")
                st.write(question['explanation']['en'])
                
                # Edit question button
                if st.button(f"✏️ Edit Question {i+1}", key=f"edit_{i}"):
                    # Copy question data to current question form
                    v = question.get('verbose')
                    st.session_state.current_question = {
                        'question': question['question'].copy(),
                        'options': question['options'].copy(),
                        'answer': question['answer'],
                        'explanation': (question.get('explanation') or {}).copy() if isinstance(question.get('explanation'), dict) else {},
                        'verbose': (v.copy() if isinstance(v, dict) else v) or {},
                        'verbose_audio': dict(question.get('verbose_audio') or {}),
                        'question_image_url': question.get('question_image_url'),
                        'option_image_urls': dict(question.get('option_image_urls') or {}),
                    }
                    # Remove the question from the list
                    st.session_state.questions.pop(i)
                    save_exam_to_storage()  # Auto-save after editing (removing from list)
                    st.success(f"Question {i+1} moved to edit form!")
                    st.rerun()

def question_editor(question_data: Dict, question_id: Optional[str] = None, exam_id: Optional[str] = None, on_save=None, on_cancel=None):
    """Reusable question editor component"""
    with st.form(f"question_editor_{question_id or 'new'}", clear_on_submit=False):
        st.markdown("### Edit Question")
        
        # Question text
        question_en = st.text_area(
            "Question (English)",
            value=question_data.get('question', {}).get('en', ''),
            height=100,
            key=f"q_question_{question_id}"
        )
        
        # Options
        col1, col2 = st.columns(2)
        with col1:
            option_a = st.text_input("Option A", value=question_data.get('options', {}).get('A', ''), key=f"q_opt_a_{question_id}")
            option_b = st.text_input("Option B", value=question_data.get('options', {}).get('B', ''), key=f"q_opt_b_{question_id}")
        with col2:
            option_c = st.text_input("Option C", value=question_data.get('options', {}).get('C', ''), key=f"q_opt_c_{question_id}")
            option_d = st.text_input("Option D", value=question_data.get('options', {}).get('D', ''), key=f"q_opt_d_{question_id}")
        
        # Correct answer
        current_answer = question_data.get('answer', 'A')
        answer_index = ['A', 'B', 'C', 'D'].index(current_answer) if current_answer in ['A', 'B', 'C', 'D'] else 0
        correct_answer = st.selectbox(
            "Correct Answer",
            options=['A', 'B', 'C', 'D'],
            index=answer_index,
            key=f"q_answer_{question_id}"
        )
        
        # Explanation
        explanation_en = st.text_area(
            "Explanation (English)",
            value=question_data.get('explanation', {}).get('en', ''),
            height=100,
            key=f"q_explanation_{question_id}"
        )

        # Question image
        q_img = (question_data.get('question_image_url') or '').strip()
        if q_img:
            st.image(q_img, width=200)
        q_img_url_edit = st.text_input("Question image URL", value=q_img, key=f"q_img_url_edit_{question_id}")
        opt_urls_existing = question_data.get('option_image_urls') or {}
        option_image_urls_edit = {}
        for opt in ['A', 'B', 'C', 'D']:
            o_url = (opt_urls_existing.get(opt) or '').strip()
            if o_url:
                st.image(o_url, width=120)
            option_image_urls_edit[opt] = st.text_input(f"Option {opt} image URL", value=o_url, key=f"opt_img_edit_{question_id}_{opt}")
        opt_urls_edit = {k: (v.strip() or None) for k, v in option_image_urls_edit.items() if v and str(v).strip()}
        
        # Buttons
        col1, col2 = st.columns(2)
        with col1:
            save_btn = st.form_submit_button("💾 Save", type="primary")
        with col2:
            cancel_btn = st.form_submit_button("❌ Cancel")
        
        if save_btn:
            # Validate
            updated_data = {
                'question': {'en': question_en, 'ha': question_data.get('question', {}).get('ha', ''), 
                            'ig': question_data.get('question', {}).get('ig', ''), 
                            'yo': question_data.get('question', {}).get('yo', '')},
                'options': {'A': option_a, 'B': option_b, 'C': option_c, 'D': option_d},
                'answer': correct_answer,
                'explanation': {'en': explanation_en, 'ha': question_data.get('explanation', {}).get('ha', ''),
                               'ig': question_data.get('explanation', {}).get('ig', ''),
                               'yo': question_data.get('explanation', {}).get('yo', '')},
                'verbose': question_data.get('verbose', {}),
                'question_image_url': q_img_url_edit.strip() or None,
                'option_image_urls': opt_urls_edit or None,
            }
            
            errors = validate_question(updated_data)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                if on_save:
                    on_save(question_id, updated_data)
        
        if cancel_btn:
            if on_cancel:
                on_cancel()

def exam_detail_view(exam_id: str):
    """Display exam details and questions with editing capabilities"""
    # Fetch exam data
    exam = fetch_exam_by_id(exam_id)
    if not exam:
        st.error("Exam not found")
        return
    
    # Display exam metadata
    st.markdown('<h2 class="section-header">Exam Details</h2>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Exam Type", exam['exam_type'] or 'N/A')
    with col2:
        st.metric("Subject", exam['subject'] or 'N/A')
    with col3:
        st.metric("Year", exam['year'] or 'N/A')
    with col4:
        st.metric("Duration", f"{exam['duration']} min" if exam['duration'] else 'N/A')
    
    st.info(f"**Title:** {exam['title']}")
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📥 Load for Bulk Edit", type="primary"):
            # Load exam into session
            questions = fetch_exam_questions(exam_id)
            st.session_state.exam_data = {
                'exam_type': exam['exam_type'],
                'subject': exam['subject'],
                'year': exam['year'],
                'title': exam['title'],
                'duration': exam['duration']
            }
            st.session_state.questions = questions
            st.session_state.editing_exam_id = exam_id
            st.session_state.viewing_exam_id = None
            st.success("Exam loaded! Switch to 'Create Exam' page to edit.")
            st.rerun()
    
    with col2:
        if st.button("🔄 Refresh", type="secondary"):
            st.rerun()
    
    with col3:
        if st.button("🗑️ Delete Exam", type="secondary"):
            st.session_state.delete_exam_confirm = exam_id
    
    # Delete confirmation
    if st.session_state.get('delete_exam_confirm') == exam_id:
        st.warning("⚠️ Are you sure you want to delete this exam and all its questions?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Yes, Delete", type="primary"):
                if delete_exam_from_db(exam_id):
                    st.success("Exam deleted successfully!")
                    st.session_state.viewing_exam_id = None
                    st.session_state.delete_exam_confirm = None
                    st.rerun()
                else:
                    st.error("Failed to delete exam")
        with col2:
            if st.button("❌ Cancel", type="secondary"):
                st.session_state.delete_exam_confirm = None
                st.rerun()
    
    # Fetch and display questions
    st.markdown('<h2 class="section-header">Questions</h2>', unsafe_allow_html=True)
    
    questions = fetch_exam_questions(exam_id)
    
    if not questions:
        st.info("No questions found for this exam.")
        
        # Add new question button
        if st.button("➕ Add Question", type="primary"):
            st.session_state.adding_question_to_exam = exam_id
            st.rerun()
    else:
        st.metric("Total Questions", len(questions))
        
        # Add new question button
        if st.button("➕ Add New Question", type="primary"):
            st.session_state.adding_question_to_exam = exam_id
            st.rerun()
        
        # Display questions
        for i, question in enumerate(questions):
            with st.container():
                st.markdown("---")
                col1, col2 = st.columns([8, 1])
                
                with col1:
                    question_preview = question['question'].get('en', '')[:80] + "..." if len(question['question'].get('en', '')) > 80 else question['question'].get('en', '')
                    st.markdown(f"**Question {question['number']}:** {question_preview}")
                
                with col2:
                    if st.button("🗑️", key=f"del_q_{question['id']}", help="Delete question"):
                        if delete_question_from_db(question['id']):
                            st.success(f"Question {question['number']} deleted!")
                            st.rerun()
                        else:
                            st.error("Failed to delete question")
                
                # Expandable question details
                with st.expander(f"View/Edit Question {question['number']}", expanded=False):
                    if st.session_state.get(f"editing_question_{question['id']}"):
                        # Show editor
                        def save_question(q_id, q_data):
                            if update_question_in_db(q_id, q_data):
                                st.session_state[f"editing_question_{q_id}"] = False
                                st.success("Question updated!")
                                st.rerun()
                            else:
                                st.error("Failed to update question")
                        
                        def cancel_edit():
                            st.session_state[f"editing_question_{question['id']}"] = False
                            st.rerun()
                        
                        question_editor(question, question['id'], exam_id, save_question, cancel_edit)
                    else:
                        # Show question details
                        st.markdown("**Question:**")
                        st.write(question['question'].get('en', 'N/A'))
                        q_img_url = (question.get('question_image_url') or '').strip()
                        if q_img_url:
                            st.image(q_img_url, width=200)
                        st.markdown("**Options:**")
                        col1, col2 = st.columns(2)
                        opt_imgs = question.get('option_image_urls') or {}
                        with col1:
                            for opt in ['A', 'B']:
                                marker = "✅" if opt == question['answer'] else "⚪"
                                st.write(f"{marker} {opt}: {question['options'].get(opt, 'N/A')}")
                                if (opt_imgs.get(opt) or '').strip():
                                    st.image((opt_imgs.get(opt) or '').strip(), width=120)
                        with col2:
                            for opt in ['C', 'D']:
                                marker = "✅" if opt == question['answer'] else "⚪"
                                st.write(f"{marker} {opt}: {question['options'].get(opt, 'N/A')}")
                                if (opt_imgs.get(opt) or '').strip():
                                    st.image((opt_imgs.get(opt) or '').strip(), width=120)
                        
                        st.markdown("**Explanation:**")
                        st.write(question['explanation'].get('en', 'N/A'))
                        
                        if st.button(f"✏️ Edit Question {question['number']}", key=f"edit_btn_{question['id']}"):
                            st.session_state[f"editing_question_{question['id']}"] = True
                            st.rerun()
    
    # Handle adding new question
    if st.session_state.get('adding_question_to_exam') == exam_id:
        st.markdown("### Add New Question")
        new_question_data = {
            'question': {'en': '', 'ha': '', 'ig': '', 'yo': ''},
            'options': {'A': '', 'B': '', 'C': '', 'D': ''},
            'answer': 'A',
            'explanation': {'en': '', 'ha': '', 'ig': '', 'yo': ''},
            'verbose': {'en': '', 'ha': '', 'ig': '', 'yo': ''},
            'question_image_url': None,
            'option_image_urls': {},
        }
        
        def save_new_question(q_id, q_data):
            if add_question_to_exam(exam_id, q_data):
                st.session_state.adding_question_to_exam = None
                st.success("Question added!")
                st.rerun()
            else:
                st.error("Failed to add question")
        
        def cancel_add():
            st.session_state.adding_question_to_exam = None
            st.rerun()
        
        question_editor(new_question_data, None, exam_id, save_new_question, cancel_add)

def browse_exams_page():
    """Browse and manage exams from the database"""
    st.markdown('<h2 class="section-header">Browse Exams</h2>', unsafe_allow_html=True)
    
    # Check if viewing a specific exam
    if st.session_state.get('viewing_exam_id'):
        if st.button("← Back to Exam List"):
            st.session_state.viewing_exam_id = None
            st.rerun()
        exam_detail_view(st.session_state.viewing_exam_id)
        return
    
    # Filters
    st.markdown("### Filters")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        exam_type_filter = st.selectbox(
            "Exam Type",
            options=[None] + [e.value for e in ExamType],
            format_func=lambda x: "All" if x is None else x
        )
    
    with col2:
        subject_filter = st.selectbox(
            "Subject",
            options=[None] + SUBJECTS,
            format_func=lambda x: "All" if x is None else x
        )
    
    with col3:
        year_filter = st.selectbox(
            "Year",
            options=[None] + EXAM_YEARS,
            format_func=lambda x: "All" if x is None else str(x)
        )
    
    with col4:
        search_title = st.text_input("Search Title", placeholder="Search by title...")
    
    # Fetch exams
    with st.spinner("Loading exams..."):
        exams = fetch_all_exams(
            exam_type=exam_type_filter,
            subject=subject_filter,
            year=year_filter,
            search_title=search_title if search_title else None
        )
    
    if not exams:
        st.info("No exams found matching the filters.")
        return
    
    st.metric("Total Exams Found", len(exams))
    
    # Display exams in a table-like format
    st.markdown("### Exam List")
    
    for exam in exams:
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1, 1, 2])
            
            with col1:
                st.markdown(f"**{exam['title'] or 'Untitled'}**")
                st.caption(f"ID: {exam['id'][:8]}...")
            
            with col2:
                st.write(f"**Type:** {exam['exam_type'] or 'N/A'}")
                st.write(f"**Subject:** {exam['subject'] or 'N/A'}")
            
            with col3:
                st.write(f"**Year:** {exam['year'] or 'N/A'}")
                st.write(f"**Questions:** {exam['question_count']}")
            
            with col4:
                if exam['created_at']:
                    created_date = datetime.fromisoformat(exam['created_at']).strftime("%Y-%m-%d")
                    st.write(f"**Created:** {created_date}")
            
            with col5:
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if st.button("👁️ View", key=f"view_{exam['id']}"):
                        st.session_state.viewing_exam_id = exam['id']
                        st.rerun()
                with col_b:
                    if st.button("📥 Load", key=f"load_{exam['id']}"):
                        # Load exam into session
                        questions = fetch_exam_questions(exam['id'])
                        st.session_state.exam_data = {
                            'exam_type': exam['exam_type'],
                            'subject': exam['subject'],
                            'year': exam['year'],
                            'title': exam['title'],
                            'duration': exam['duration']
                        }
                        st.session_state.questions = questions
                        st.session_state.editing_exam_id = exam['id']
                        st.success("Exam loaded! Switch to 'Create Exam' page to edit.")
                        st.rerun()
                with col_c:
                    if st.button("🗑️", key=f"del_{exam['id']}", help="Delete"):
                        st.session_state.delete_exam_id = exam['id']
            
            st.markdown("---")
    
    # Delete confirmation dialog
    if st.session_state.get('delete_exam_id'):
        exam_to_delete = st.session_state.delete_exam_id
        st.warning(f"⚠️ Are you sure you want to delete this exam? This action cannot be undone.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Yes, Delete", type="primary"):
                if delete_exam_from_db(exam_to_delete):
                    st.success("Exam deleted successfully!")
                    st.session_state.delete_exam_id = None
                    st.rerun()
                else:
                    st.error("Failed to delete exam")
        with col2:
            if st.button("❌ Cancel", type="secondary"):
                st.session_state.delete_exam_id = None
                st.rerun()

def database_status_page():
    st.markdown('<h2 class="section-header">Database Status</h2>', unsafe_allow_html=True)
    
    # Test database connection
    with st.spinner("Testing database connection..."):
        try:
            connection_ok = test_database_connection()
            
            if connection_ok:
                st.success("✅ Database connection successful!")
            else:
                st.error("❌ Database connection failed!")
        except Exception as e:
            st.error(f"❌ Database connection error: {str(e)}")
    
    # Show current exam data
    st.markdown("### Current Session Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Exam Details:**")
        st.json(st.session_state.exam_data)
    
    with col2:
        st.markdown("**Questions Count:**")
        st.metric("Total Questions", len(st.session_state.questions))
        
        if st.session_state.questions:
            st.markdown("**Question Preview:**")
            for i, q in enumerate(st.session_state.questions[:3], 1):
                st.write(f"{i}. {q['question']['en'][:50]}...")
            if len(st.session_state.questions) > 3:
                st.write(f"... and {len(st.session_state.questions) - 3} more")

if __name__ == "__main__":
    main()
