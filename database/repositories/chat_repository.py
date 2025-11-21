from datetime import datetime, timezone
from typing import List
from assets.enum import MessageType
from database.models import Chat, Message
from sqlalchemy.orm import Session
from schema.message import MessageSchema
from schema.chat import ChatSchema
from sqlalchemy.orm import load_only

class ChatRepository:
    """Repository class for managing chat and message data persistence in the database."""
    
    def __init__(self, db: Session):
        """Initialize the chat repository with a database session.
        
        Args:
            db: SQLAlchemy database session for executing queries
        """
        self.db = db

    def create_chat(self, title: str) -> int:
        """Create a new chat session in the database.
        
        Args:
            title: Title for the new chat session
            
        Returns:
            The ID of the newly created chat
        """
        chat = Chat(title=title)
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(chat)
        return chat.id
    
    def update_chat_title(self, chat_id: int, title: str) -> None:
        """Update the title of an existing chat.
        
        Args:
            chat_id: ID of the chat to update
            title: New title for the chat
            
        Raises:
            ValueError: If chat with the given ID is not found
        """
        chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            raise ValueError(f"Chat with id {chat_id} not found.")

        chat.title = title
        self.db.commit()

    def add_message(self, chat_id: int, sender: MessageType, content: str) -> Message:
        """Add a new message to a chat and update the chat's timestamp.
        
        Args:
            chat_id: ID of the chat to add the message to
            sender: Type of message sender (USER, ASSISTANT, TOOL, etc.)
            content: Content/text of the message
            
        Returns:
            The ID of the newly created message
        """
        message = Message(chat_id=chat_id, sender=sender, content=content)
        self.db.add(message)
        # Automatically access the chat via the relationship
        self.db.flush()
        message.chat.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(message)
        return message.id

    def get_chat_messages(self, chat_id: int) -> List[MessageSchema]:
        """Retrieve all messages from a specific chat, ordered by timestamp.
        
        Args:
            chat_id: ID of the chat to retrieve messages from
            
        Returns:
            List of message schemas containing message data
        """
        query = self.db.query(Message).options(load_only(
            Message.id,
            Message.chat_id,
            Message.sender,
            Message.type,
            Message.content,
            Message.timestamp
        )).join(Chat).filter(Chat.id == chat_id)

        messages = query.order_by(Message.timestamp.asc()).all()

        return [MessageSchema.model_validate(msg) for msg in messages]
    
    def update_message_by_id(
        self,
        chat_id: int,
        message_id: int,
        new_content: str = None,
    ):
        """Update the content of a specific message in a chat.
        
        Args:
            chat_id: ID of the chat containing the message
            message_id: ID of the message to update
            new_content: New content to replace the existing message content
            
        Returns:
            The message ID if updated successfully, None if message not found
        """
        message = self.db.query(Message).filter_by(id=message_id, chat_id=chat_id).first()
        if not message:
            return None

        updated = False

        if new_content is not None and message.content != new_content:
            message.content = new_content
            updated = True

        if updated:
            now = datetime.now(timezone.utc)
            message.timestamp = now
            self.db.commit()
            self.db.refresh(message)

        return message.id
    
    def get_message_by_id(self, chat_id: int, message_id=int):
        """Retrieve a specific message by its ID from a chat.
        
        Args:
            chat_id: ID of the chat containing the message
            message_id: ID of the message to retrieve
            
        Returns:
            MessageSchema if found, None otherwise
        """
        query = (
            self.db.query(Message)
            .join(Chat)
            .filter(Chat.id == chat_id, Message.id == message_id)
        )
        message = query.first()

        if message:
            return MessageSchema.model_validate(message)
        return None


    def chat_exists(self, chat_id: int) -> bool:
        """Check if a chat with the given ID exists in the database.
        
        Args:
            chat_id: ID of the chat to check
            
        Returns:
            True if the chat exists, False otherwise
        """
        return self.db.query(Chat.id).filter(Chat.id == chat_id).scalar() is not None
    
    def get_chat_history(self, limit: int = 10):
        """Retrieve the most recent chat sessions ordered by last update time.
        
        Args:
            limit: Maximum number of chat sessions to return (default: 10)
            
        Returns:
            List of chat schemas containing chat data, ordered by most recent first
        """
        query = self.db.query(Chat)
            
        chat_records = query.order_by(Chat.updated_at.desc()).limit(limit).all()
        return [ChatSchema.model_validate(chat) for chat in chat_records]


