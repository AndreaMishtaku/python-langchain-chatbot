import base64
import io
import os
from typing import List
import uuid
from PIL import Image
from pytesseract import image_to_string
import logging

logger = logging.getLogger(__name__)

def image_to_base64(img: Image.Image) -> str:
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def process_pdf_pages(pages: List[dict]):
    full_text= ""
    for page in pages:
        if page["type"] == "text":
            full_text += page["content"] + "\n"
        elif page["type"]=="image":
            ocr_text = image_to_string(page["content"])
            full_text += ocr_text.strip() + "\n"

    return full_text

