import logging
from fastapi import APIRouter, File, Form, Query, Request, UploadFile, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from controllers.chatbot_controller.chatbot_payload import ChatRequest
from service import ChatbotService
from fastapi import Depends
from database.db import get_db

logger = logging.getLogger(__name__)


chatbot_router = APIRouter()
SessionDependency =  Depends(get_db)

@chatbot_router.post("/chat")
async def stream_response(
    request: Request,
    file: UploadFile = File(None),
    chat_id: str = Form(None),
    db: Session = SessionDependency
):
    try:
        chatbot_service = ChatbotService(db)
        prompt = None

        try:
            request_data = await request.json()
            logger.info(f"JSON data keys: {list(request_data.keys())}")
            
            chat_request = ChatRequest(**request_data)
            prompt = chat_request.prompt
            chat_id = chat_request.chat_id
            
            logger.info(f"Parsed request - prompt length: {len(prompt) if prompt else 0}, chat_id: {chat_id}")
            
        except Exception as json_error:
            logger.error(f"JSON parsing error: {str(json_error)}")
            raise HTTPException(status_code=400, detail=f"Invalid JSON request: {str(json_error)}")
        
        generator, custom_attributes = await chatbot_service.stream(
            prompt=prompt,
            chat_id=chat_id,
            file_input=file
        )
        

        headers = {"Content-Type": "text/event-stream"}
        headers.update(custom_attributes)
        
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers=headers
        )
        
    except HTTPException as he:
        logger.error(f"HTTPException: {he.status_code} - {he.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@chatbot_router.get("/chat-history")
async def get_chat_history(
    limit: int = Query(5, ge=1, le=100), 
    tag: str = Query("knowledge", description="Filter chats by tag"),
    db: Session = SessionDependency
):
    chatbot_service = ChatbotService(db)
    chat_list = chatbot_service.get_chat_history(limit=limit, tag=tag)

    return JSONResponse(
        content = jsonable_encoder(chat_list),
        status_code=200
    )

@chatbot_router.get("/chat/{chat_id}")
async def get_chat_history(chat_id: int, db: Session = SessionDependency):
    chatbot_service = ChatbotService(db)
    messages_list = chatbot_service.get_chat_messages(chat_id=chat_id)

    return JSONResponse(
        content = jsonable_encoder(messages_list), 
        status_code=200
    )

@chatbot_router.get("/chat/{chat_id}/{msg_id}")
async def get_chat_message_by_id(
    chat_id: int,
    msg_id:int,
    db: Session = SessionDependency
    ):
    chatbot_service = ChatbotService(db)


    message = chatbot_service.get_message_by_id(chat_id, msg_id)
    return JSONResponse(
        content = jsonable_encoder(message), 
        status_code=200
    )


