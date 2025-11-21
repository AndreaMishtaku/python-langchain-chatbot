import os
from typing import List
import chromadb
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from chromadb.utils.embedding_functions.chroma_langchain_embedding_function import create_langchain_embedding
import logging
logger = logging.getLogger(__name__)

load_dotenv()

DB_FOLDER = "data"  
os.makedirs(DB_FOLDER, exist_ok=True)  

DB_NAME = os.path.join(DB_FOLDER, "chatbot.db") 
FULL_DATABASE_URL = f"sqlite:///{DB_NAME}"

connect_args = {"check_same_thread": False}
engine = create_engine(FULL_DATABASE_URL, connect_args=connect_args, pool_size=10, max_overflow=20)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def set_sqlite_pragma():
    with engine.connect() as connection:
        connection.execute(text("PRAGMA journal_mode=WAL;"))
        connection.execute(text("PRAGMA busy_timeout=3000;"))
        connection.execute(text("PRAGMA synchronous=NORMAL;"))
        connection.execute(text("PRAGMA temp_store=MEMORY;"))
    
    logger.info("Pragma commands executed successfully!")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_chroma_collections(collections: List[dict]):
    openai_ef = create_langchain_embedding(OpenAIEmbeddings(
            model= int(os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")),
            chunk_size=int(os.getenv("EMBEDDING_CHUNK_SIZE", "4000"))
        ))
    
    t_path = f"collections/{DB_FOLDER}"
    client = chromadb.PersistentClient(path=t_path)

    logger.info(f"Connected successfully with chromadb:///{t_path}")
    for col in collections:
        client.get_or_create_collection(name=col['name'], embedding_function = openai_ef)
        

def init_tables():
    Base.metadata.create_all(bind=engine)
    logger.info("DB tables initialized successfully")

def init_db():
    set_sqlite_pragma()
    init_tables()

