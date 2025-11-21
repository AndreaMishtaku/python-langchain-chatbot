import os
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from knowledge_base.chroma import ChromaDBManager
import logging

logger = logging.getLogger(__name__)

# Through RunableConfig can be passed config values needed depending on the workflow

@tool
def retrieve_content_by_similarity(query: str, collection_name: str, config: RunnableConfig) -> dict:
    """
    Retrieve relevant document chunks based on similarity search.

    This tool returns extracted content segments (chunks) from multiple files that best match the user's query. 
    The returned content should not be treated as a single combined result — instead, carefully evaluate each chunk and 
    select only the parts that precisely address the user's request.

    Args:
        - query: A rich and precise query that reflects the full context of the conversation so far. Do not omit any relevant detail shared by the user at any point. If the query involves an abbreviation or acronym, explicitly request the full form followed by the abbreviation in brackets. The query must be fully self-contained and understandable on its own.
        - collection_name: Collection name from where to retrieve content

    """

    vector_store = ChromaDBManager()
    
    documents = vector_store.retrieve_data(
        collection_name=collection_name,
        query_texts=[query]
    )

    content = [{
        "chunk": doc["content"],
        "fileName": doc["metadata"]["fileName"],
    } for doc in documents]

    # Log successful completion
    logger.info(f"Tool 'retrieve_content_by_similarity' completed - returned {len(content)} chunks from ChromaDB")

    return content
