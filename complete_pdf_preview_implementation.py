# Complete PDF Preview Implementation for front.py
# Replace lines 1336-1384 with this comprehensive solution

# Additional imports to add at the top of front.py (after existing imports)
import gc
import psutil
import threading
from io import BytesIO
from functools import lru_cache
import hashlib

# Custom exception classes for better error handling
class PDFPreviewError(Exception):
    """Base exception for PDF preview errors"""
    pass

class PDFMemoryError(PDFPreviewError):
    """Raised when PDF is too large for memory"""
    pass

class PDFCorruptedError(PDFPreviewError):
    """Raised when PDF file is corrupted"""
    pass

class PDFProcessingError(PDFPreviewError):
    """Raised when PDF processing fails"""
    pass

# Helper functions for PDF validation and processing
def validate_pdf(uploaded_file):
    """
    Comprehensive PDF validation with multiple checks
    """
    if not uploaded_file:
        raise PDFPreviewError("No file provided")
    
    # Check file extension
    if not uploaded_file.name.lower().endswith('.pdf'):
        raise PDFPreviewError("File must be a PDF")
    
    # Check file size (50MB limit)
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > 50:
        raise PDFMemoryError(f"File too large ({file_size_mb:.1f}MB). Maximum size is 50MB")
    
    # Check available memory
    available_memory_gb = psutil.virtual_memory().available / (1024**3)
    if file_size_mb > (available_memory_gb * 0.3 * 1024):  # Don't use more than 30% of available memory
        raise PDFMemoryError(f"Insufficient memory for {file_size_mb:.1f}MB file")
    
    # Check PDF header
    try:
        file_content = uploaded_file.getvalue()
        if not file_content.startswith(b'%PDF'):
            raise PDFCorruptedError("Invalid PDF format - missing PDF header")
        
        # Check for PDF footer
        if b'%%EOF' not in file_content[-1024:]:
            raise PDFCorruptedError("Invalid PDF format - missing EOF marker")
            
    except Exception as e:
        if isinstance(e, PDFCorruptedError):
            raise
        raise PDFPreviewError(f"File validation failed: {str(e)}")
    
    return True

def get_pdf_metadata(uploaded_file):
    """
    Extract PDF metadata safely
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(uploaded_file.getvalue()))
        
        metadata = {
            'page_count': len(reader.pages),
            'title': None,
            'author': None,
            'subject': None,
            'creator': None,
            'producer': None,
            'creation_date': None,
            'modification_date': None
        }
        
        if reader.metadata:
            metadata.update({
                'title': reader.metadata.get('/Title', ''),
                'author': reader.metadata.get('/Author', ''),
                'subject': reader.metadata.get('/Subject', ''),
                'creator': reader.metadata.get('/Creator', ''),
                'producer': reader.metadata.get('/Producer', ''),
                'creation_date': reader.metadata.get('/CreationDate', ''),
                'modification_date': reader.metadata.get('/ModDate', '')
            })
        
        return metadata
        
    except Exception as e:
        raise PDFProcessingError(f"Failed to extract metadata: {str(e)}")

def create_base64_preview(uploaded_file, max_size_mb=3):
    """
    Create base64 preview with memory management
    """
    try:
        file_size_mb = uploaded_file.size / (1024 * 1024)
        
        if file_size_mb > max_size_mb:
            raise PDFMemoryError(f"File too large for preview ({file_size_mb:.1f}MB)")
        
        # Create base64 preview
        file_content = uploaded_file.getvalue()
        base64_pdf = base64.b64encode(file_content).decode("utf-8")
        
        # Validate base64 string
        if len(base64_pdf) > 10 * 1024 * 1024:  # 10MB limit for base64 string
            raise PDFMemoryError("Base64 preview too large")
        
        return base64_pdf
        
    except Exception as e:
        if isinstance(e, PDFMemoryError):
            raise
        raise PDFProcessingError(f"Failed to create preview: {str(e)}")

def create_metadata_preview(metadata, file_size_kb):
    """
    Create metadata preview HTML
    """
    title = metadata.get('title') or 'Untitled Document'
    author = metadata.get('author') or 'Unknown Author'
    page_count = metadata.get('page_count', 0)
    
    # Format dates
    creation_date = metadata.get('creation_date')
    if creation_date and hasattr(creation_date, 'strftime'):
        creation_date = creation_date.strftime('%B %d, %Y')
    else:
        creation_date = 'Unknown'
    
    return f'''
    <div class="pdf-metadata-preview">
        <div class="metadata-header">
            <div class="metadata-icon">📋</div>
            <div class="metadata-title">Document Information</div>
        </div>
        <div class="metadata-content">
            <div class="metadata-row">
                <span class="metadata-label">Title:</span>
                <span class="metadata-value">{title}</span>
            </div>
            <div class="metadata-row">
                <span class="metadata-label">Author:</span>
                <span class="metadata-value">{author}</span>
            </div>
            <div class="metadata-row">
                <span class="metadata-label">Pages:</span>
                <span class="metadata-value">{page_count}</span>
            </div>
            <div class="metadata-row">
                <span class="metadata-label">Size:</span>
                <span class="metadata-value">{round(file_size_kb, 1)} KB</span>
            </div>
            <div class="metadata-row">
                <span class="metadata-label">Created:</span>
                <span class="metadata-value">{creation_date}</span>
            </div>
        </div>
        <div class="metadata-footer">
            <div class="metadata-status">✅ Ready to summarize</div>
        </div>
    </div>
    '''

def create_simple_preview(uploaded_file, file_size_kb):
    """
    Create simple file info preview
    """
    try:
        # Try to get page count
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(uploaded_file.getvalue()))
        page_count = len(reader.pages)
    except:
        page_count = "?"
    
    return f'''
    <div class="pdf-simple-preview">
        <div class="simple-icon">📄</div>
        <div class="simple-content">
            <div class="simple-name">{uploaded_file.name}</div>
            <div class="simple-meta">{round(file_size_kb, 1)} KB • {page_count} pages</div>
            <div class="simple-status">✅ Ready to summarize</div>
        </div>
    </div>
    '''

def create_error_preview(error_message, error_type="general"):
    """
    Create error preview with appropriate styling
    """
    error_icons = {
        "memory": "🧠",
        "corrupted": "🔴",
        "processing": "⚠️",
        "general": "❌"
    }
    
    error_titles = {
        "memory": "Memory Limit Exceeded",
        "corrupted": "Corrupted PDF File",
        "processing": "Processing Error",
        "general": "Preview Error"
    }
    
    icon = error_icons.get(error_type, error_icons["general"])
    title = error_titles.get(error_type, error_titles["general"])
    
    return f'''
    <div class="pdf-error-preview">
        <div class="error-icon">{icon}</div>
        <div class="error-title">{title}</div>
        <div class="error-message">{error_message}</div>
        <div class="error-help">
            <div class="error-help-title">Suggestions:</div>
            <div class="error-help-item">• Try a smaller PDF file</div>
            <div class="error-help-item">• Check if the file is corrupted</div>
            <div class="error-help-item">• Close other applications to free memory</div>
        </div>
    </div>
    '''

# Main preview function to replace lines 1336-1384
def render_pdf_preview(uploaded_file):
    """
    Main PDF preview rendering function with 4-tier fallback system
    """
    if not uploaded_file:
        st.markdown('''
        <div class="empty-state">
            <div class="empty-icon">📄</div>
            <div class="empty-title">No document yet</div>
            <div class="empty-subtitle">Upload a PDF to preview</div>
        </div>
        ''', unsafe_allow_html=True)
        return
    
    file_size_kb = uploaded_file.size / 1024
    file_size_mb = file_size_kb / 1024
    
    # Tier 1: Full PDF preview (under 3MB)
    if file_size_mb < 3:
        try:
            # Validate PDF
            validate_pdf(uploaded_file)
            
            # Create base64 preview
            base64_pdf = create_base64_preview(uploaded_file)
            
            # Render full preview
            st.markdown(f'''
            <div class="pdf-container">
                <div class="pdf-header">📄 {uploaded_file.name} ({round(file_size_kb, 1)} KB)</div>
                <iframe src="data:application/pdf;base64,{base64_pdf}"
                        width="100%" height="350px"
                        style="border: none; border-radius: 8px;">
                </iframe>
            </div>
            ''', unsafe_allow_html=True)
            
            # Clean up memory
            gc.collect()
            
        except PDFMemoryError as e:
            st.markdown(create_error_preview(str(e), "memory"), unsafe_allow_html=True)
        except PDFCorruptedError as e:
            st.markdown(create_error_preview(str(e), "corrupted"), unsafe_allow_html=True)
        except PDFProcessingError as e:
            st.markdown(create_error_preview(str(e), "processing"), unsafe_allow_html=True)
        except Exception as e:
            st.markdown(create_error_preview(f"Unexpected error: {str(e)}", "general"), unsafe_allow_html=True)
    
    # Tier 2: Metadata preview (3MB - 10MB)
    elif file_size_mb < 10:
        try:
            # Validate PDF
            validate_pdf(uploaded_file)
            
            # Extract metadata
            metadata = get_pdf_metadata(uploaded_file)
            
            # Render metadata preview
            st.markdown(create_metadata_preview(metadata, file_size_kb), unsafe_allow_html=True)
            
        except PDFMemoryError as e:
            st.markdown(create_error_preview(str(e), "memory"), unsafe_allow_html=True)
        except PDFCorruptedError as e:
            st.markdown(create_error_preview(str(e), "corrupted"), unsafe_allow_html=True)
        except PDFProcessingError as e:
            st.markdown(create_error_preview(str(e), "processing"), unsafe_allow_html=True)
        except Exception as e:
            st.markdown(create_error_preview(f"Unexpected error: {str(e)}", "general"), unsafe_allow_html=True)
    
    # Tier 3: Simple preview (10MB - 25MB)
    elif file_size_mb < 25:
        try:
            # Basic validation
            if not uploaded_file.name.lower().endswith('.pdf'):
                raise PDFPreviewError("File must be a PDF")
            
            # Render simple preview
            st.markdown(create_simple_preview(uploaded_file, file_size_kb), unsafe_allow_html=True)
            
        except Exception as e:
            st.markdown(create_error_preview(str(e), "general"), unsafe_allow_html=True)
    
    # Tier 4: File info only (25MB+)
    else:
        st.markdown(f'''
        <div class="pdf-large-file-info">
            <div class="large-file-icon">📄</div>
            <div class="large-file-content">
                <div class="large-file-name">{uploaded_file.name}</div>
                <div class="large-file-size">{round(file_size_mb, 1)} MB</div>
                <div class="large-file-status">✅ Ready to summarize</div>
                <div class="large-file-note">Preview disabled for very large files</div>
            </div>
        </div>
        ''', unsafe_allow_html=True)

# Enhanced CSS for better error states and preview styling
# Add this to your existing CSS in front.py
enhanced_pdf_css = """
/* Enhanced PDF Preview Styles */
.pdf-container {
    background: white;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    overflow: hidden;
    margin-bottom: 1rem;
}

.pdf-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 1rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.pdf-metadata-preview {
    background: white;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    overflow: hidden;
    margin-bottom: 1rem;
}

.metadata-header {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    color: white;
    padding: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.metadata-content {
    padding: 1rem;
}

.metadata-row {
    display: flex;
    justify-content: space-between;
    padding: 0.5rem 0;
    border-bottom: 1px solid #f0f0f0;
}

.metadata-row:last-child {
    border-bottom: none;
}

.metadata-label {
    font-weight: 600;
    color: #666;
}

.metadata-value {
    color: #333;
}

.metadata-footer {
    background: #f8f9fa;
    padding: 0.75rem 1rem;
    text-align: center;
}

.metadata-status {
    color: #28a745;
    font-weight: 600;
}

.pdf-simple-preview {
    background: white;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    padding: 1.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
}

.simple-icon {
    font-size: 2rem;
}

.simple-content {
    flex: 1;
}

.simple-name {
    font-weight: 600;
    font-size: 1.1rem;
    margin-bottom: 0.25rem;
}

.simple-meta {
    color: #666;
    margin-bottom: 0.5rem;
}

.simple-status {
    color: #28a745;
    font-weight: 600;
}

.pdf-error-preview {
    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
    color: white;
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
    margin-bottom: 1rem;
}

.error-icon {
    font-size: 2.5rem;
    margin-bottom: 0.5rem;
}

.error-title {
    font-size: 1.2rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
}

.error-message {
    margin-bottom: 1rem;
    opacity: 0.9;
}

.error-help {
    background: rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 1rem;
    text-align: left;
}

.error-help-title {
    font-weight: 600;
    margin-bottom: 0.5rem;
}

.error-help-item {
    margin-bottom: 0.25rem;
    opacity: 0.9;
}

.pdf-large-file-info {
    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    color: white;
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
    margin-bottom: 1rem;
}

.large-file-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
}

.large-file-name {
    font-weight: 600;
    font-size: 1.2rem;
    margin-bottom: 0.5rem;
}

.large-file-size {
    font-size: 1.1rem;
    margin-bottom: 0.5rem;
    opacity: 0.9;
}

.large-file-status {
    font-weight: 600;
    margin-bottom: 0.5rem;
}

.large-file-note {
    opacity: 0.8;
    font-size: 0.9rem;
}

/* Responsive adjustments */
@media (max-width: 768px) {
    .pdf-container iframe {
        height: 250px;
    }
    
    .metadata-row {
        flex-direction: column;
        gap: 0.25rem;
    }
    
    .pdf-simple-preview {
        flex-direction: column;
        text-align: center;
    }
    
    .error-help {
        text-align: center;
    }
}
"""

# Usage instructions:
# 1. Add the additional imports at the top of front.py
# 2. Add the enhanced CSS to your existing CSS section
# 3. Replace lines 1336-1384 with: render_pdf_preview(uploaded_file)
# 4. Make sure to add: import psutil, gc, threading, io, functools, hashlib