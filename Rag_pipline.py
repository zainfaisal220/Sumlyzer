import os
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from vector import create_faiss_db, FAISS_DB_PATH
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
# Explicitly load from current directory to ensure it's found
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

# Initialize Groq LLM - check both env vars and Streamlit secrets
groq_api_key = os.environ.get("GROQ_API_KEY")

# Try Streamlit secrets if env var not found (for Streamlit Cloud deployment)
if not groq_api_key:
    try:
        import streamlit as st
        groq_api_key = st.secrets.get("GROQ_API_KEY")
    except:
        pass

if not groq_api_key:
    raise ValueError("GROQ_API_KEY environment variable is not set. Please set it before running the application.")

llm_model = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=groq_api_key
)

def retrieve_summary(query, faiss_db):
    """
    Retrieve relevant documents from FAISS vector store based on query.
    query: User query string.
    faiss_db: FAISS vector store instance.
    """
    try:
        return faiss_db.similarity_search(query, k=4)  # Retrieve top 4 documents
    except Exception as e:
        raise Exception(f"Error retrieving documents: {e}")

def get_context(documents):
    """
    Combine document content into a single context string.
    documents: List of retrieved documents.
    """
    try:
        context = "\n\n".join([doc.page_content for doc in documents])
        return context
    except Exception as e:
        raise Exception(f"Error creating context: {e}")

custom_prompt_template = """
Summarize the following document clearly and concisely. Your goal is to provide a complete overview of the content, highlighting the most important points, arguments, or sections.

Instructions:
- Do not act as an assistant or expert.
- Focus on the core content of the entire document.
- Present the main ideas in bullet points (5 to 10 points).
- Ensure the summary captures key sections and logical flow.
Question: {question} 
Context: {context} 
Answer:
"""

def answer_query(documents, model, query):
    """
    Generate a response using the LLM based on retrieved documents and query.
    documents: List of retrieved documents.
    model: ChatGroq LLM instance.
    query: User query string.
    """
    try:
        context = get_context(documents)
        prompt = ChatPromptTemplate.from_template(custom_prompt_template)
        chain = prompt | model
        response = chain.invoke({"question": query, "context": context})
        return response.content  # Extract text content from AIMessage
    except Exception as e:
        raise Exception(f"Error generating answer: {e}")