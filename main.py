import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from config.logging import setup_logging
from controllers import chatbot_router, ingestion_router
from database.db import init_db
import uvicorn

setup_logging()
init_db()

logger = logging.getLogger(__name__)


app = FastAPI()
PORT = os.getenv("PORT", "8080")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["chat_id", "bot_message_id","user_message_id"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "message": "Internal server error",
            "detail": str(exc),
            "path": request.url.path
        }
    )

app.include_router(chatbot_router, prefix="/api")
app.include_router(ingestion_router, prefix="/api")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(PORT))