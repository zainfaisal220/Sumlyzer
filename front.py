import streamlit as st
from vector import upload_pdf, create_faiss_db
from Rag_pipline import answer_query, retrieve_summary, llm_model
import os
import time
import base64

# Initialize session state
if "faiss_db" not in st.session_state:
    st.session_state.faiss_db = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_pdf_name" not in st.session_state:
    st.session_state.last_pdf_name = None
if "theme" not in st.session_state:
    st.session_state.theme = "light"

# Custom CSS for attractive UI with fixed text visibility
st.markdown(
    """
    <style>
    .main { padding: 20px; background: linear-gradient(135deg, #f5f7fa, #c3cfe2); }
    .dark-theme .main { background: linear-gradient(135deg, #2c3e50, #1a1a2a); }
    .stButton>button { 
        background-color: #6200ea; 
        color: white; 
        border-radius: 8px; 
        padding: 10px 20px; 
        font-weight: bold; 
        transition: all 0.3s; 
    }
    .stButton>button:hover { 
        background-color: #3700b3; 
        transform: scale(1.05); 
    }
    .chat-container { 
        max-height: 400px; 
        overflow-y: auto; 
        padding: 10px; 
        border: 1px solid #ddd; 
        border-radius: 10px; 
        background: #ffffff; 
    }
    .dark-theme .chat-container { 
        background: #333333; 
        border-color: #555555; 
    }
    .chat-message-ai { 
        background: #e8ecef; 
        color: #1a1a1a; /* Dark text for light theme */
        padding: 10px; 
        border-radius: 10px; 
        margin: 5px 0; 
        max-width: 80%; 
    }
    .dark-theme .chat-message-ai { 
        background: #4a4a4a; 
        color: #e0e0e0; /* Light text for dark theme */
    }
    .error-box { 
        background: #ffebee; 
        color: #d32f2f; 
        padding: 10px; 
        border-radius: 8px; 
        border: 1px solid #d32f2f; 
    }
    .dark-theme .error-box { 
        background: #b71c1c; 
        color: #ffffff; 
    }
    .sidebar .stButton>button { 
        width: 100%; 
        margin-bottom: 10px; 
    }
    .pdf-preview { 
        border: 1px solid #ddd; 
        border-radius: 10px; 
        padding: 10px; 
        background: #ffffff; 
    }
    .dark-theme .pdf-preview { 
        background: #333333; 
        border-color: #555555; 
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Apply theme
st.markdown(f"<div class='{st.session_state.theme}-theme'>", unsafe_allow_html=True)

# Title and description
st.title("📚 Sumlyzer")
st.markdown("Upload a PDF and click 'Get Summary' to receive a concise bullet-point summary of the document’s main points.")

# Sidebar for controls
with st.sidebar:
    st.header("Settings")
    # Theme toggle
    theme = st.selectbox("Theme", ["light", "dark"], index=0 if st.session_state.theme == "light" else 1)
    if theme != st.session_state.theme:
        st.session_state.theme = theme
        st.rerun()

# Main layout
col1, col2 = st.columns([2, 1])

with col1:
    # File uploader
    uploaded_file = st.file_uploader("Upload a PDF", type="pdf", accept_multiple_files=False, key="pdf_uploader")
    
    # Submit button
    ask_question = st.button("Get Summary", key="submit_button")

with col2:
    # PDF preview (if uploaded)
    if uploaded_file:
        st.subheader("PDF Preview")
        pdf_path = f"pdfs/{uploaded_file.name}"
        with open(pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        # Convert PDF to base64 for iframe
        with open(pdf_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode("utf-8")
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="300px" class="pdf-preview"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)

# Summary history
st.subheader("Summary History")
with st.container():
    chat_container = st.empty()
    for message in st.session_state.chat_history:
        st.markdown(f"<div class='chat-message-ai'><b>Summary:</b> {message['ai']}</div>", unsafe_allow_html=True)

# Download summary history
if st.session_state.chat_history:
    history_text = "\n\n".join([f"Summary:\n{m['ai']}" for m in st.session_state.chat_history])
    st.download_button("Download Summary History", history_text, file_name="summary_history.txt", key="download_button")

# Clear history
if st.button("Clear Summary History", key="clear_history"):
    st.session_state.chat_history = []
    st.rerun()

# Process PDF and generate summary
if ask_question:
    if not uploaded_file:
        st.markdown("<div class='error-box'>Please upload a valid PDF file!</div>", unsafe_allow_html=True)
    else:
        with st.spinner("Generating summary..."):
            try:
                # Check for existing FAISS index
                current_pdf_name = uploaded_file.name
                if st.session_state.last_pdf_name != current_pdf_name:
                    pdf_file_path = upload_pdf(uploaded_file)
                    st.session_state.faiss_db = create_faiss_db(pdf_file_path)
                    st.session_state.last_pdf_name = current_pdf_name
                    st.success("PDF processed successfully!")
                
                # Use fixed prompt for summarization
                fixed_prompt = "Summarize the main points of the document in 5 to 10 bullet points."
                retrieved_docs = retrieve_summary(fixed_prompt, st.session_state.faiss_db)
                response = answer_query(documents=retrieved_docs, model=llm_model, query=fixed_prompt)
                
                # Add to history
                st.session_state.chat_history.append({"ai": response})
                st.rerun()
                
            except Exception as e:
                st.markdown(f"<div class='error-box'>Error: {e}</div>", unsafe_allow_html=True)
                with open("error_log.txt", "a") as f:
                    f.write(f"[{time.ctime()}] Error: {e}\n")

# Close theme div
st.markdown("</div>", unsafe_allow_html=True)
