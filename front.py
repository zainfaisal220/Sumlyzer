import streamlit as st
from vector import upload_pdf, create_faiss_db
from Rag_pipline import answer_query, retrieve_summary, llm_model
import os
import time
import base64
from datetime import datetime
import io
import re
import gc
from typing import Optional, Dict, Any, Tuple

# PDF Preview Exception Classes
class PDFPreviewError(Exception):
    """Base exception for PDF preview errors"""
    pass

class PDFValidationError(PDFPreviewError):
    """Raised when PDF validation fails"""
    pass

class PDFSizeError(PDFPreviewError):
    """Raised when PDF size exceeds limits"""
    pass

class PDFCorruptionError(PDFPreviewError):
    """Raised when PDF file is corrupted"""
    pass

class PDFEncodingError(PDFPreviewError):
    """Raised when PDF encoding fails"""
    pass

class PDFBrowserLimitError(PDFPreviewError):
    """Raised when browser limitations prevent preview"""
    pass

class PDFMemoryError(PDFPreviewError):
    """Raised when memory is insufficient for preview"""
    pass

# Page configuration - Mobile-first Responsive
st.set_page_config(
    page_title="Sumlyzer - Smart PDF Summarizer",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",  # Collapsed on mobile for better UX
    menu_items=None
)

# Initialize session state
if "faiss_db" not in st.session_state:
    st.session_state.faiss_db = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_pdf_name" not in st.session_state:
    st.session_state.last_pdf_name = None
if "total_pages" not in st.session_state:
    st.session_state.total_pages = 0

# PDF Preview Helper Functions
def validate_pdf_file(uploaded_file) -> Tuple[bool, str]:
    """
    Validate PDF file before processing
    Returns: (is_valid, error_message)
    """
    if uploaded_file is None:
        return False, "No file provided"
    
    # Check file extension
    if not uploaded_file.name.lower().endswith('.pdf'):
        return False, "File must be a PDF (.pdf extension required)"
    
    # Check MIME type
    if hasattr(uploaded_file, 'type') and uploaded_file.type:
        if uploaded_file.type not in ['application/pdf', 'application/x-pdf']:
            return False, f"Invalid file type: {uploaded_file.type}"
    
    # Check file size
    max_size_mb = 50  # Maximum 50MB file
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > max_size_mb:
        return False, f"File too large: {file_size_mb:.1f}MB (max: {max_size_mb}MB)"
    
    if uploaded_file.size == 0:
        return False, "File is empty"
    
    # Basic PDF header validation
    try:
        header = uploaded_file.read(5)
        uploaded_file.seek(0)  # Reset file pointer
        if not header.startswith(b'%PDF'):
            return False, "Invalid PDF format - corrupted or not a PDF"
    except Exception as e:
        return False, f"Error reading file header: {str(e)}"
    
    return True, ""

def safe_get_file_content(uploaded_file) -> Tuple[Optional[bytes], Optional[Exception]]:
    """
    Safely get file content with memory management
    Returns: (content, exception)
    """
    try:
        # Check if file is too large for memory
        content = uploaded_file.getvalue()
        
        # Memory check - if content is too large, return memory error
        if len(content) > 100 * 1024 * 1024:  # 100MB limit in memory
            raise PDFMemoryError("File too large to load into memory")
        
        return content, None
    except MemoryError:
        return None, PDFMemoryError("Insufficient memory to process file")
    except Exception as e:
        return None, PDFEncodingError(f"Failed to read file content: {str(e)}")

def safe_base64_encode(content: bytes) -> Tuple[Optional[str], Optional[Exception]]:
    """
    Safely encode content to base64
    Returns: (base64_string, exception)
    """
    try:
        return base64.b64encode(content).decode('utf-8'), None
    except MemoryError:
        return None, PDFMemoryError("Insufficient memory for base64 encoding")
    except Exception as e:
        return None, PDFEncodingError(f"Base64 encoding failed: {str(e)}")

def extract_pdf_metadata(content: bytes) -> Dict[str, Any]:
    """
    Extract PDF metadata safely
    Returns: dictionary with metadata
    """
    metadata = {
        'page_count': '?',
        'title': None,
        'author': None,
        'subject': None,
        'creator': None,
        'producer': None,
        'creation_date': None,
        'modification_date': None,
        'is_encrypted': False,
        'has_errors': False,
        'error_message': None
    }
    
    try:
        from pypdf import PdfReader
        from io import BytesIO
        
        reader = PdfReader(BytesIO(content))
        metadata['page_count'] = len(reader.pages)
        metadata['is_encrypted'] = reader.is_encrypted
        
        if reader.is_encrypted:
            try:
                reader.decrypt('')  # Try empty password
            except:
                metadata['is_encrypted'] = True
        
        # Extract metadata
        if hasattr(reader, 'metadata') and reader.metadata:
            meta = reader.metadata
            metadata['title'] = getattr(meta, 'title', None)
            metadata['author'] = getattr(meta, 'author', None)
            metadata['subject'] = getattr(meta, 'subject', None)
            metadata['creator'] = getattr(meta, 'creator', None)
            metadata['producer'] = getattr(meta, 'producer', None)
            metadata['creation_date'] = getattr(meta, 'creation_date', None)
            metadata['modification_date'] = getattr(meta, 'modification_date', None)
        
    except ImportError:
        metadata['error_message'] = "pypdf library not available"
        metadata['has_errors'] = True
    except Exception as e:
        metadata['error_message'] = str(e)
        metadata['has_errors'] = True
    
    return metadata

def extract_text_preview(content: bytes, max_chars: int = 500) -> str:
    """
    Extract text preview from PDF
    Returns: text preview string
    """
    try:
        from pypdf import PdfReader
        from io import BytesIO
        
        reader = PdfReader(BytesIO(content))
        text_content = []
        chars_extracted = 0
        
        for page in reader.pages:
            try:
                page_text = page.extract_text()
                if page_text:
                    # Limit characters to prevent memory issues
                    if chars_extracted + len(page_text) > max_chars:
                        text_content.append(page_text[:max_chars - chars_extracted])
                        break
                    text_content.append(page_text)
                    chars_extracted += len(page_text)
                
                if chars_extracted >= max_chars:
                    break
                    
            except Exception:
                continue  # Skip problematic pages
        
        result = ''.join(text_content).strip()
        
        # Clean up the text
        result = re.sub(r'\s+', ' ', result)  # Normalize whitespace
        result = re.sub(r'[^\w\s.,;:!?\'"-]', '', result)  # Remove special chars
        
        return result[:max_chars]
        
    except Exception:
        return "Unable to extract text preview"

def cleanup_memory():
    """Force garbage collection to free memory"""
    try:
        gc.collect()
    except:
        pass

def render_upload_status(uploaded_file) -> None:
    """
    Show only upload status - no PDF preview/view
    """
    
    if not uploaded_file:
        st.markdown('''
        <div class="empty-state">
            <div class="empty-icon">📄</div>
            <div class="empty-title">No document yet</div>
            <div class="empty-subtitle">Upload a PDF to get started</div>
        </div>
        ''', unsafe_allow_html=True)
        return
    
    # Validate PDF file
    is_valid, error_msg = validate_pdf_file(uploaded_file)
    if not is_valid:
        st.markdown(f'''
        <div class="pdf-error-container">
            <div class="pdf-error-header">
                <div class="pdf-error-icon">❌</div>
                <div class="pdf-error-title">Invalid PDF File</div>
            </div>
            <div class="pdf-error-message">{error_msg}</div>
            <div class="pdf-error-actions">
                <div class="pdf-error-action">
                    <strong>Solution:</strong> Please upload a valid PDF file with .pdf extension and reasonable size (max 50MB)
                </div>
            </div>
        </div>
        ''', unsafe_allow_html=True)
        return
    
    file_size_kb = uploaded_file.size / 1024
    file_size_mb = file_size_kb / 1024
    
    # Show upload status only
    try:
        # Try to get basic metadata for status
        content, content_error = safe_get_file_content(uploaded_file)
        if not content_error:
            metadata = extract_pdf_metadata(content)
            page_count = metadata.get('page_count', '?')
        else:
            page_count = '?'
    except:
        page_count = '?'
    
    st.markdown(f'''
    <div class="pdf-container">
        <div class="pdf-preview-info">
            <div class="pdf-icon-large">📄</div>
            <div class="pdf-details">
                <div class="pdf-name">{uploaded_file.name}</div>
                <div class="pdf-meta">{round(file_size_kb, 1)} KB • {page_count} pages</div>
            </div>
            <div class="pdf-status">✓ Uploaded Successfully</div>
            <div class="pdf-note">Ready to generate summary</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

# Warm, colorful CSS with soft gradients
st.markdown("""
<script>
    // Set viewport meta tag dynamically
    (function() {
        var viewport = document.querySelector("meta[name=viewport]");
        if (!viewport) {
            viewport = document.createElement('meta');
            viewport.name = 'viewport';
            document.getElementsByTagName('head')[0].appendChild(viewport);
        }
        viewport.content = 'width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes';
    })();
    
    // Comprehensive mobile-first responsive handler
    function makeResponsive() {
        var width = window.innerWidth;
        var isMobile = width <= 768;
        
        // Find all column containers
        var columnContainers = document.querySelectorAll('[data-testid="column-container"]');
        var columns = document.querySelectorAll('[data-testid="column"]');
        
        if (isMobile) {
            // Mobile: Force columns to stack, hide sidebar by default
            columnContainers.forEach(function(container) {
                container.style.flexDirection = 'column';
                container.style.width = '100%';
                container.style.gap = '1rem';
            });
            
            columns.forEach(function(col) {
                col.style.width = '100%';
                col.style.flex = '1 1 100%';
                col.style.minWidth = '100%';
                col.style.maxWidth = '100%';
                col.style.display = 'block';
                col.style.marginBottom = '1rem';
            });
            
            // Auto-collapse sidebar on mobile
            var sidebar = document.querySelector('section[data-testid="stSidebar"]');
            if (sidebar) {
                var sidebarButton = document.querySelector('button[kind="header"]');
                if (sidebarButton && !sidebar.classList.contains('css-1d391kg')) {
                    // Sidebar is open, we'll let user close it manually
                }
            }
        } else if (width <= 1024) {
            // Tablet: Allow some flexibility
            columnContainers.forEach(function(container) {
                container.style.flexDirection = 'row';
            });
        } else {
            // Desktop: Normal layout
            columnContainers.forEach(function(container) {
                container.style.flexDirection = 'row';
            });
        }
        
        // Force full width on all containers
        var containers = document.querySelectorAll('.block-container, [data-testid="stAppViewContainer"]');
        containers.forEach(function(container) {
            container.style.maxWidth = '100%';
            container.style.width = '100%';
        });
    }
    
    // Run immediately and on events
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', makeResponsive);
    } else {
        makeResponsive();
    }
    
    window.addEventListener('resize', function() {
        clearTimeout(window.responsiveTimeout);
        window.responsiveTimeout = setTimeout(makeResponsive, 100);
    });
    
    // Hide icon box in file uploader
    function hideIconBox() {
        var dropzone = document.querySelector('[data-testid="stFileUploaderDropzone"]');
        if (dropzone) {
            // Find the div containing only the SVG icon and hide it
            var children = dropzone.children;
            for (var i = 0; i < children.length; i++) {
                var child = children[i];
                if (child.querySelector('svg') && !child.querySelector('button') && !child.querySelector('span')) {
                    child.style.display = 'none';
                }
            }
            // Also hide by finding SVG parent
            var svg = dropzone.querySelector('svg');
            if (svg && svg.parentElement && svg.parentElement.parentElement) {
                var iconWrapper = svg.parentElement.parentElement;
                if (!iconWrapper.querySelector('button')) {
                    iconWrapper.style.display = 'none';
                }
            }
        }
    }

    // Use MutationObserver to catch Streamlit's dynamic updates
    var observer = new MutationObserver(function(mutations) {
        makeResponsive();
        hideIconBox();
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    // Also run periodically to catch any missed updates
    setInterval(function() {
        makeResponsive();
        hideIconBox();
    }, 300);

    hideIconBox();

    // Hamburger menu toggle functionality
    function toggleSidebar() {
        var sidebar = document.querySelector('section[data-testid="stSidebar"]');
        var sidebarButton = document.querySelector('button[kind="header"]') ||
                           document.querySelector('button[data-testid="baseButton-header"]');

        if (sidebarButton) {
            sidebarButton.click();
        }
    }

    // Create hamburger menu element
    function createHamburgerMenu() {
        if (document.querySelector('.hamburger-menu')) return;

        var hamburger = document.createElement('div');
        hamburger.className = 'hamburger-menu';
        hamburger.innerHTML = '<div class="hamburger-line"></div><div class="hamburger-line"></div><div class="hamburger-line"></div>';
        hamburger.onclick = toggleSidebar;
        document.body.appendChild(hamburger);
    }

    // Initialize hamburger menu
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createHamburgerMenu);
    } else {
        createHamburgerMenu();
    }

    // Re-create if removed by Streamlit
    setInterval(function() {
        if (!document.querySelector('.hamburger-menu')) {
            createHamburgerMenu();
        }
    }, 500);
</script>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Base Reset */
    html, body {
        overflow-x: hidden !important;
        max-width: 100vw !important;
        width: 100% !important;
    }

    .stApp {
        max-width: 100% !important;
    }

    * {
        -webkit-tap-highlight-color: rgba(0,0,0,0.05);
        box-sizing: border-box;
    }

    /* Hide Streamlit defaults */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}

    /* ===== HAMBURGER MENU ===== */
    .hamburger-menu {
        position: fixed;
        top: 16px;
        left: 16px;
        z-index: 99999;
        width: 42px;
        height: 42px;
        background: #2563eb;
        border-radius: 10px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        gap: 4px;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
        transition: all 0.2s ease;
    }

    .hamburger-menu:hover {
        background: #1d4ed8;
        transform: scale(1.05);
    }

    .hamburger-menu:active {
        transform: scale(0.95);
    }

    .hamburger-line {
        width: 18px;
        height: 2px;
        background: #fff;
        border-radius: 1px;
    }

    /* Container */
    .block-container {
        padding: 1.5rem 2rem !important;
        max-width: 1400px !important;
        margin: 0 auto !important;
    }

    [data-testid="stAppViewContainer"] {
        max-width: 100% !important;
        width: 100% !important;
    }

    /* Main App */
    .stApp {
        background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        min-height: 100vh;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
        border-right: none;
    }

    section[data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }

    /* Hero Banner */
    .hero-compact {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 2rem 2.5rem;
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border-radius: 16px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
    }

    .hero-left {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .hero-icon {
        font-size: 2.5rem;
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .hero-title {
        font-size: 2rem;
        font-weight: 700;
        color: #ffffff;
        margin: 0;
        letter-spacing: -0.5px;
    }

    .hero-subtitle {
        font-size: 0.95rem;
        color: #94a3b8;
        margin: 0.25rem 0 0 0;
    }

    .hero-features {
        display: flex;
        gap: 0.75rem;
    }

    .hero-feature {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        color: #e2e8f0;
        font-size: 0.85rem;
        font-weight: 500;
        background: rgba(255,255,255,0.1);
        padding: 0.5rem 1rem;
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.1);
        transition: all 0.2s ease;
    }

    .hero-feature:hover {
        background: rgba(255,255,255,0.15);
        border-color: rgba(255,255,255,0.2);
    }

    /* Main Cards */
    .upload-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        transition: all 0.2s ease;
    }

    .upload-card:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    }

    .preview-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        transition: all 0.2s ease;
    }

    .preview-card:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    }

    .summary-section {
        background: #ffffff;
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        margin-top: 2rem;
    }

    /* Section titles */
    .section-title {
        font-size: 1rem;
        font-weight: 600;
        color: #1e293b;
        margin-bottom: 1.25rem;
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #f1f5f9;
    }

    .section-icon {
        font-size: 1.15rem;
    }

    /* Compact illustration */
    .illustration-small {
        display: none;
    }

    /* File upload styling */
    .stFileUploader {
        background: transparent !important;
    }

    .stFileUploader > div {
        background: transparent !important;
        padding: 0 !important;
    }

    .stFileUploader label {
        color: #64748b !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
    }

    .stFileUploader section {
        background: #f8fafc !important;
        border: 2px dashed #cbd5e1 !important;
        border-radius: 12px !important;
        padding: 2rem !important;
        transition: all 0.2s ease !important;
    }

    .stFileUploader section:hover {
        border-color: #3b82f6 !important;
        background: #eff6ff !important;
    }

    .stFileUploader section > div {
        background: transparent !important;
        color: #64748b !important;
        border: none !important;
    }

    .stFileUploader section > div > div {
        border: none !important;
        background: transparent !important;
    }

    .stFileUploader section span {
        color: #64748b !important;
    }

    .stFileUploader section svg {
        stroke: #3b82f6 !important;
        border: none !important;
    }

    .stFileUploader section,
    [data-testid="stFileUploaderDropzone"] {
        border: 2px dashed #cbd5e1 !important;
    }

    .stFileUploader section:hover,
    [data-testid="stFileUploaderDropzone"]:hover {
        border: 2px dashed #3b82f6 !important;
    }

    /* Remove ALL borders inside file uploader except the main dashed border */
    .stFileUploader section *:not(button),
    [data-testid="stFileUploaderDropzone"] *:not(button) {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
    }

    .stFileUploader section button {
        background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
        color: white !important;
        border: none !important;
        border-color: transparent !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.25rem !important;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3) !important;
    }

    /* Ensure Browse files button has proper border */
    .stFileUploader button {
        border: none !important;
    }

    .stFileUploader section small {
        color: #94a3b8 !important;
    }

    [data-testid="stFileUploader"] > section > div {
        background: transparent !important;
    }

    [data-testid="stFileUploaderDropzone"] {
        background: #f8fafc !important;
        border: 2px dashed #cbd5e1 !important;
        border-radius: 12px !important;
        transition: all 0.2s ease !important;
    }

    [data-testid="stFileUploaderDropzone"]:hover {
        border-color: #3b82f6 !important;
        background: #eff6ff !important;
    }

    [data-testid="stFileUploaderDropzone"] div {
        background: transparent !important;
        border: none !important;
    }

    [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stFileUploaderDropzone"] p {
        color: #64748b !important;
    }

    [data-testid="stFileUploaderDropzone"] button {
        background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
    }

    /* Hide the icon with box completely - clean look */
    [data-testid="stFileUploaderDropzone"] > div:first-child {
        display: none !important;
    }

    /* Style the dropzone content */
    [data-testid="stFileUploaderDropzone"] {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 1rem !important;
        padding: 1.5rem !important;
    }

    [data-testid="stFileUploaderDropzone"] > div {
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
    }

    .uploadedFile {
        background: #ecfdf5 !important;
        border: 1px solid #6ee7b7 !important;
        border-radius: 8px !important;
    }

    /* File info */
    .file-info {
        background: linear-gradient(135deg, #ecfdf5, #d1fae5);
        border: 1px solid #6ee7b7;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        display: flex;
        align-items: center;
        gap: 1rem;
        margin: 1.25rem 0;
    }

    .file-icon-box {
        width: 44px;
        height: 44px;
        background: linear-gradient(135deg, #10b981, #059669);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.25);
    }

    .file-details h4 {
        margin: 0;
        font-size: 0.95rem;
        color: #065f46;
        font-weight: 600;
    }

    .file-details p {
        margin: 0.2rem 0 0 0;
        font-size: 0.8rem;
        color: #059669;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.75rem 1.5rem;
        font-size: 0.95rem;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
        transition: all 0.2s ease;
        width: 100%;
        min-height: 48px;
        cursor: pointer;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.25);
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35);
        transform: translateY(-1px);
    }

    .stButton > button:active {
        transform: translateY(0);
    }

    .stDownloadButton > button {
        background: linear-gradient(135deg, #10b981, #059669);
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.25);
    }

    .stDownloadButton > button:hover {
        background: linear-gradient(135deg, #059669, #047857);
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.35);
    }

    /* Summary cards */
    .summary-card {
        background: #ffffff;
        border-radius: 14px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
        transition: all 0.2s ease;
    }

    .summary-card:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
    }

    .summary-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding-bottom: 0.75rem;
        margin-bottom: 0.75rem;
        border-bottom: 1px solid #f1f5f9;
    }

    .summary-file-icon {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.1rem;
        box-shadow: 0 2px 6px rgba(59, 130, 246, 0.2);
    }

    .summary-file-info h4 {
        margin: 0;
        font-size: 0.95rem;
        color: #1e293b;
        font-weight: 600;
    }

    .summary-file-info span {
        font-size: 0.75rem;
        color: #64748b;
    }

    .summary-content {
        color: #475569;
        line-height: 1.75;
        font-size: 0.9rem;
    }

    .summary-badge {
        margin-left: auto;
        background: linear-gradient(135deg, #8b5cf6, #7c3aed);
        color: white;
        padding: 0.35rem 0.75rem;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 600;
    }

    /* Summary action buttons */
    .summary-section .stButton > button {
        font-size: 0.85rem !important;
        padding: 0.6rem 1rem !important;
        min-height: 40px !important;
        border-radius: 8px !important;
    }

    .summary-section .stDownloadButton > button {
        font-size: 0.85rem !important;
        padding: 0.6rem 1rem !important;
        min-height: 40px !important;
        border-radius: 8px !important;
    }

    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 3rem 2rem;
        background: linear-gradient(135deg, #f8fafc, #f1f5f9);
        border-radius: 14px;
        border: 2px dashed #e2e8f0;
    }

    .empty-icon {
        font-size: 3rem;
        margin-bottom: 0.75rem;
        opacity: 0.6;
    }

    .empty-title {
        font-size: 1rem;
        font-weight: 600;
        color: #475569;
        margin-bottom: 0.35rem;
    }

    .empty-subtitle {
        color: #94a3b8;
        font-size: 0.875rem;
    }

    /* Stats in sidebar */
    .stat-box {
        background: rgba(59, 130, 246, 0.15);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        border: 1px solid rgba(59, 130, 246, 0.2);
    }

    .stat-number {
        font-size: 1.75rem;
        font-weight: 700;
        color: #60a5fa !important;
    }

    .stat-label {
        font-size: 0.75rem;
        color: #94a3b8 !important;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* PDF Preview */
    .pdf-container {
        background: #f8fafc;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #e2e8f0;
    }

    .pdf-preview-info {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        gap: 1rem;
        padding: 2rem 1rem;
    }

    .pdf-icon-large {
        font-size: 4rem;
        line-height: 1;
    }

    .pdf-details {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }

    .pdf-name {
        font-weight: 600;
        color: #1e293b;
        font-size: 1rem;
        word-break: break-word;
    }

    .pdf-meta {
        color: #64748b;
        font-size: 0.85rem;
    }

    .pdf-status {
        background: #ecfdf5;
        color: #059669;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
    }

    .pdf-note {
        color: #94a3b8;
        font-size: 0.75rem;
        margin-top: 0.5rem;
    }

    .pdf-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding-bottom: 0.75rem;
        margin-bottom: 0.75rem;
        border-bottom: 1px solid #e2e8f0;
        color: #475569;
        font-weight: 600;
        font-size: 0.85rem;
    }

    /* PDF Preview Error States */
    .pdf-error-container {
        background: linear-gradient(135deg, #fef2f2, #fee2e2);
        border: 1px solid #fca5a5;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }

    .pdf-error-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 1rem;
    }

    .pdf-error-icon {
        font-size: 1.5rem;
        flex-shrink: 0;
    }

    .pdf-error-title {
        font-weight: 600;
        color: #991b1b;
        font-size: 1rem;
    }

    .pdf-error-message {
        color: #dc2626;
        font-size: 0.875rem;
        margin-bottom: 1rem;
        line-height: 1.5;
    }

    .pdf-error-actions {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .pdf-error-action {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.75rem;
        font-size: 0.8rem;
        color: #475569;
    }

    .pdf-error-action strong {
        color: #1e293b;
    }

    /* PDF Preview Fallback States */
    .pdf-fallback-container {
        background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
        border: 1px solid #7dd3fc;
        border-radius: 12px;
        padding: 1.5rem;
    }

    .pdf-fallback-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 1rem;
        color: #0c4a6e;
        font-weight: 600;
        font-size: 0.9rem;
    }

    .pdf-fallback-content {
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .pdf-metadata-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 0.75rem;
        font-size: 0.85rem;
    }

    .pdf-metadata-item {
        background: #f8fafc;
        padding: 0.5rem 0.75rem;
        border-radius: 6px;
        border: 1px solid #e2e8f0;
    }

    .pdf-metadata-label {
        color: #64748b;
        font-size: 0.75rem;
        margin-bottom: 0.25rem;
    }

    .pdf-metadata-value {
        color: #1e293b;
        font-weight: 500;
    }

    .pdf-text-preview {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem;
        font-size: 0.85rem;
        color: #475569;
        line-height: 1.5;
        max-height: 150px;
        overflow-y: auto;
    }

    .pdf-text-preview::-webkit-scrollbar {
        width: 6px;
    }

    .pdf-text-preview::-webkit-scrollbar-track {
        background: #f1f5f9;
        border-radius: 3px;
    }

    .pdf-text-preview::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 3px;
    }

    .pdf-loading-preview {
        background: linear-gradient(135deg, #eff6ff, #dbeafe);
        border: 1px solid #bfdbfe;
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
    }

    .pdf-loading-spinner {
        width: 32px;
        height: 32px;
        border: 2px solid #dbeafe;
        border-top: 2px solid #3b82f6;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 0 auto 1rem;
    }

    .pdf-loading-text {
        color: #1e40af;
        font-weight: 600;
        font-size: 0.9rem;
        margin-bottom: 0.25rem;
    }

    .pdf-loading-subtext {
        color: #3b82f6;
        font-size: 0.8rem;
    }

    /* Loading */
    .loading-container {
        text-align: center;
        padding: 2.5rem;
        background: linear-gradient(135deg, #eff6ff, #dbeafe);
        border-radius: 14px;
        border: 1px solid #bfdbfe;
    }

    .loading-spinner {
        width: 44px;
        height: 44px;
        border: 3px solid #dbeafe;
        border-top: 3px solid #3b82f6;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
        margin: 0 auto 1rem;
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    .loading-text {
        font-size: 1rem;
        font-weight: 600;
        color: #1e40af;
    }

    .loading-subtext {
        color: #3b82f6;
        font-size: 0.85rem;
        margin-top: 0.25rem;
    }

    /* Error box */
    .error-box {
        background: linear-gradient(135deg, #fef2f2, #fee2e2);
        border: 1px solid #fca5a5;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        display: flex;
        align-items: center;
        gap: 0.6rem;
        color: #dc2626;
        font-weight: 500;
        font-size: 0.9rem;
    }

    /* Sidebar content */
    .sidebar-logo {
        text-align: center;
        padding: 1.5rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 1.5rem;
    }

    .sidebar-logo-icon {
        font-size: 2.25rem;
        margin-bottom: 0.25rem;
    }

    .sidebar-logo-text {
        font-size: 1.35rem;
        font-weight: 700;
        color: #fff !important;
    }

    .sidebar-logo-tagline {
        font-size: 0.8rem;
        color: #94a3b8 !important;
        margin-top: 0.2rem;
    }

    .sidebar-divider {
        height: 1px;
        background: rgba(255, 255, 255, 0.08);
        margin: 1.25rem 0;
    }

    /* How it works */
    .steps-container {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1.25rem;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }

    .steps-title {
        font-weight: 600;
        color: #e2e8f0 !important;
        margin-bottom: 1rem;
        font-size: 0.9rem;
    }

    .step-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.75rem;
    }

    .step-item:last-child {
        margin-bottom: 0;
    }

    .step-number {
        width: 24px;
        height: 24px;
        background: linear-gradient(135deg, #3b82f6, #2563eb);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 0.7rem;
        font-weight: 700;
        flex-shrink: 0;
    }

    .step-text {
        color: #cbd5e1 !important;
        font-size: 0.85rem;
        font-weight: 400;
    }

    /* ===== RESPONSIVE - Universal Base Styles ===== */
    /* Force all containers to be responsive */
    .stApp, .stApp > div, [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > div,
    main[data-testid="stAppViewContainer"] {
        max-width: 100% !important;
        width: 100% !important;
    }
    
    /* Make columns responsive by default */
    [data-testid="column-container"] {
        display: flex !important;
        width: 100% !important;
        flex-wrap: wrap !important;
    }
    
    [data-testid="column"] {
        flex: 1 1 auto !important;
        min-width: 0 !important;
        max-width: 100% !important;
    }
    
    /* ===== MOBILE RESPONSIVE ===== */
    @media screen and (max-width: 768px) {
        * {
            max-width: 100vw !important;
        }

        .block-container {
            padding: 1rem !important;
        }

        /* Stack columns */
        [data-testid="column-container"] {
            flex-direction: column !important;
            gap: 1rem !important;
        }

        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
            max-width: 100% !important;
        }

        /* Sidebar */
        section[data-testid="stSidebar"] {
            min-width: 260px !important;
            max-width: 85vw !important;
        }

        /* Hide default toggle */
        button[kind="header"],
        button[data-testid="baseButton-header"] {
            display: none !important;
        }

        /* Hamburger stays same */
        .hamburger-menu {
            top: 12px;
            left: 12px;
        }

        /* Hero */
        .hero-compact {
            flex-direction: column !important;
            text-align: center !important;
            padding: 1.25rem !important;
            gap: 1rem !important;
        }

        .hero-left {
            flex-direction: column !important;
            gap: 0.5rem !important;
        }

        .hero-icon {
            font-size: 2rem !important;
        }

        .hero-title {
            font-size: 1.5rem !important;
        }

        .hero-subtitle {
            font-size: 0.85rem !important;
        }

        .hero-features {
            flex-wrap: wrap !important;
            justify-content: center !important;
            gap: 0.5rem !important;
        }

        .hero-feature {
            font-size: 0.75rem !important;
            padding: 0.4rem 0.75rem !important;
        }

        /* Cards */
        .upload-card, .preview-card, .summary-section {
            padding: 1.25rem !important;
            border-radius: 14px !important;
        }

        .section-title {
            font-size: 0.95rem !important;
        }

        /* Summary */
        .summary-card {
            padding: 1rem !important;
        }

        .summary-content {
            font-size: 0.85rem !important;
        }

        /* Buttons */
        .stButton > button {
            min-height: 46px !important;
            font-size: 0.9rem !important;
        }

        .empty-state {
            padding: 2rem 1.5rem !important;
        }

        .pdf-container iframe {
            height: 280px !important;
        }

        .stFileUploader section {
            padding: 1.5rem !important;
        }
    }

    /* Small phones */
    @media screen and (max-width: 480px) {
        .block-container {
            padding: 0.75rem !important;
        }

        .hero-compact {
            padding: 1rem !important;
        }

        .hero-title {
            font-size: 1.25rem !important;
        }

        .hero-features {
            display: none !important;
        }

        .pdf-container iframe {
            height: 220px !important;
        }
        
        .sidebar-logo-icon {
            font-size: 1.8rem !important;
        }
    }
    
    /* Extra small devices */
    @media screen and (max-width: 360px) {
        .hero-title {
            font-size: 1.1rem;
        }
        .hero-subtitle {
            font-size: 0.7rem;
        }
        .section-title {
            font-size: 0.85rem;
        }
        .summary-content {
            font-size: 0.75rem;
        }
    }
    
    /* Landscape mobile orientation */
    @media screen and (max-width: 768px) and (orientation: landscape) {
        .pdf-container iframe {
            height: 180px !important;
        }
        .hero-compact {
            padding: 0.8rem 1rem;
        }
    }
    
    /* Tablet adjustments */
    @media screen and (min-width: 769px) and (max-width: 1024px) {
        /* Allow columns to work but with adjusted sizing */
        [data-testid="column-container"] {
            flex-direction: row !important;
        }
        
        [data-testid="column"] {
            flex: 1 1 auto !important;
            min-width: 0 !important;
        }
        
        .hero-compact {
            padding: 1rem 1.5rem;
        }
        .upload-card, .preview-card {
            padding: 1.2rem;
        }
        .pdf-container iframe {
            height: 300px !important;
        }
    }
    
    /* Large screens - ensure proper layout */
    @media screen and (min-width: 1025px) {
        [data-testid="column-container"] {
            flex-direction: row !important;
        }
        
        [data-testid="column"] {
            flex: 1 1 auto !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# Small SVG Illustration
small_illustration = '''
<svg viewBox="0 0 200 140" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="100" cy="70" r="50" fill="#FEF3C7" opacity="0.8"/>
  <circle cx="160" cy="35" r="25" fill="#FBCFE8" opacity="0.6"/>
  <circle cx="40" cy="90" r="20" fill="#A7F3D0" opacity="0.6"/>

  <rect x="60" y="25" width="60" height="80" rx="8" fill="#FEF9C3" stroke="#FBBF24" stroke-width="2"/>
  <rect x="70" y="40" width="35" height="5" rx="2" fill="#FCD34D"/>
  <rect x="70" y="50" width="40" height="4" rx="2" fill="#FDE68A"/>
  <rect x="70" y="58" width="30" height="4" rx="2" fill="#FDE68A"/>
  <rect x="70" y="66" width="38" height="4" rx="2" fill="#FDE68A"/>
  <rect x="70" y="74" width="32" height="4" rx="2" fill="#FDE68A"/>

  <circle cx="140" cy="60" r="20" fill="url(#grad1)"/>
  <path d="M140 48 L142 56 L150 58 L142 60 L140 68 L138 60 L130 58 L138 56 Z" fill="white"/>

  <rect x="130" y="85" width="55" height="40" rx="6" fill="#D1FAE5" stroke="#34D399" stroke-width="2"/>
  <rect x="140" y="95" width="25" height="4" rx="2" fill="#34D399"/>
  <rect x="140" y="103" width="35" height="3" rx="1" fill="#A7F3D0"/>
  <rect x="140" y="110" width="30" height="3" rx="1" fill="#A7F3D0"/>

  <circle cx="175" cy="90" r="10" fill="#10B981"/>
  <path d="M170 90 L173 93 L180 86" stroke="white" stroke-width="2" stroke-linecap="round"/>

  <defs>
    <linearGradient id="grad1" x1="120" y1="40" x2="160" y2="80">
      <stop offset="0%" stop-color="#F97316"/>
      <stop offset="100%" stop-color="#EC4899"/>
    </linearGradient>
  </defs>
</svg>
'''

# Sidebar
with st.sidebar:
    st.markdown('''
    <div class="sidebar-logo">
        <div class="sidebar-logo-icon">📄</div>
        <div class="sidebar-logo-text">Sumlyzer</div>
        <div class="sidebar-logo-tagline">Smart PDF Summarizer</div>
    </div>
    ''', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f'''
        <div class="stat-box">
            <div class="stat-number">{len(st.session_state.chat_history)}</div>
            <div class="stat-label">Summaries</div>
        </div>
        ''', unsafe_allow_html=True)
    with col2:
        st.markdown(f'''
        <div class="stat-box">
            <div class="stat-number">{st.session_state.total_pages}</div>
            <div class="stat-label">Pages</div>
        </div>
        ''', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    if st.session_state.chat_history:
        history_text = "\n\n".join([f"📄 {m.get('pdf', 'Document')}\n{'='*40}\n{m['ai']}" for m in st.session_state.chat_history])
        st.download_button(
            "📥 Download All",
            history_text,
            file_name=f"sumlyzer_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            use_container_width=True
        )

    if st.button("🗑️ Clear History", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.total_pages = 0
        st.rerun()

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    st.markdown('''
    <div class="steps-container">
        <div class="steps-title">📌 How it works</div>
        <div class="step-item">
            <div class="step-number">1</div>
            <div class="step-text">Upload your PDF</div>
        </div>
        <div class="step-item">
            <div class="step-number">2</div>
            <div class="step-text">Click Generate</div>
        </div>
        <div class="step-item">
            <div class="step-number">3</div>
            <div class="step-text">Get AI summary</div>
        </div>
        <div class="step-item">
            <div class="step-number">4</div>
            <div class="step-text">Download results</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

# Main content - Compact Hero at top
st.markdown('''
<div class="hero-compact">
    <div class="hero-left">
        <span class="hero-icon">📄</span>
        <div>
            <h1 class="hero-title">Sumlyzer</h1>
            <p class="hero-subtitle">Transform PDFs into concise AI summaries</p>
        </div>
    </div>
    <div class="hero-features">
        <div class="hero-feature">⚡ Fast</div>
        <div class="hero-feature">🎯 Accurate</div>
        <div class="hero-feature">📥 Export</div>
    </div>
</div>
''', unsafe_allow_html=True)

# Upload and Preview - Fully Responsive columns
# Columns will automatically stack on mobile via CSS and JavaScript
# Using equal width on mobile, proportional on desktop
col1, col2 = st.columns(2, gap="medium")

with col1:
    st.markdown('''
    <div class="upload-card">
        <div class="section-title">
            <span class="section-icon">📤</span> Upload Document
        </div>
    ''', unsafe_allow_html=True)

    st.markdown(f'<div class="illustration-small">{small_illustration}</div>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Drop PDF here or click to browse",
        type="pdf",
        key="pdf_uploader"
    )

    if uploaded_file:
        st.markdown(f'''
        <div class="file-info">
            <div class="file-icon-box">📄</div>
            <div class="file-details">
                <h4>{uploaded_file.name}</h4>
                <p>{round(uploaded_file.size / 1024, 1)} KB • Ready!</p>
            </div>
        </div>
        ''', unsafe_allow_html=True)

        ask_question = st.button("✨ Generate Summary", use_container_width=True)
    else:
        ask_question = False

    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('''
    <div class="preview-card">
        <div class="section-title">
            <span class="section-icon">📄</span> Document Viewer
        </div>
''', unsafe_allow_html=True)

    # Render upload status only
    render_upload_status(uploaded_file)

    st.markdown('</div>', unsafe_allow_html=True)

# Summaries section
st.markdown('''
<div class="summary-section">
    <div class="section-title">
        <span class="section-icon">📝</span> Your Summaries
    </div>
''', unsafe_allow_html=True)

# Process
if ask_question and uploaded_file:
    processing = st.empty()
    processing.markdown('''
    <div class="loading-container">
        <div class="loading-spinner"></div>
        <div class="loading-text">Analyzing document...</div>
        <div class="loading-subtext">This takes 10-30 seconds</div>
    </div>
    ''', unsafe_allow_html=True)

    try:
        current_pdf_name = uploaded_file.name
        if st.session_state.last_pdf_name != current_pdf_name:
            pdf_file_path = upload_pdf(uploaded_file)
            st.session_state.faiss_db = create_faiss_db(pdf_file_path)
            st.session_state.last_pdf_name = current_pdf_name

        fixed_prompt = "Summarize the main points of the document in 5 to 10 bullet points."
        retrieved_docs = retrieve_summary(fixed_prompt, st.session_state.faiss_db)
        response = answer_query(documents=retrieved_docs, model=llm_model, query=fixed_prompt)

        try:
            from pypdf import PdfReader
            from io import BytesIO
            reader = PdfReader(BytesIO(uploaded_file.getvalue()))
            st.session_state.total_pages += len(reader.pages)
        except:
            pass

        st.session_state.chat_history.append({
            "ai": response,
            "pdf": uploaded_file.name,
            "time": datetime.now().strftime("%I:%M %p")
        })

        processing.empty()
        st.rerun()

    except Exception as e:
        processing.empty()
        st.markdown(f'''
        <div class="error-box">
            <span>⚠️</span>
            <span>Error: {str(e)}</span>
        </div>
        ''', unsafe_allow_html=True)
        with open("error_log.txt", "a") as f:
            f.write(f"[{time.ctime()}] Error: {e}\n")

# Display summaries with individual actions
if st.session_state.chat_history:
    for idx, message in enumerate(reversed(st.session_state.chat_history)):
        actual_idx = len(st.session_state.chat_history) - 1 - idx
        pdf_name = message.get('pdf', 'Document')
        summary_time = message.get('time', '')

        st.markdown(f'''
        <div class="summary-card">
            <div class="summary-header">
                <div class="summary-file-icon">📄</div>
                <div class="summary-file-info">
                    <h4>{pdf_name}</h4>
                    <span>{summary_time}</span>
                </div>
                <div class="summary-badge">✨ AI Summary</div>
            </div>
            <div class="summary-content">
                {message['ai'].replace(chr(10), '<br>')}
            </div>
        </div>
        ''', unsafe_allow_html=True)

        # Action buttons for each summary
        col_dl, col_del = st.columns([1, 1])
        with col_dl:
            summary_text = f"📄 {pdf_name}\n{'='*40}\n{message['ai']}"
            st.download_button(
                "📥 Download",
                summary_text,
                file_name=f"{pdf_name.replace('.pdf', '')}_summary.txt",
                key=f"download_{actual_idx}",
                use_container_width=True
            )
        with col_del:
            if st.button("🗑️ Delete", key=f"delete_{actual_idx}", use_container_width=True):
                st.session_state.chat_history.pop(actual_idx)
                st.rerun()
else:
    st.markdown('''
    <div class="empty-state">
        <div class="empty-icon">📋</div>
        <div class="empty-title">No summaries yet</div>
        <div class="empty-subtitle">Upload a PDF and click "Generate Summary"</div>
    </div>
    ''', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
