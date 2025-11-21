import os
from fastapi import HTTPException, UploadFile
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, AIMessageChunk, ToolMessage
from assets.enum import MessageType, InteractionType
from config.prompt import SYSTEM_MESSAGE
from langchain_openai import ChatOpenAI
from knowledge_base.chroma import ChromaDBManager
from langgraph.prebuilt import create_react_agent
from database.repositories.chat_repository import ChatRepository
from service.chatbot.tools import retrieve_content_by_similarity
from datetime import datetime
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

class ChatbotService:
    """Service class for managing chatbot interactions and conversation flow."""
    
    def __init__(self, db: Session):
        """Initialize the chatbot service with LLM, tools, and database connection.
        
        Args:
            db: SQLAlchemy database session for chat persistence
        """
        llm =  ChatOpenAI(model="gpt-4o",temperature=0, max_tokens=None, timeout=None, max_retries=2)
        tools = [retrieve_content_by_similarity]
        self.vector_store = ChromaDBManager()
        self.graph = create_react_agent(llm, tools)
        self.chat_repository = ChatRepository(db)

    async def stream(self, prompt:str, chat_id:str, file_input: UploadFile = None):
        """Stream AI responses for a user prompt with real-time message generation.
        
        Args:
            prompt: User's input message
            chat_id: Unique identifier for the chat session
            file_input: Optional file upload from user
            
        Returns:
            Tuple of (chunk generator, custom attributes dict)
        """
        try:
            custom_attributes = {}
            prompt, chat_id = await self._prepare_prompt_and_chat_id(file_input, chat_id, prompt)
            
            system_message_content = SYSTEM_MESSAGE.format(datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), documents = self.get_document_type_guide())
            system_message = SystemMessage(content=system_message_content)
            user_input = HumanMessage(content=prompt)

            logger.info(f"HumanMessage in chat_id: {chat_id} - {prompt}")

            input = {"messages": [system_message] + self._get_chat_for_llm(chat_id) +[user_input]}

            user_message_id = self.chat_repository.add_message(chat_id, MessageType.USER, prompt)

            config = {"configurable": {"chat_id": chat_id}}

            placeholder_message_id = self.chat_repository.add_message(
                chat_id=chat_id,
                sender=MessageType.ASSISTANT,
                content="",  # Empty for now
            )

            custom_attributes["chat_id"] = str(chat_id)
            custom_attributes["bot_message_id"]= str(placeholder_message_id)
            custom_attributes["user_message_id"]= str(user_message_id)
            return self._chunk_generator(input, config, chat_id, placeholder_message_id), custom_attributes
        except Exception as e:
            logger.error(f"Exception while processing stream for chat_id {chat_id}")
            raise Exception(e)

    async def _chunk_generator(self, input: dict, config:dict, chat_id:str, message_id:str):
        """Generate streaming chunks from the AI agent and save the final response.
        
        Args:
            input: Input dictionary containing messages for the LLM
            config: Configuration dict with chat_id
            chat_id: Unique identifier for the chat session
            message_id: ID of the placeholder message to update
            
        Yields:
            String chunks of AI response content
        """
        gathered_response = None
        async for message_chunk, metadata  in self.graph.astream(input=input, config=config, stream_mode="messages") :
            if isinstance(message_chunk,AIMessageChunk) and message_chunk.content and metadata.get("type","")!="retriever":
                if gathered_response is None:
                    gathered_response = message_chunk
                else:
                    gathered_response = gathered_response + message_chunk
                yield message_chunk.content  
        
            if isinstance(message_chunk,ToolMessage):
                logger.info((f"ToolMessage ({message_chunk.name}) received: {message_chunk.content}").encode("utf-8"))
                self.chat_repository.add_message(chat_id, MessageType.TOOL, str(message_chunk.content), InteractionType.TEXT)

            
        self.chat_repository.update_message_by_id(
            chat_id=chat_id, 
            message_id=message_id,
            new_content=gathered_response.content,
        )

        logger.info((f"AIMessage received: {gathered_response.content}").encode("utf-8"))

    def _get_chat_for_llm(self, chat_id: str):
        """Retrieve and format chat history as LangChain message objects.
        
        Args:
            chat_id: Unique identifier for the chat session
            
        Returns:
            List of LangChain message objects (AIMessage, HumanMessage)
        """
        message_history = []
        db_messages = self.chat_repository.get_chat_messages(int(chat_id))
        for item in db_messages:
            if item.sender==MessageType.ASSISTANT.value:
                message_history.append(AIMessage(content=item.content))
            if item.sender==MessageType.USER.value:
                message_history.append(HumanMessage(content=item.content))
        
        return message_history
    
    def get_message_by_id(self, chat_id: str, message_id):
        """Retrieve a specific message by its ID from a chat.
        
        Args:
            chat_id: Unique identifier for the chat session
            message_id: ID of the message to retrieve
            
        Returns:
            Message object if found
            
        Raises:
            HTTPException: If message is not found
        """
        message = self.chat_repository.get_message_by_id(self.user["id"], chat_id, message_id)
        if message is None:
            raise HTTPException(status_code=404, detail=f'Message with id {message_id} in chat {chat_id} not found.')
        
        return message

    def get_chat_messages(self, chat_id: str):
        """Retrieve all messages from a specific chat.
        
        Args:
            chat_id: Unique identifier for the chat session
            
        Returns:
            List of message objects from the chat
        """
        self.check_chat_id(chat_id)
        return self.chat_repository.get_chat_messages(int(chat_id), user_id=self.user["id"])

    def get_chat_history(self, limit=5):
        """Retrieve the most recent chat sessions.
        
        Args:
            limit: Maximum number of chat sessions to return (default: 5)
            
        Returns:
            List of recent chat objects
        """
        return self.chat_repository.get_chat_history(limit=limit)

    def check_chat_id(self, chat_id: str):
        """Verify that a chat ID exists in the database.
        
        Args:
            chat_id: Unique identifier for the chat session
            
        Raises:
            HTTPException: If chat ID does not exist
        """
        if not self.chat_repository.chat_exists(chat_id):
            raise HTTPException(status_code=404, detail=f'Chat ID {chat_id} does not exist.')
    
    def create_chat(self, title: str):
        """Create a new chat session with a given title.
        
        Args:
            title: Title for the new chat session
            
        Returns:
            The newly created chat ID
        """
        chat_id = self.chat_repository.create_chat(title=title)
        return chat_id
    
    async def _prepare_prompt_and_chat_id(self,chat_id: str, prompt:str=None) -> tuple[str, str]:
        """Prepare the prompt and ensure a valid chat_id exists.
        
        Args:
            chat_id: Existing chat ID or None to create a new chat
            prompt: User's input message (used as title if creating new chat)
            
        Returns:
            Tuple of (prompt, chat_id)
        """
        if chat_id is not None:
            self.check_chat_id(chat_id)
        else:
            chat_id = self.create_chat(title=prompt)
        return prompt, chat_id


