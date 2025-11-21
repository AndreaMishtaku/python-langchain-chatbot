from sqlalchemy import Column, Integer, DateTime, String, func
from sqlalchemy.orm import relationship
from database.db import Base

class Chat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    title = Column(String, nullable=False)