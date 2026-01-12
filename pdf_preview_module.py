import streamlit as st
import base64
import logging
from io import BytesIO
from typing import Optional, Tuple, Dict, Any
import hashlib
import time

# Configure logging for PDF preview operations
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# PDF processing constants
MAX_PREVIEW_SIZE_MB = 5
MAX_LARGE_FILE_SIZE_MB = 50
MAX_MEMORY_SIZE_MB = 100
PDF_SIGNATURE = b'%PDF-'
SUPPORTED_MIME_TYPES = ['application/pdf']

class PDFPreviewError(Exception):
    """Base exception for PDF preview operations"""
    pass

class PDFValidationError(PDFPreviewError):
    """Raised when PDF validation fails"""
    pass

class PDFMemoryError(PDFPreviewError):
    """Raised when PDF is too large for memory operations"""
    pass

class PDFProcessingError(PDFPreviewError):
    """Raised when PDF processing fails"""
    pass

def validate_pdf_file(uploaded_file) -> None:
    """
    Validate PDF file structure and security
    
    Args:
        uploaded_file: Streamlit uploaded file object
        
    Raises:
        PDFValidationError: If file validation fails
    """
    if not uploaded_file:
        raise PDFValidationError("No file provided")
    
    # Check file type
    if uploaded_file.type not in SUPPORTED_MIME_TYPES:
        raise PDFValidationError(f"Unsupported file type: {uploaded_file.type}")
    
    # Check file size
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > MAX_LARGE_FILE_SIZE_MB:
        raise PDFValidationError(f"File too large: {file_size_mb:.1f}MB (max: {MAX_LARGE_FILE_SIZE_MB}MB)")
    
    # Check PDF signature
    try:
        file_content = uploaded_file.getvalue()
        if not file_content.startswith(PDF_SIGNATURE):
            raise PDFValidationError("Invalid PDF file signature")
    except Exception as e:
        raise PDFValidationError(f"Failed to read file content: {str(e)}")

def get_pdf_metadata(uploaded_file) -> Dict[str, Any]:
    """
    Extract PDF metadata safely
    
    Args:
        uploaded_file: Streamlit uploaded file object
        
    Returns:
        Dictionary containing PDF metadata
        
    Raises:
        PDFProcessingError: If metadata extraction fails
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(uploaded_file.getvalue()))
        
        metadata = {
            'page_count': len(reader.pages),
            'is_encrypted': reader.is_encrypted,
            'has_metadata': bool(reader.metadata),
        }
        
        # Extract additional metadata if available
        if reader.metadata:
            metadata.update({
                'title': reader.metadata.get('/Title', ''),
                'author': reader.metadata.get('/Author', ''),
                'subject': reader.metadata.get('/Subject', ''),
                'creator': reader.metadata.get('/Creator', ''),
                'producer': reader.metadata.get('/Producer', ''),
                'creation_date': reader.metadata.get('/CreationDate', ''),
            })
        
        return metadata
        
    except Exception as e:
        logger.error(f"Failed to extract PDF metadata: {str(e)}")
        raise PDFProcessingError(f"Metadata extraction failed: {str(e)}")

def get_pdf_text_preview(uploaded_file, max_chars: int = 500) -> str:
    """
    Extract text preview from PDF
    
    Args:
        uploaded_file: Streamlit uploaded file object
        max_chars: Maximum characters to extract
        
    Returns:
        Text preview string
        
    Raises:
        PDFProcessingError: If text extraction fails
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(uploaded_file.getvalue()))
        
        text_preview = ""
        for i, page in enumerate(reader.pages):
            if len(text_preview) >= max_chars:
                break
            try:
                page_text = page.extract_text()
                if page_text:
                    text_preview += page_text + "\n"
            except Exception as e:
                logger.warning(f"Failed to extract text from page {i+1}: {str(e)}")
                continue
        
        return text_preview[:max_chars].strip()
        
    except Exception as e:
        logger.error(f"Failed to extract PDF text preview: {str(e)}")
        raise PDFProcessingError(f"Text extraction failed: {str(e)}")

def create_base64_preview(uploaded_file) -> str:
    """
    Create base64 encoded PDF preview
    
    Args:
        uploaded_file: Streamlit uploaded file object
        
    Returns:
        Base64 encoded PDF string
        
    Raises:
        PDFMemoryError: If file is too large for base64 encoding
        PDFProcessingError: If encoding fails
    """
    try:
        file_size_mb = uploaded_file.size / (1024 * 1024)
        if file_size_mb > MAX_PREVIEW_SIZE_MB:
            raise PDFMemoryError(f"File too large for preview: {file_size_mb:.1f}MB")
        
        pdf_bytes = uploaded_file.getvalue()
        base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        
        # Validate base64 encoding
        if not base64_pdf:
            raise PDFProcessingError("Base64 encoding resulted in empty string")
        
        return base64_pdf
        
    except MemoryError:
        raise PDFMemoryError("Insufficient memory for base64 encoding")
    except Exception as e:
        logger.error(f"Failed to create base64 preview: {str(e)}")
        raise PDFProcessingError(f"Base64 encoding failed: {str(e)}")

def render_pdf_iframe(base64_pdf: str, file_name: str, file_size_kb: float) -> None:
    """
    Render PDF iframe with base64 content
    
    Args:
        base64_pdf: Base64 encoded PDF
        file_name: Original file name
        file_size_kb: File size in KB
    """
    st.markdown(f'''
    <div class="pdf-container">
        <div class="pdf-header">📄 {file_name} ({round(file_size_kb, 1)} KB)</div>
        <iframe src="data:application/pdf;base64,{base64_pdf}"
                width="100%" height="350px"
                style="border: none; border-radius: 8px;">
        </iframe>
    </div>
    ''', unsafe_allow_html=True)

def render_metadata_preview(metadata: Dict[str, Any], file_name: str, file_size_mb: float) -> None:
    """
    Render PDF metadata preview
    
    Args:
        metadata: PDF metadata dictionary
        file_name: Original file name
        file_size_mb: File size in MB
    """
    page_count = metadata.get('page_count', '?')
    is_encrypted = "🔒" if metadata.get('is_encrypted', False) else "🔓"
    
    st.markdown(f'''
    <div class="pdf-container">
        <div class="pdf-preview-info">
            <div class="pdf-icon-large">📄</div>
            <div class="pdf-details">
                <div class="pdf-name">{file_name}</div>
                <div class="pdf-meta">{round(file_size_mb, 1)} MB • {page_count} pages {is_encrypted}</div>
            </div>
            <div class="pdf-status">✓ Ready to summarize</div>
            <div class="pdf-note">Metadata preview</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

def render_text_preview(text_preview: str, file_name: str, file_size_mb: float) -> None:
    """
    Render PDF text preview
    
    Args:
        text_preview: Extracted text preview
        file_name: Original file name
        file_size_mb: File size in MB
    """
    # Escape HTML characters in text preview
    escaped_text = text_preview.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    st.markdown(f'''
    <div class="pdf-container">
        <div class="pdf-header">📄 {file_name} ({round(file_size_mb, 1)} MB)</div>
        <div class="pdf-text-preview">
            <div class="pdf-preview-text">{escaped_text}</div>
            <div class="pdf-preview-note">Text preview (first 500 characters)</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

def render_basic_info_preview(file_name: str, file_size_mb: float) -> None:
    """
    Render basic file information preview
    
    Args:
        file_name: Original file name
        file_size_mb: File size in MB
    """
    st.markdown(f'''
    <div class="pdf-container">
        <div class="pdf-preview-info">
            <div class="pdf-icon-large">📄</div>
            <div class="pdf-details">
                <div class="pdf-name">{file_name}</div>
                <div class="pdf-meta">{round(file_size_mb, 1)} MB</div>
            </div>
            <div class="pdf-status">✓ Ready to summarize</div>
            <div class="pdf-note">Basic file info</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

def render_error_state(error_message: str, file_name: str = None) -> None:
    """
    Render error state with user-friendly message
    
    Args:
        error_message: Error message to display
        file_name: Optional file name for context
    """
    st.markdown(f'''
    <div class="pdf-container error-state">
        <div class="pdf-preview-info">
            <div class="pdf-icon-large">⚠️</div>
            <div class="pdf-details">
                <div class="pdf-name">{file_name or "PDF File"}</div>
                <div class="pdf-error">{error_message}</div>
            </div>
            <div class="pdf-status">❌ Preview unavailable</div>
            <div class="pdf-note">File will still be processed for summarization</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

def render_loading_state() -> None:
    """Render loading state for PDF preview"""
    st.markdown('''
    <div class="pdf-container loading-state">
        <div class="pdf-preview-info">
            <div class="pdf-icon-large">⏳</div>
            <div class="pdf-details">
                <div class="pdf-name">Processing PDF...</div>
                <div class="pdf-loading">Generating preview</div>
            </div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

def render_empty_state() -> None:
    """Render empty state when no file is uploaded"""
    st.markdown('''
    <div class="empty-state">
        <div class="empty-icon">📄</div>
        <div class="empty-title">No document yet</div>
        <div class="empty-subtitle">Upload a PDF to preview</div>
    </div>
    ''', unsafe_allow_html=True)

def process_pdf_preview(uploaded_file) -> None:
    """
    Main function to process and render PDF preview with comprehensive error handling
    
    Args:
        uploaded_file: Streamlit uploaded file object
    """
    if not uploaded_file:
        render_empty_state()
        return
    
    file_size_kb = uploaded_file.size / 1024
    file_size_mb = file_size_kb / 1024
    file_name = uploaded_file.name
    
    # Show loading state initially
    render_loading_state()
    
    try:
        # Validate PDF file
        validate_pdf_file(uploaded_file)
        
        # 4-tier fallback system
        preview_success = False
        
        # Tier 1: Base64 preview for small files
        if file_size_mb < MAX_PREVIEW_SIZE_MB:
            try:
                base64_pdf = create_base64_preview(uploaded_file)
                render_pdf_iframe(base64_pdf, file_name, file_size_kb)
                preview_success = True
                logger.info(f"Successfully rendered base64 preview for {file_name}")
            except (PDFMemoryError, PDFProcessingError) as e:
                logger.warning(f"Base64 preview failed for {file_name}: {str(e)}")
        
        # Tier 2: Metadata preview
        if not preview_success:
            try:
                metadata = get_pdf_metadata(uploaded_file)
                render_metadata_preview(metadata, file_name, file_size_mb)
                preview_success = True
                logger.info(f"Successfully rendered metadata preview for {file_name}")
            except PDFProcessingError as e:
                logger.warning(f"Metadata preview failed for {file_name}: {str(e)}")
        
        # Tier 3: Text preview
        if not preview_success:
            try:
                text_preview = get_pdf_text_preview(uploaded_file)
                if text_preview:
                    render_text_preview(text_preview, file_name, file_size_mb)
                    preview_success = True
                    logger.info(f"Successfully rendered text preview for {file_name}")
                else:
                    logger.warning(f"No text extracted from {file_name}")
            except PDFProcessingError as e:
                logger.warning(f"Text preview failed for {file_name}: {str(e)}")
        
        # Tier 4: Basic info preview (always succeeds)
        if not preview_success:
            render_basic_info_preview(file_name, file_size_mb)
            logger.info(f"Rendered basic info preview for {file_name}")
        
    except PDFValidationError as e:
        logger.error(f"PDF validation failed for {file_name}: {str(e)}")
        render_error_state(f"Invalid PDF file: {str(e)}", file_name)
        
    except Exception as e:
        logger.error(f"Unexpected error processing {file_name}: {str(e)}")
        render_error_state("Preview generation failed", file_name)

# CSS for enhanced preview states
st.markdown("""
<style>
.pdf-container {
    border: 1px solid #e1e5e9;
    border-radius: 12px;
    overflow: hidden;
    background: white;
    margin-bottom: 1rem;
}

.pdf-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 12px 16px;
    font-weight: 600;
    font-size: 14px;
}

.pdf-preview-info {
    display: flex;
    align-items: center;
    padding: 20px;
    gap: 16px;
}

.pdf-icon-large {
    font-size: 48px;
    flex-shrink: 0;
}

.pdf-details {
    flex: 1;
}

.pdf-name {
    font-weight: 600;
    font-size: 16px;
    color: #1a202c;
    margin-bottom: 4px;
    word-break: break-all;
}

.pdf-meta {
    font-size: 14px;
    color: #718096;
    margin-bottom: 8px;
}

.pdf-status {
    font-size: 14px;
    color: #48bb78;
    font-weight: 500;
}

.pdf-note {
    font-size: 12px;
    color: #a0aec0;
    margin-top: 4px;
}

.pdf-error {
    font-size: 14px;
    color: #e53e3e;
    margin-bottom: 8px;
}

.pdf-text-preview {
    padding: 20px;
}

.pdf-preview-text {
    background: #f7fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 16px;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    color: #2d3748;
    max-height: 200px;
    overflow-y: auto;
    white-space: pre-wrap;
    margin-bottom: 12px;
}

.pdf-preview-note {
    font-size: 12px;
    color: #718096;
    text-align: center;
}

.error-state .pdf-preview-info {
    background: #fff5f5;
    border-left: 4px solid #fc8181;
}

.loading-state .pdf-preview-info {
    background: #f0fff4;
    border-left: 4px solid #68d391;
}

.empty-state {
    text-align: center;
    padding: 40px 20px;
    color: #718096;
}

.empty-icon {
    font-size: 48px;
    margin-bottom: 16px;
}

.empty-title {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 8px;
    color: #2d3748;
}

.empty-subtitle {
    font-size: 14px;
    color: #a0aec0;
}

/* Mobile responsiveness */
@media (max-width: 768px) {
    .pdf-preview-info {
        padding: 16px;
        gap: 12px;
    }
    
    .pdf-icon-large {
        font-size: 36px;
    }
    
    .pdf-name {
        font-size: 14px;
    }
    
    .pdf-meta, .pdf-status, .pdf-note {
        font-size: 12px;
    }
}
</style>
""", unsafe_allow_html=True)