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

# Page configuration
st.set_page_config(
    page_title="Exam Annotation Tool",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'exam_data' not in st.session_state:
    st.session_state.exam_data = {
        'exam_type': None,
        'subject': '',
        'year': datetime.now().year,
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
    st.markdown('<h1 class="main-header">📝 Exam Annotation Tool</h1>', unsafe_allow_html=True)
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Select Page", ["Create Exam", "View Questions", "Database Status"])
    
    if page == "Create Exam":
        create_exam_page()
    elif page == "View Questions":
        view_questions_page()
    elif page == "Database Status":
        database_status_page()

def create_exam_page():
    st.markdown('<h2 class="section-header">📋 Exam Details</h2>', unsafe_allow_html=True)
    
    # Exam details form
    col1, col2 = st.columns(2)
    
    with col1:
        exam_type = st.selectbox(
            "Exam Type",
            options=[e.value for e in ExamType],
            index=0,
            help="Select the type of exam you're creating"
        )
        st.session_state.exam_data['exam_type'] = exam_type
        
        subject = st.text_input(
            "Subject",
            value=st.session_state.exam_data['subject'],
            placeholder="e.g., Mathematics, Physics, Chemistry",
            help="Enter the subject for this exam"
        )
        st.session_state.exam_data['subject'] = subject
        
        year = st.number_input(
            "Year",
            min_value=2000,
            max_value=2030,
            value=st.session_state.exam_data['year'],
            help="Enter the year for this exam"
        )
        st.session_state.exam_data['year'] = year
    
    with col2:
        title = st.text_input(
            "Exam Title",
            value=st.session_state.exam_data['title'],
            placeholder="e.g., WAEC Mathematics 2024",
            help="Enter a descriptive title for this exam"
        )
        st.session_state.exam_data['title'] = title
        
        duration = st.number_input(
            "Duration (minutes)",
            min_value=15,
            max_value=300,
            value=st.session_state.exam_data['duration'],
            help="Enter the duration in minutes"
        )
        st.session_state.exam_data['duration'] = duration
    
    st.markdown('<h2 class="section-header">❓ Add Questions</h2>', unsafe_allow_html=True)
    
    # Question form
    with st.form("question_form", clear_on_submit=False):
        st.markdown("### Question Details")
        
        # Question text in multiple languages
        st.markdown("**Question Text (Multilingual)**")
        col1, col2 = st.columns(2)
        
        with col1:
            question_en = st.text_area(
                "English",
                value=st.session_state.current_question['question']['en'],
                placeholder="Enter the question in English",
                height=100
            )
            st.session_state.current_question['question']['en'] = question_en
            
            question_ha = st.text_area(
                "Hausa",
                value=st.session_state.current_question['question']['ha'],
                placeholder="Enter the question in Hausa (optional)",
                height=100
            )
            st.session_state.current_question['question']['ha'] = question_ha
        
        with col2:
            question_ig = st.text_area(
                "Igbo",
                value=st.session_state.current_question['question']['ig'],
                placeholder="Enter the question in Igbo (optional)",
                height=100
            )
            st.session_state.current_question['question']['ig'] = question_ig
            
            question_yo = st.text_area(
                "Yoruba",
                value=st.session_state.current_question['question']['yo'],
                placeholder="Enter the question in Yoruba (optional)",
                height=100
            )
            st.session_state.current_question['question']['yo'] = question_yo
        
        # Options
        st.markdown("**Answer Options**")
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
        correct_answer = st.selectbox(
            "Correct Answer",
            options=['A', 'B', 'C', 'D'],
            index=['A', 'B', 'C', 'D'].index(st.session_state.current_question['answer']),
            help="Select the correct answer"
        )
        st.session_state.current_question['answer'] = correct_answer
        
        # Explanation in multiple languages
        st.markdown("**Explanation (Multilingual)**")
        col1, col2 = st.columns(2)
        
        with col1:
            explanation_en = st.text_area(
                "English Explanation",
                value=st.session_state.current_question['explanation']['en'],
                placeholder="Explain why this answer is correct in English",
                height=80
            )
            st.session_state.current_question['explanation']['en'] = explanation_en
            
            explanation_ha = st.text_area(
                "Hausa Explanation",
                value=st.session_state.current_question['explanation']['ha'],
                placeholder="Explain in Hausa (optional)",
                height=80
            )
            st.session_state.current_question['explanation']['ha'] = explanation_ha
        
        with col2:
            explanation_ig = st.text_area(
                "Igbo Explanation",
                value=st.session_state.current_question['explanation']['ig'],
                placeholder="Explain in Igbo (optional)",
                height=80
            )
            st.session_state.current_question['explanation']['ig'] = explanation_ig
            
            explanation_yo = st.text_area(
                "Yoruba Explanation",
                value=st.session_state.current_question['explanation']['yo'],
                placeholder="Explain in Yoruba (optional)",
                height=80
            )
            st.session_state.current_question['explanation']['yo'] = explanation_yo
        
        # Verbose content in multiple languages
        st.markdown("**Verbose Content (Multilingual)**")
        col1, col2 = st.columns(2)
        
        with col1:
            verbose_en = st.text_area(
                "English Verbose",
                value=st.session_state.current_question['verbose']['en'],
                placeholder="Additional detailed explanation in English (optional)",
                height=80
            )
            st.session_state.current_question['verbose']['en'] = verbose_en
            
            verbose_ha = st.text_area(
                "Hausa Verbose",
                value=st.session_state.current_question['verbose']['ha'],
                placeholder="Additional explanation in Hausa (optional)",
                height=80
            )
            st.session_state.current_question['verbose']['ha'] = verbose_ha
        
        with col2:
            verbose_ig = st.text_area(
                "Igbo Verbose",
                value=st.session_state.current_question['verbose']['ig'],
                placeholder="Additional explanation in Igbo (optional)",
                height=80
            )
            st.session_state.current_question['verbose']['ig'] = verbose_ig
            
            verbose_yo = st.text_area(
                "Yoruba Verbose",
                value=st.session_state.current_question['verbose']['yo'],
                placeholder="Additional explanation in Yoruba (optional)",
                height=80
            )
            st.session_state.current_question['verbose']['yo'] = verbose_yo
        
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
                st.success(f"✅ Question {len(st.session_state.questions)} added successfully!")
                reset_current_question()
                st.rerun()
        
        if clear_form:
            reset_current_question()
            st.rerun()
        
        if save_exam:
            # Validate exam data
            if not st.session_state.exam_data['subject']:
                st.error("Please enter a subject for the exam")
            elif not st.session_state.exam_data['title']:
                st.error("Please enter a title for the exam")
            elif not st.session_state.questions:
                st.error("Please add at least one question before saving")
            else:
                # Save to database
                with st.spinner("Saving exam to database..."):
                    exam_id = asyncio.run(save_exam_to_database(
                        st.session_state.exam_data,
                        st.session_state.questions
                    ))
                
                if exam_id:
                    st.success(f"🎉 Exam saved successfully! Exam ID: {exam_id}")
                    # Reset session state
                    st.session_state.exam_data = {
                        'exam_type': None,
                        'subject': '',
                        'year': datetime.now().year,
                        'title': '',
                        'duration': 60
                    }
                    st.session_state.questions = []
                    reset_current_question()
                    st.rerun()
                else:
                    st.error("❌ Failed to save exam to database")

def view_questions_page():
    st.markdown('<h2 class="section-header">📚 Current Questions</h2>', unsafe_allow_html=True)
    
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
            st.success("All questions cleared!")
            st.rerun()
    
    with col2:
        if st.button("📋 Duplicate Last Question", type="secondary"):
            if st.session_state.questions:
                last_question = st.session_state.questions[-1].copy()
                st.session_state.questions.append(last_question)
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
                        st.rerun()
                if st.button("⬇️", key=f"down_{i}", disabled=(i == len(st.session_state.questions)-1)):
                    # Move question down
                    if i < len(st.session_state.questions)-1:
                        st.session_state.questions[i], st.session_state.questions[i+1] = st.session_state.questions[i+1], st.session_state.questions[i]
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
                    st.success(f"Question {i+1} deleted!")
                    st.rerun()
            
            # Question details in expander
            with st.expander(f"View Details - Question {i+1}", expanded=False):
                st.markdown("**Question Text:**")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"🇬🇧 English: {question['question']['en']}")
                    if question['question']['ha']:
                        st.write(f"🇳🇬 Hausa: {question['question']['ha']}")
                
                with col2:
                    if question['question']['ig']:
                        st.write(f"🇳🇬 Igbo: {question['question']['ig']}")
                    if question['question']['yo']:
                        st.write(f"🇳🇬 Yoruba: {question['question']['yo']}")
                
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
                st.write(f"🇬🇧 English: {question['explanation']['en']}")
                
                if any(question['explanation'][lang] for lang in ['ha', 'ig', 'yo']):
                    st.markdown("**Other Languages:**")
                    for lang, name in [('ha', 'Hausa'), ('ig', 'Igbo'), ('yo', 'Yoruba')]:
                        if question['explanation'][lang]:
                            st.write(f"🇳🇬 {name}: {question['explanation'][lang]}")
                
                if any(question['verbose'][lang] for lang in ['en', 'ha', 'ig', 'yo']):
                    st.markdown("**Verbose Content:**")
                    for lang, name in [('en', 'English'), ('ha', 'Hausa'), ('ig', 'Igbo'), ('yo', 'Yoruba')]:
                        if question['verbose'][lang]:
                            st.write(f"🇳🇬 {name}: {question['verbose'][lang]}")
                
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
                    st.success(f"Question {i+1} moved to edit form!")
                    st.rerun()

def database_status_page():
    st.markdown('<h2 class="section-header">🗄️ Database Status</h2>', unsafe_allow_html=True)
    
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
