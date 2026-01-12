import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Define directories
PDFS_DIRECTORY = "pdfs/"
FAISS_DB_PATH = "vectorstore/db_faiss"

# Ensure directories exist
os.makedirs(PDFS_DIRECTORY, exist_ok=True)
os.makedirs(FAISS_DB_PATH, exist_ok=True)

def upload_pdf(file, filename=None):
    """
    Save an uploaded PDF file to the pdfs/ directory.
    """
    try:
        file_path = os.path.join(PDFS_DIRECTORY, filename or file.name)
        with open(file_path, "wb") as f:
            f.write(file.getbuffer())
        return file_path
    except Exception as e:
        raise Exception(f"Error uploading PDF: {e}")

def load_pdf(file_path):
    """
    Load a PDF file and return its documents.
    """
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        if not documents:
            raise ValueError("No documents loaded from PDF")
        
        # Check if any documents have actual content
        has_content = False
        total_chars = 0
        for doc in documents:
            if doc and hasattr(doc, 'page_content') and doc.page_content:
                content = doc.page_content.strip()
                if len(content) > 0:
                    has_content = True
                    total_chars += len(content)
        
        if not has_content:
            raise ValueError("PDF loaded but contains no extractable text. The PDF might be image-based (scanned) or encrypted.")
        
        if total_chars < 50:
            raise ValueError(f"PDF contains very little text ({total_chars} characters). Cannot create meaningful chunks.")
        
        return documents
    except Exception as e:
        raise Exception(f"Error loading PDF: {e}")

def create_chunks(documents):
    """
    Split documents into chunks.
    """
    try:
        # Filter out empty documents and check for actual text content
        valid_documents = []
        for doc in documents:
            if doc and hasattr(doc, 'page_content'):
                # Check if document has meaningful content (not just whitespace)
                content = doc.page_content.strip() if doc.page_content else ""
                if len(content) > 10:  # At least 10 characters of actual content
                    valid_documents.append(doc)
        
        if not valid_documents:
            raise ValueError("No valid text content found in PDF. The PDF might be image-based (scanned) or empty.")
        
        # Use smaller chunk size and overlap for better handling
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # Reduced from 2000 for better chunking
            chunk_overlap=100,  # Reduced from 200
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]  # Explicit separators
        )
        
        text_chunks = text_splitter.split_documents(valid_documents)
        
        # Filter out empty chunks
        text_chunks = [chunk for chunk in text_chunks if chunk.page_content.strip()]
        
        if not text_chunks:
            raise ValueError("No chunks created from documents after filtering")
        
        return text_chunks
    except Exception as e:
        raise Exception(f"Error creating chunks: {e}")

def create_faiss_db(file_path):
    """
    Load PDF and return text chunks directly (no embeddings needed).
    Returns list of document chunks for direct use with LLM.
    """
    try:
        documents = load_pdf(file_path)
        text_chunks = create_chunks(documents)
        return text_chunks
    except Exception as e:
        raise Exception(f"Error processing PDF: {e}")