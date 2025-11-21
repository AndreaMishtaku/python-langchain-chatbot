from sqlalchemy import Column, Enum, Integer, LargeBinary, String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from assets.enum import MessageType, InteractionType
from database.db import Base

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"))
    sender = Column(Enum(MessageType), nullable=False) 
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=func.now())


    chat = relationship("Chat", back_populates="messages")