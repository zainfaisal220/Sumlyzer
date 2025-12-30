import os
import streamlit as st
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceInferenceAPIEmbeddings
from langchain_community.vectorstores import FAISS

# Define directories
PDFS_DIRECTORY = "pdfs/"
FAISS_DB_PATH = "vectorstore/db_faiss"

# Ensure directories exist
os.makedirs(PDFS_DIRECTORY, exist_ok=True)
os.makedirs(FAISS_DB_PATH, exist_ok=True)

def upload_pdf(file, filename=None):
    """
    Save an uploaded PDF file to the pdfs/ directory.
    file: File object (e.g., from Streamlit).
    filename: Optional filename to save as.
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
    file_path: Path to the PDF file.
    """
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        if not documents:
            raise ValueError("No documents loaded from PDF")
        return documents
    except Exception as e:
        raise Exception(f"Error loading PDF: {e}")

def create_chunks(documents):
    """
    Split documents into chunks.
    documents: List of documents from PyPDFLoader.
    """
    try:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            add_start_index=True
        )
        text_chunks = text_splitter.split_documents(documents)
        if not text_chunks:
            raise ValueError("No chunks created from documents")
        print(f"Created {len(text_chunks)} chunks")
        return text_chunks
    except Exception as e:
        raise Exception(f"Error creating chunks: {e}")

def get_hf_token():
    """Get HuggingFace API token from environment or Streamlit secrets"""
    token = os.environ.get("HF_TOKEN")
    if token:
        return token
    try:
        token = st.secrets["HF_TOKEN"]
        if token:
            return token
    except (KeyError, FileNotFoundError):
        pass
    raise ValueError("HF_TOKEN not found. Get a free token at https://huggingface.co/settings/tokens")

def get_embedding_model():
    """
    Initialize the HuggingFace Inference API embeddings.
    Uses HuggingFace's free API - no local installation needed.
    """
    try:
        embeddings = HuggingFaceInferenceAPIEmbeddings(
            api_key=get_hf_token(),
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        return embeddings
    except Exception as e:
        raise Exception(f"Error initializing embeddings model: {e}")

def create_faiss_db(file_path):
    """
    Create and save a FAISS vector store from a PDF file.
    file_path: Path to the PDF file.
    Returns: FAISS vector store.
    """
    try:
        # Load and process PDF
        documents = load_pdf(file_path)
        text_chunks = create_chunks(documents)
        embeddings = get_embedding_model()
        
        # Create and save FAISS vector store
        faiss_db = FAISS.from_documents(text_chunks, embeddings)
        faiss_db.save_local(FAISS_DB_PATH)
        print(f"FAISS vector store saved to {FAISS_DB_PATH}")
        return faiss_db
    except Exception as e:
        raise Exception(f"Error creating FAISS vector store: {e}")