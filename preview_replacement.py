# PDF PREVIEW SECTION - REPLACEMENT CODE
# This replaces lines 1336-1384 in front.py

# Import the comprehensive PDF preview module
try:
    from pdf_preview_module import process_pdf_preview
except ImportError:
    # Fallback if module import fails
    st.error("PDF preview module not available")
    process_pdf_preview = None

# Main preview rendering logic
if uploaded_file and process_pdf_preview:
    # Use the comprehensive preview system
    process_pdf_preview(uploaded_file)
elif uploaded_file:
    # Fallback to basic preview if module unavailable
    file_size_kb = uploaded_file.size / 1024
    file_size_mb = file_size_kb / 1024
    
    st.markdown(f'''
    <div class="pdf-container">
        <div class="pdf-preview-info">
            <div class="pdf-icon-large">📄</div>
            <div class="pdf-details">
                <div class="pdf-name">{uploaded_file.name}</div>
                <div class="pdf-meta">{round(file_size_mb, 1)} MB</div>
            </div>
            <div class="pdf-status">✓ Ready to summarize</div>
            <div class="pdf-note">Basic preview (enhanced preview unavailable)</div>
        </div>
    </div>
    ''', unsafe_allow_html=True)
else:
    # Empty state
    st.markdown('''
    <div class="empty-state">
        <div class="empty-icon">📄</div>
        <div class="empty-title">No document yet</div>
        <div class="empty-subtitle">Upload a PDF to preview</div>
    </div>
    ''', unsafe_allow_html=True)