import streamlit as st
from vector import upload_pdf, create_faiss_db
from Rag_pipline import answer_query, retrieve_summary, llm_model
import os
import time
import base64
from datetime import datetime

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
    
    // Use MutationObserver to catch Streamlit's dynamic updates
    var observer = new MutationObserver(function(mutations) {
        makeResponsive();
    });
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // Also run periodically to catch any missed updates
    setInterval(makeResponsive, 1000);
</script>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800&display=swap');
    
    /* Prevent horizontal scroll on mobile */
    html, body {
        overflow-x: hidden !important;
        max-width: 100vw !important;
        width: 100% !important;
    }
    
    /* Force responsive behavior */
    .stApp {
        max-width: 100% !important;
    }
    
    /* Smooth scrolling */
    * {
        -webkit-tap-highlight-color: rgba(0,0,0,0.1);
        box-sizing: border-box;
    }

    /* Hide Streamlit defaults */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}

    /* Remove top padding and force full width */
    .block-container {
        padding-top: 1rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        max-width: 100% !important;
        width: 100% !important;
    }
    
    /* Main content area - force responsive */
    [data-testid="stAppViewContainer"] {
        max-width: 100% !important;
        width: 100% !important;
    }
    
    /* Responsive container */
    @media screen and (max-width: 768px) {
        .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            padding-top: 0.5rem !important;
        }
    }

    /* Main app - soft warm gradient */
    .stApp {
        background: linear-gradient(135deg, #fef9f3 0%, #fce7f3 30%, #e0f2fe 70%, #f0fdf4 100%);
        font-family: 'Nunito', sans-serif;
        min-height: 100vh;
    }

    /* Sidebar - soft cream */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #fefce8 0%, #fef3c7 100%);
        border-right: 2px solid #fcd34d;
    }
    
    /* Mobile sidebar adjustments */
    @media screen and (max-width: 768px) {
        section[data-testid="stSidebar"] {
            min-width: 200px !important;
            max-width: 80vw !important;
        }
        
        /* Make sidebar toggle more visible on mobile */
        button[data-testid="baseButton-header"] {
            z-index: 999 !important;
        }
    }

    /* Compact Hero */
    .hero-compact {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1.2rem 2rem;
        background: linear-gradient(135deg, #f97316 0%, #ec4899 50%, #8b5cf6 100%);
        border-radius: 20px;
        margin-bottom: 1.5rem;
        box-shadow: 0 10px 40px rgba(249, 115, 22, 0.25);
    }

    .hero-left {
        display: flex;
        align-items: center;
        gap: 1rem;
    }

    .hero-icon {
        font-size: 2.5rem;
    }

    .hero-title {
        font-size: 1.8rem;
        font-weight: 800;
        color: #ffffff;
        margin: 0;
    }

    .hero-subtitle {
        font-size: 0.95rem;
        color: rgba(255, 255, 255, 0.9);
        margin: 0;
    }

    .hero-features {
        display: flex;
        gap: 1.5rem;
    }

    .hero-feature {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        color: rgba(255, 255, 255, 0.95);
        font-size: 0.9rem;
        font-weight: 600;
    }

    /* Main Cards */
    .upload-card {
        background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
        border-radius: 24px;
        padding: 1.5rem;
        border: 2px solid #fdba74;
        box-shadow: 0 10px 40px rgba(251, 146, 60, 0.15);
    }

    .preview-card {
        background: linear-gradient(135deg, #ecfeff 0%, #cffafe 100%);
        border-radius: 24px;
        padding: 1.5rem;
        border: 2px solid #67e8f9;
        box-shadow: 0 10px 40px rgba(34, 211, 238, 0.15);
    }

    .summary-section {
        background: linear-gradient(135deg, #fdf4ff 0%, #fae8ff 100%);
        border-radius: 24px;
        padding: 1.5rem;
        border: 2px solid #e879f9;
        box-shadow: 0 10px 40px rgba(217, 70, 239, 0.15);
        margin-top: 1.5rem;
    }

    /* Section titles */
    .section-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .section-icon {
        font-size: 1.3rem;
    }

    /* Compact illustration */
    .illustration-small {
        display: flex;
        justify-content: center;
        margin-bottom: 1rem;
    }

    .illustration-small svg {
        max-width: 200px;
        height: auto;
    }

    /* File upload styling - complete override */
    .stFileUploader {
        background: transparent !important;
    }

    .stFileUploader > div {
        background: transparent !important;
        padding: 0 !important;
    }

    .stFileUploader label {
        color: #92400e !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
    }

    .stFileUploader section {
        background: linear-gradient(135deg, #fef3c7, #fde68a) !important;
        border: 3px dashed #f59e0b !important;
        border-radius: 16px !important;
        padding: 1.5rem !important;
    }

    .stFileUploader section:hover {
        border-color: #d97706 !important;
        background: linear-gradient(135deg, #fde68a, #fcd34d) !important;
    }

    .stFileUploader section > div {
        background: transparent !important;
        color: #92400e !important;
    }

    .stFileUploader section span {
        color: #92400e !important;
    }

    .stFileUploader section svg {
        stroke: #d97706 !important;
    }

    .stFileUploader section button {
        background: linear-gradient(135deg, #f97316, #ea580c) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.2rem !important;
    }

    .stFileUploader section small {
        color: #b45309 !important;
    }

    /* Override dark inner box */
    [data-testid="stFileUploader"] > section > div {
        background: transparent !important;
    }

    [data-testid="stFileUploaderDropzone"] {
        background: linear-gradient(135deg, #fef3c7, #fde68a) !important;
        border: 3px dashed #f59e0b !important;
        border-radius: 16px !important;
    }

    [data-testid="stFileUploaderDropzone"]:hover {
        border-color: #d97706 !important;
        background: linear-gradient(135deg, #fde68a, #fcd34d) !important;
    }

    [data-testid="stFileUploaderDropzone"] div {
        background: transparent !important;
    }

    [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stFileUploaderDropzone"] p {
        color: #92400e !important;
    }

    [data-testid="stFileUploaderDropzone"] button {
        background: linear-gradient(135deg, #f97316, #ea580c) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
    }

    /* Hide the inner dark section completely and restyle */
    .uploadedFile {
        background: linear-gradient(135deg, #d1fae5, #a7f3d0) !important;
        border: 2px solid #34d399 !important;
        border-radius: 10px !important;
    }

    /* File info */
    .file-info {
        background: linear-gradient(135deg, #d1fae5, #a7f3d0);
        border: 2px solid #34d399;
        border-radius: 14px;
        padding: 0.8rem 1.2rem;
        display: flex;
        align-items: center;
        gap: 0.8rem;
        margin: 0.8rem 0;
    }

    .file-icon-box {
        width: 42px;
        height: 42px;
        background: linear-gradient(135deg, #10b981, #059669);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
    }

    .file-details h4 {
        margin: 0;
        font-size: 0.95rem;
        color: #065f46;
        font-weight: 700;
    }

    .file-details p {
        margin: 0;
        font-size: 0.8rem;
        color: #047857;
    }

    /* Buttons - Touch-friendly */
    .stButton > button {
        background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.75rem 1.5rem;
        font-size: 1rem;
        font-weight: 700;
        font-family: 'Nunito', sans-serif;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(249, 115, 22, 0.4);
        width: 100%;
        min-height: 44px; /* Touch target size */
        cursor: pointer;
        -webkit-tap-highlight-color: transparent;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(249, 115, 22, 0.5);
    }
    
    .stButton > button:active {
        transform: translateY(0);
    }

    .stDownloadButton > button {
        background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 700;
        box-shadow: 0 4px 15px rgba(139, 92, 246, 0.4);
    }

    /* Summary cards */
    .summary-card {
        background: linear-gradient(135deg, #fef9c3, #fef08a);
        border-radius: 16px;
        padding: 1.2rem;
        margin-bottom: 0.8rem;
        border: 2px solid #facc15;
        box-shadow: 0 6px 20px rgba(250, 204, 21, 0.2);
        transition: all 0.3s ease;
    }

    .summary-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 30px rgba(250, 204, 21, 0.3);
    }

    .summary-header {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding-bottom: 0.8rem;
        margin-bottom: 0.8rem;
        border-bottom: 2px dashed #fbbf24;
    }

    .summary-file-icon {
        width: 38px;
        height: 38px;
        background: linear-gradient(135deg, #f97316, #ea580c);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.1rem;
    }

    .summary-file-info h4 {
        margin: 0;
        font-size: 0.9rem;
        color: #78350f;
        font-weight: 700;
    }

    .summary-file-info span {
        font-size: 0.75rem;
        color: #a16207;
    }

    .summary-content {
        color: #713f12;
        line-height: 1.8;
        font-size: 0.9rem;
    }

    .summary-badge {
        margin-left: auto;
        background: linear-gradient(135deg, #ec4899, #db2777);
        color: white;
        padding: 0.3rem 0.7rem;
        border-radius: 16px;
        font-size: 0.7rem;
        font-weight: 700;
    }

    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 2rem;
        background: linear-gradient(135deg, #fefce8, #fef9c3);
        border-radius: 16px;
        border: 2px dashed #fbbf24;
    }

    .empty-icon {
        font-size: 3rem;
        margin-bottom: 0.8rem;
    }

    .empty-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #78350f;
        margin-bottom: 0.3rem;
    }

    .empty-subtitle {
        color: #a16207;
        font-size: 0.9rem;
    }

    /* Stats in sidebar */
    .stat-box {
        background: linear-gradient(135deg, #fef3c7, #fde68a);
        border-radius: 14px;
        padding: 1rem;
        text-align: center;
        border: 2px solid #fbbf24;
    }

    .stat-number {
        font-size: 1.8rem;
        font-weight: 800;
        color: #d97706;
    }

    .stat-label {
        font-size: 0.8rem;
        color: #92400e;
        font-weight: 600;
    }

    /* PDF Preview */
    .pdf-container {
        background: linear-gradient(135deg, #e0f2fe, #bae6fd);
        border-radius: 14px;
        padding: 0.8rem;
        border: 2px solid #38bdf8;
    }

    .pdf-header {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        padding-bottom: 0.6rem;
        margin-bottom: 0.6rem;
        border-bottom: 2px dashed #7dd3fc;
        color: #0369a1;
        font-weight: 700;
        font-size: 0.85rem;
    }

    /* Loading */
    .loading-container {
        text-align: center;
        padding: 2rem;
        background: linear-gradient(135deg, #fef3c7, #fde68a);
        border-radius: 16px;
        border: 2px solid #fbbf24;
    }

    .loading-spinner {
        width: 50px;
        height: 50px;
        border: 4px solid #fde68a;
        border-top: 4px solid #f97316;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
        margin: 0 auto 1rem;
    }

    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    .loading-text {
        font-size: 1.1rem;
        font-weight: 700;
        color: #92400e;
    }

    .loading-subtext {
        color: #a16207;
        font-size: 0.85rem;
    }

    /* Error box */
    .error-box {
        background: linear-gradient(135deg, #fee2e2, #fecaca);
        border: 2px solid #f87171;
        border-radius: 14px;
        padding: 0.8rem 1.2rem;
        display: flex;
        align-items: center;
        gap: 0.6rem;
        color: #b91c1c;
        font-weight: 600;
    }

    /* Sidebar content */
    .sidebar-logo {
        text-align: center;
        padding: 1rem 0;
        border-bottom: 2px dashed #fbbf24;
        margin-bottom: 1.2rem;
    }

    .sidebar-logo-icon {
        font-size: 2.5rem;
    }

    .sidebar-logo-text {
        font-size: 1.4rem;
        font-weight: 800;
        color: #d97706;
    }

    .sidebar-logo-tagline {
        font-size: 0.8rem;
        color: #a16207;
    }

    .sidebar-divider {
        height: 2px;
        background: linear-gradient(90deg, transparent, #fbbf24, transparent);
        margin: 1.2rem 0;
    }

    /* How it works */
    .steps-container {
        background: linear-gradient(135deg, #fff7ed, #ffedd5);
        border-radius: 14px;
        padding: 1.2rem;
        border: 2px solid #fdba74;
    }

    .steps-title {
        font-weight: 700;
        color: #c2410c;
        margin-bottom: 0.8rem;
        font-size: 0.95rem;
    }

    .step-item {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        margin-bottom: 0.6rem;
    }

    .step-item:last-child {
        margin-bottom: 0;
    }

    .step-number {
        width: 24px;
        height: 24px;
        background: linear-gradient(135deg, #f97316, #ea580c);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 0.75rem;
        font-weight: 700;
        flex-shrink: 0;
    }

    .step-text {
        color: #9a3412;
        font-size: 0.85rem;
        font-weight: 500;
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
    
    /* ===== MOBILE-FIRST RESPONSIVE DESIGN ===== */
    @media screen and (max-width: 768px) {
        /* CRITICAL: Force full width, no horizontal scroll */
        * {
            max-width: 100vw !important;
        }
        
        html, body, .stApp, .stApp > div,
        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > div,
        main[data-testid="stAppViewContainer"],
        .block-container {
            max-width: 100% !important;
            width: 100% !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            overflow-x: hidden !important;
        }
        
        /* Stack ALL columns on mobile - NO EXCEPTIONS */
        [data-testid="column-container"] {
            flex-direction: column !important;
            flex-wrap: nowrap !important;
            width: 100% !important;
            gap: 1rem !important;
        }
        
        [data-testid="column"],
        div[data-testid="column-container"] > div,
        div[data-testid="column-container"] > [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
            max-width: 100% !important;
            display: block !important;
            margin-bottom: 1rem !important;
        }
        
        /* Sidebar - Auto-collapse on mobile, make toggle button bigger */
        section[data-testid="stSidebar"] {
            min-width: 250px !important;
            max-width: 85vw !important;
        }
        
        /* Make sidebar toggle button more visible on mobile */
        button[kind="header"] {
            z-index: 9999 !important;
            background: #f97316 !important;
            color: white !important;
            padding: 0.5rem !important;
            border-radius: 8px !important;
            min-width: 44px !important;
            min-height: 44px !important;
        }
        
        /* Simplified Hero for mobile */
        .hero-compact {
            flex-direction: column !important;
            text-align: center !important;
            padding: 1rem !important;
            gap: 0.8rem !important;
            margin-bottom: 1rem !important;
            border-radius: 16px !important;
        }
        
        .hero-left {
            flex-direction: column !important;
            gap: 0.5rem !important;
            width: 100% !important;
        }
        
        .hero-icon { 
            font-size: 2.5rem !important;
        }
        
        .hero-title { 
            font-size: 1.5rem !important;
            line-height: 1.3 !important;
        }
        
        .hero-subtitle { 
            font-size: 0.9rem !important;
            line-height: 1.4 !important;
        }
        
        .hero-features {
            flex-wrap: wrap !important;
            justify-content: center !important;
            gap: 0.8rem !important;
            width: 100% !important;
        }
        
        .hero-feature { 
            font-size: 0.85rem !important;
            padding: 0.4rem 0.8rem !important;
            background: rgba(255, 255, 255, 0.2) !important;
            border-radius: 12px !important;
        }
        
        /* Cards - Simplified for mobile */
        .upload-card, .preview-card, .summary-section {
            padding: 1rem !important;
            border-radius: 16px !important;
            margin-bottom: 1rem !important;
            width: 100% !important;
        }
        
        .section-title { 
            font-size: 1.1rem !important;
            flex-wrap: wrap !important;
            margin-bottom: 0.8rem !important;
        }
        
        .section-icon {
            font-size: 1.2rem !important;
        }
        
        /* Hide illustration on very small screens */
        .illustration-small {
            display: none !important;
        }
        
        /* Summary cards - Mobile optimized */
        .summary-card { 
            padding: 1rem !important;
            margin-bottom: 1rem !important;
            border-radius: 12px !important;
        }
        
        .summary-header { 
            flex-wrap: wrap !important;
            gap: 0.5rem !important;
        }
        
        .summary-badge {
            margin-left: 0 !important;
            margin-top: 0.5rem !important;
            width: 100% !important;
            text-align: center !important;
        }
        
        .summary-content { 
            font-size: 0.9rem !important; 
            line-height: 1.7 !important;
            word-wrap: break-word !important;
            overflow-wrap: break-word !important;
        }
        
        /* File info - Mobile friendly */
        .file-info { 
            padding: 1rem !important;
            flex-wrap: wrap !important;
            gap: 0.8rem !important;
        }
        
        .file-icon-box {
            width: 48px !important;
            height: 48px !important;
            font-size: 1.3rem !important;
        }
        
        .file-details h4 {
            font-size: 1rem !important;
            word-break: break-word !important;
            line-height: 1.4 !important;
        }
        
        .file-details p {
            font-size: 0.85rem !important;
        }
        
        /* Empty states */
        .empty-state { 
            padding: 2rem 1rem !important;
        }
        
        .empty-icon { 
            font-size: 3rem !important;
        }
        
        .empty-title {
            font-size: 1.1rem !important;
        }
        
        .empty-subtitle {
            font-size: 0.9rem !important;
        }
        
        /* PDF Preview - Simplified on mobile */
        .pdf-container { 
            padding: 0.8rem !important;
        }
        
        .pdf-container iframe { 
            height: 300px !important;
            width: 100% !important;
            border-radius: 8px !important;
        }
        
        .pdf-header {
            font-size: 0.85rem !important;
            word-break: break-word !important;
            line-height: 1.4 !important;
        }
        
        /* Buttons - Extra large for mobile touch */
        .stButton > button {
            min-height: 52px !important;
            font-size: 1rem !important;
            padding: 0.9rem 1.5rem !important;
            font-weight: 700 !important;
            border-radius: 12px !important;
        }
        
        .stDownloadButton > button {
            min-height: 48px !important;
            font-size: 0.95rem !important;
            padding: 0.8rem 1.2rem !important;
        }
        
        /* File uploader - Mobile optimized */
        .stFileUploader section {
            padding: 1.5rem 1rem !important;
            min-height: 120px !important;
        }
        
        .stFileUploader label {
            font-size: 1rem !important;
        }
        
        /* Stats in sidebar - if visible */
        .stat-box {
            padding: 1rem !important;
        }
        
        .stat-number {
            font-size: 1.8rem !important;
        }
        
        .stat-label {
            font-size: 0.85rem !important;
        }
        
        /* Steps container */
        .steps-container {
            padding: 1rem !important;
        }
        
        .step-text {
            font-size: 0.9rem !important;
        }
    }

    @media screen and (max-width: 480px) {
        /* Extra small phones - Even more simplified */
        .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
            padding-top: 0.5rem !important;
        }
        
        .hero-compact { 
            padding: 0.9rem !important;
            border-radius: 12px !important;
        }
        
        .hero-icon { 
            font-size: 2rem !important;
        }
        
        .hero-title { 
            font-size: 1.3rem !important;
            line-height: 1.2 !important;
        }
        
        .hero-subtitle { 
            font-size: 0.85rem !important;
            line-height: 1.3 !important;
        }
        
        .hero-feature { 
            font-size: 0.8rem !important;
            padding: 0.35rem 0.7rem !important;
        }
        
        .upload-card, .preview-card, .summary-section {
            padding: 0.9rem !important;
            border-radius: 12px !important;
        }
        
        .section-title { 
            font-size: 1rem !important;
            margin-bottom: 0.8rem !important;
        }
        
        .section-icon {
            font-size: 1.1rem !important;
        }
        
        .summary-card { 
            padding: 0.9rem !important;
            border-radius: 12px !important;
        }
        
        .summary-content { 
            font-size: 0.85rem !important;
            line-height: 1.6 !important;
        }
        
        .summary-file-info h4 {
            font-size: 0.9rem !important;
        }
        
        .summary-file-info span {
            font-size: 0.75rem !important;
        }
        
        .file-info {
            padding: 0.8rem !important;
        }
        
        .file-icon-box {
            width: 44px !important;
            height: 44px !important;
            font-size: 1.2rem !important;
        }
        
        .file-details h4 {
            font-size: 0.95rem !important;
        }
        
        .empty-state {
            padding: 1.5rem 0.8rem !important;
        }
        
        .empty-icon {
            font-size: 2.5rem !important;
        }
        
        .empty-title {
            font-size: 1rem !important;
        }
        
        .empty-subtitle {
            font-size: 0.85rem !important;
        }
        
        .pdf-container iframe {
            height: 250px !important;
        }
        
        .stButton > button { 
            font-size: 0.95rem !important; 
            padding: 0.8rem 1.2rem !important;
            min-height: 48px !important;
        }
        
        .stat-box {
            padding: 0.8rem !important;
        }
        
        .stat-number {
            font-size: 1.6rem !important;
        }
        
        .stat-label {
            font-size: 0.8rem !important;
        }
        
        .sidebar-logo-text {
            font-size: 1.1rem !important;
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
            <span class="section-icon">👁️</span> Preview
        </div>
    ''', unsafe_allow_html=True)

    if uploaded_file:
        pdf_path = f"pdfs/{uploaded_file.name}"
        os.makedirs("pdfs", exist_ok=True)
        with open(pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        with open(pdf_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode("utf-8")

        st.markdown(f'''
        <div class="pdf-container">
            <div class="pdf-header">📄 {uploaded_file.name}</div>
            <iframe src="data:application/pdf;base64,{base64_pdf}"
                    width="100%" height="280px"
                    style="border: none; border-radius: 8px;">
            </iframe>
        </div>
        ''', unsafe_allow_html=True)
    else:
        st.markdown('''
        <div class="empty-state">
            <div class="empty-icon">📄</div>
            <div class="empty-title">No document yet</div>
            <div class="empty-subtitle">Upload a PDF to preview</div>
        </div>
        ''', unsafe_allow_html=True)

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
            reader = PdfReader(pdf_path)
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

# Display summaries
if st.session_state.chat_history:
    for message in reversed(st.session_state.chat_history):
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
else:
    st.markdown('''
    <div class="empty-state">
        <div class="empty-icon">📋</div>
        <div class="empty-title">No summaries yet</div>
        <div class="empty-subtitle">Upload a PDF and click "Generate Summary"</div>
    </div>
    ''', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
