import streamlit as st
import asyncio
import json
from typing import Dict, List, Optional
from datetime import datetime
import uuid

# Import from your existing modules
from exam import Exam, ExamType
from question import Question
from database import AsyncSessionLocal, get_db
from sqlalchemy import select, text

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
def datetime_encoder(obj):
    """Custom JSON encoder for datetime objects"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

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
        'verbose': {'en': '', 'ha': '', 'ig': '', 'yo': ''}
    }

# Helper functions
def reset_current_question():
    """Reset the current question form"""
    st.session_state.current_question = {
        'question': {'en': '', 'ha': '', 'ig': '', 'yo': ''},
        'options': {'A': '', 'B': '', 'C': '', 'D': ''},
        'answer': 'A',
        'explanation': {'en': '', 'ha': '', 'ig': '', 'yo': ''},
        'verbose': {'en': '', 'ha': '', 'ig': '', 'yo': ''}
    }

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

async def save_exam_to_database(exam_data: Dict, questions: List[Dict]) -> Optional[str]:
    """Save exam and questions to database"""
    try:
        async with AsyncSessionLocal() as db:
            # Create exam
            exam = Exam(
                exam_type=ExamType(exam_data['exam_type']),
                subject=exam_data['subject'],
                year=exam_data['year'],
                title=exam_data['title'],
                duration=exam_data['duration']
            )
            
            db.add(exam)
            await db.flush()  # Get the exam ID
            
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
            
            await db.commit()
            return str(exam.id)
            
    except Exception as e:
        st.error(f"Error saving to database: {str(e)}")
        return None

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
            save_exam = st.form_submit_button("💾 Save Exam to Database", type="secondary")
        
        # Handle form submissions
        if add_question:
            # Validate question
            errors = validate_question(st.session_state.current_question)
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                # Add question to list
                question_copy = {
                    'question': st.session_state.current_question['question'].copy(),
                    'options': st.session_state.current_question['options'].copy(),
                    'answer': st.session_state.current_question['answer'],
                    'explanation': st.session_state.current_question['explanation'].copy(),
                    'verbose': st.session_state.current_question['verbose'].copy()
                }
                st.session_state.questions.append(question_copy)
                save_exam_to_storage()  # Auto-save after adding question
                reset_current_question()
                st.session_state.question_added_success = True
                st.rerun()
        
        if clear_form:
            reset_current_question()
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
                # Save to database
                with st.spinner("Saving exam to database..."):
                    exam_id = asyncio.run(save_exam_to_database(
                        st.session_state.exam_data,
                        st.session_state.questions
                    ))
                
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
                
                st.markdown("**Options:**")
                col1, col2 = st.columns(2)
                
                with col1:
                    for option in ['A', 'B']:
                        marker = "✅" if option == question['answer'] else "⚪"
                        st.write(f"{marker} {option}: {question['options'][option]}")
                
                with col2:
                    for option in ['C', 'D']:
                        marker = "✅" if option == question['answer'] else "⚪"
                        st.write(f"{marker} {option}: {question['options'][option]}")
                
                st.markdown("**Explanation:**")
                st.write(question['explanation']['en'])
                
                # Edit question button
                if st.button(f"✏️ Edit Question {i+1}", key=f"edit_{i}"):
                    # Copy question data to current question form
                    st.session_state.current_question = {
                        'question': question['question'].copy(),
                        'options': question['options'].copy(),
                        'answer': question['answer'],
                        'explanation': question['explanation'].copy(),
                        'verbose': question['verbose'].copy()
                    }
                    # Remove the question from the list
                    st.session_state.questions.pop(i)
                    save_exam_to_storage()  # Auto-save after editing (removing from list)
                    st.success(f"Question {i+1} moved to edit form!")
                    st.rerun()

def database_status_page():
    st.markdown('<h2 class="section-header">Database Status</h2>', unsafe_allow_html=True)
    
    # Test database connection
    with st.spinner("Testing database connection..."):
        try:
            async def test_connection():
                async with AsyncSessionLocal() as db:
                    result = await db.execute(text("SELECT 1"))
                    return True
            
            connection_ok = asyncio.run(test_connection())
            
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
