import json
import logging
from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from service import IngestionService
from database.db import init_chroma_collections

logger = logging.getLogger(__name__)

ingestion_router = APIRouter()

@ingestion_router.post("/doc/upload")
async def process_upload(
    file: UploadFile = File(...),
    metadata: str = Form(...),
    id: int = Form(...),
    collection_name: str = Form(...),
):
    try:
        logger.info("🔄 Parsing metadata JSON...")
        try:
            if isinstance(metadata, str):
                metadata_dict = json.loads(metadata)
            else:
                metadata_dict = metadata
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse metadata JSON: {e}")

            raise
        ingestion_service = IngestionService()

        # Start ingestion
        await ingestion_service.ingest_new_document(id, collection_name, file, metadata_dict)

        logger.info("✅ Document ingestion completed successfully")
        logger.info("="*80)

        return JSONResponse(
            content={"result": True, "message": "File uploaded successfully"},
            status_code=200
        )

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parsing error: {e}")
        return JSONResponse(
            content={"result": False, "error": f"Invalid JSON in metadata: {str(e)}"},
            status_code=400
        )
    except Exception as e:
        logger.error(f"❌ Unexpected error in /api/doc/upload: {e}", exc_info=True)
        return JSONResponse(
            content={"result": False, "error": str(e), "type": type(e).__name__},
            status_code=500
        )

@ingestion_router.put("/doc/{id}/upload")
async def process_update(
    id: int,
    file: UploadFile = File(...), 
    metadata: str = Form(...),  
    collection_name: str = Form(...),
):
    metadata = json.loads(metadata)
    metadata_dict = json.loads(metadata) if isinstance(metadata, str) else metadata
    ingestion_service = IngestionService()

    await ingestion_service.update_document(id, collection_name, file, metadata_dict)
    
    return JSONResponse(
        content={"result": True, "message": "File uploaded successfully"},
        status_code=200
    )

@ingestion_router.delete("/doc/{id}")
async def delete_document(
    id: int,
    collection_name: str = Query(...),  
):
    ingestion_service = IngestionService()

    await ingestion_service.delete_document(id, collection_name)
    return JSONResponse(
        content={"result": True, "message": "File deleted successfully"},
        status_code=200
    )
    