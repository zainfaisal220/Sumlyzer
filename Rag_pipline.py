from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from vector import create_faiss_db, FAISS_DB_PATH
from langchain_community.vectorstores import FAISS


llm_model = ChatGroq(
    model="deepseek-r1-distill-llama-70b",  
    api_key="Grok_API_Key"  
    
)

def retrieve_summary(query, faiss_db):
    
    try:
        return faiss_db.similarity_search(query, k=4)  
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
        return response.content  
    except Exception as e:
        raise Exception(f"Error generating answer: {e}")
