import os
import chromadb
from typing import List, Dict, Optional
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from chromadb.utils.embedding_functions.chroma_langchain_embedding_function import create_langchain_embedding
import logging

logger = logging.getLogger(__name__)


class CollectionNotFoundError(Exception):
    """Raised when a ChromaDB collection doesn't exist and needs to be created via ingestion."""
    def __init__(self, collection_name: str, account: str):
        self.collection_name = collection_name
        self.account = account
        super().__init__(f"Collection '{collection_name}' not found for account '{account}'")


class ChromaDBManager:
    """Manager class for ChromaDB vector database operations including ingestion and retrieval."""
    
    def __init__(self, db_path: str = "data"):
        """Initialize ChromaDB manager with persistent storage and embedding configuration.
        
        Args:
            db_path: Base directory path for storing ChromaDB data (default: "data")
        """
        self.account_db_path = f"{db_path}"
        self.client = chromadb.PersistentClient(path=self.account_db_path)
        
        # Use environment variable for chunk size with fallback
        if chunk_size is None:
            chunk_size = int(os.getenv("EMBEDDING_CHUNK_SIZE", "4000"))
            
        self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size = chunk_size,
                chunk_overlap=500,
                length_function=len,
                is_separator_regex=False,
            )
        self.embedding = OpenAIEmbeddings(
            model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"),
            chunk_size=chunk_size
        )
        
        self.collention_list=[]
    
    def _get_docs(self, chroma_query_results):
        """Transform ChromaDB query results into a structured document list.
        
        Args:
            chroma_query_results: Raw query results from ChromaDB
            
        Returns:
            List of dictionaries containing document content, IDs, and metadata
        """
        all_docs=[]
        for i, documents in enumerate(chroma_query_results["documents"]):
            for j, d in enumerate(documents):
                all_docs.append({"content":d, "id":chroma_query_results["ids"][i][j], "metadata":chroma_query_results["metadatas"][i][j]})
        return all_docs

    def clear_collection(self, collection_name: str):
        """Delete and recreate a collection, removing all its data.
        
        Args:
            collection_name: Name of the collection to clear
            
        Raises:
            Exception: If collection deletion or recreation fails
        """
        try:
            self.client.delete_collection(name=collection_name)
            logger.info(f"Collection {collection_name} dropped successfully for the account {self.account}.")
        except Exception as e:
            logger.error("Failed to drop collection!")
            raise(e)

        self.client.create_collection(name=collection_name, embedding_function=self.embedding)
        logger.info(f"Reinitialized collection {collection_name} for the account {self.account}.")

    def delete_from_collection(self, collection_name: str, file_id: str):
        """Delete all chunks associated with a specific file ID from a collection.
        
        Args:
            collection_name: Name of the collection to delete from
            file_id: Unique identifier of the file whose chunks should be deleted
            
        Returns:
            True if documents were deleted, False if no matching documents found
            
        Raises:
            Exception: If deletion operation fails
        """
        try:
            self._check_collection(collection_name)
            collection = self.client.get_collection(name=collection_name)
            
            # Get all items from the collection
            results = collection.get(where={"id": {"$eq": int(file_id)}})

            if len(results["ids"]) > 0:
                collection.delete(where={"id": int(file_id)})
                logger.info(f"Deleted {len(results['ids'])} chunks from collection {collection_name}.")
                return True
            else:
                logger.info(f"No documents found in collection {collection_name} matching id {file_id}. Nothing was deleted.")
                return False

        except Exception as e:
            logger.error(f"Failed to delete from collection {collection_name}! Error: {str(e)}")
            raise e
            

    def _hierarchical_chunking(self, text: str) -> List[str]:
        """Split text into smaller chunks using recursive character text splitting.
        
        Args:
            text: Input text to be chunked
            
        Returns:
            List of text chunks
        """
        return self.text_splitter.split_text(text)
    
    def _check_collection(self, collection_name: str) -> bool:
        """Verify if a collection exists and create it automatically if it doesn't.
        
        Args:
            collection_name: Name of the collection to check
            
        Returns:
            None (creates collection if it doesn't exist)
        """
        if len(self.collention_list) == 0:
            # ChromaDB v0.6.0+ returns collection names as strings directly
            self.collention_list = self.client.list_collections()
        
        if collection_name in self.collention_list:
            return
        else:
            # Auto-create collection if it doesn't exist
            logger.info(f"Collection '{collection_name}' not found for account '{self.account}'. Creating automatically...")
            self.client.get_or_create_collection(name=collection_name, embedding_function=self.embedding)
            logger.info(f"Collection '{collection_name}' created successfully for account '{self.account}'.")


    def ingest_data(self, collection_name: str, ids: List[str], documents: List[str], metadata: Optional[List[Dict]] = None):
        """Ingest documents into ChromaDB by chunking and storing with embeddings.
        
        Args:
            collection_name: Name of the collection to ingest data into
            ids: List of unique document identifiers
            documents: List of document texts to ingest
            metadata: Optional list of metadata dictionaries for each document
        """
        self._check_collection(collection_name)
        collection = self.client.get_collection(name=collection_name, embedding_function=self.embedding)
        
        chunked_ids = []
        chunked_documents = []
        chunked_metadata = []

        for idx, doc in enumerate(documents):
            chunks = self._hierarchical_chunking(doc) or ["empty"]
            for j, chunk in enumerate(chunks):
                chunked_ids.append(f"{ids[idx]}_{j}") 
                chunked_documents.append(chunk)
                if metadata:
                    chunked_metadata.append(metadata[idx])
                else:
                    chunked_metadata.append({})
        
        collection.add(ids=chunked_ids, documents=chunked_documents, metadatas=[meta for meta in chunked_metadata])

    def retrieve_data(self, collection_name: str, query_texts: List[str], metadata_filter: dict = None, n_results: int = 15) -> Dict:
        """Retrieve similar documents from ChromaDB based on semantic search.
        
        Args:
            collection_name: Name of the collection to search in
            query_texts: List of query strings for similarity search
            metadata_filter: Optional metadata filter to narrow down results
            n_results: Maximum number of results to return (default: 15)
            
        Returns:
            Dictionary containing matched documents with content, IDs, and metadata
            
        Raises:
            Exception: If retrieval operation fails
        """
        try:
            self._check_collection(collection_name)
            collection = self.client.get_collection(name=collection_name, embedding_function=self.embedding)

            query_params = {"query_texts": query_texts, "n_results": n_results}

            if metadata_filter is not None:
                query_params["where"] = metadata_filter
            docs = collection.query(**query_params)
            return self._get_docs(docs)
        except Exception as e:
            logger.error(f"ChromaDB error for account '{self.account}', collection '{collection_name}': {e}")
            raise e