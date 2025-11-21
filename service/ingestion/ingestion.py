from email import policy
from email.parser import BytesParser
import io
import json
import os
import tempfile
from bs4 import BeautifulSoup
from fastapi import HTTPException, UploadFile
import fitz
from docx import Document
from knowledge_base.chroma import ChromaDBManager
from PIL import Image
from pytesseract import image_to_string
from service.utils import process_pdf_pages
import logging
logger = logging.getLogger(__name__)

class IngestionService:
    """Service class for ingesting and processing various document types into vector storage."""
    
    def __init__(self):
        """Initialize the ingestion service with a ChromaDB vector store manager."""
        self.vector_store = ChromaDBManager()
            
    async def ingest_new_document(self, id:int, collection_name: str, file: UploadFile, metadata: dict):
        """Ingest a new document by extracting text and storing it in the vector database.
        
        Args:
            id: Unique identifier for the document
            collection_name: Name of the vector store collection
            file: Uploaded file to process
            metadata: Additional metadata to store with the document
        """
        temp_dir = tempfile.gettempdir()
        file_name = file.filename
        file_type = file.content_type 
        file_path = os.path.join(temp_dir, file_name)

        try:
            with open(file_path, 'wb') as f:
                content = await file.read()
                f.write(content)

            text = self.extract_text_from_file(file_path, file_type)
            metadata["id"] = id
            metadata["fileName"] = file_name
            logger.info(f"Text from file {os.path.basename(file_path)} extracted successfully.")
            self.vector_store.ingest_data(collection_name = collection_name, ids=[id],documents=[text], metadata=[metadata])
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    async def update_document(self, id:int, collection_name: str, file: UploadFile, metadata: dict):
        """Update an existing document by deleting the old version and ingesting the new one.
        
        Args:
            id: Unique identifier for the document to update
            collection_name: Name of the vector store collection
            file: New uploaded file to replace the old one
            metadata: Updated metadata to store with the document
        """
        self.vector_store.delete_from_collection(collection_name=collection_name, file_id=str(id))

        # TODO avoid code replication with ingest_new_document
        temp_dir = tempfile.gettempdir()
        file_name = file.filename
        file_type = file.content_type 
        file_path = os.path.join(temp_dir, file_name)

        try:
            with open(file_path, 'wb') as f:
                content = await file.read()
                f.write(content)

            text = self.extract_text_from_file(file_path, file_type) 
            metadata["id"] = id
            metadata["fileName"] = file_name
            logger.info(f"Text from file {os.path.basename(file_path)} extracted successfully.")
            self.extraction_service.save_extraction(id, text, file_name)
            self.vector_store.ingest_data(collection_name = collection_name, ids=[id],documents=[text], metadata=[metadata])
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    async def delete_document(self, id:int, collection_name):
        """Delete a document from the vector store collection.
        
        Args:
            id: Unique identifier for the document to delete
            collection_name: Name of the vector store collection
            
        Returns:
            Dictionary with success message
            
        Raises:
            HTTPException: If document is not found in the collection
        """
        result = self.vector_store.delete_from_collection(collection_name=collection_name, file_id=str((id)))

        if result is False:
            raise HTTPException(
                status_code=404,
                detail=f"Document with id {id} not found in collection {collection_name}."
            )

        return {"message": "Deleted successfully"}

    def _read_pdf(self, pdf_path):
        """Extract text from a PDF file, handling both text-based and image-based pages.
        
        Args:
            pdf_path: File path to the PDF document
            
        Returns:
            Extracted text content from all pages
        """
        pages_content = []
        with fitz.open(pdf_path) as doc:
            for i, page in enumerate(doc):
                if not page.get_images(full=True):
                    text = page.get_text().strip()
                    pages_content.append({"page": i + 1, "type": "text", "content": text})
                else:
                    pix = page.get_pixmap(dpi=300)
                    img_data = pix.tobytes("png")
                    image = Image.open(io.BytesIO(img_data))
                    pages_content.append({"page": i + 1, "type": "image", "content": image})

        return process_pdf_pages(pages_content)

    def _read_image(self, image_path: str) -> str:
        """Extract text from an image file using OCR (Optical Character Recognition).
        
        Args:
            image_path: File path to the image
            
        Returns:
            Extracted text from the image
        """
        try:
            img = Image.open(image_path)
            text = image_to_string(img)
            return text.strip()
        except Exception as e:
            logger.error(f"Failed to read image: {e}")

    def _read_eml(self, file_path: str) -> str:
        """Extract content from an email (.eml) file including subject, sender, recipients, and body.
        
        Handles both plain text and HTML emails, and extracts text from attachments (PDF, images, DOCX).
        
        Args:
            file_path: File path to the email file
            
        Returns:
            Formatted string with email metadata and content
        """
        with open(file_path, 'rb') as f:
            msg = BytesParser(policy=policy.default).parse(f)

        subject = msg['subject'] or ''
        sender = msg['from'] or ''
        recipients = msg['to'] or ''
        body_content = ''
        if msg.is_multipart():
            for part in msg.iter_parts():
                content_type = part.get_content_type()

                if content_type == 'text/plain':
                    body_content = part.get_payload(decode=True).decode(part.get_content_charset(), errors='ignore')
                    break
                elif content_type == 'text/html' and not body_content:
                    html_content = part.get_payload(decode=True).decode(part.get_content_charset(), errors='ignore')
                    body_content = BeautifulSoup(html_content, 'html.parser').get_text()
                elif content_type == 'application/pdf' or content_type.startswith("image/") or content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    filename = part.get_filename()
                    if filename:
                        temp_dir = tempfile.gettempdir()
                        file_path = os.path.join(temp_dir , filename)
                        try:
                            with open(file_path, 'wb') as pdf_file:
                                pdf_file.write(part.get_payload(decode=True))

                            text_content = self.extract_text_from_file(file_path, content_type)
                            body_content += "\n\n[File Content]\n" + text_content
                        except Exception as e:
                            logger.error(f"Failed to read attachement: {e}")
                        finally:
                            if os.path.exists(file_path):
                                os.remove(file_path)
        else:
            body_content = msg.get_body(preferencelist=('plain', 'html')).get_content()

            if msg.get_content_type() == 'text/html':
                html_content = body_content
                body_content = BeautifulSoup(html_content, 'html.parser').get_text()

        return f"Subject: {subject}\nFrom: {sender}\nTo: {recipients}\n\n{body_content}"

    def extract_text_from_file(self, file_path: str, file_type: str) -> str:
        """Extract text content from various file types.
        
        Supports PDF, TXT, images (JPG, PNG), DOCX, and EML files.
        
        Args:
            file_path: Path to the file to extract text from
            file_type: MIME type or file extension of the file
            
        Returns:
            Extracted text content as a string
            
        Raises:
            ValueError: If the file type is not supported
        """
        file_type = file_type.lower()
        file_name = os.path.basename(file_path) 
        if file_type == "application/pdf" or file_name.endswith(".pdf"):
            return self._read_pdf(file_path)

        elif file_type == "text/plain" or file_name.endswith(".txt"):
            with open(file_path, 'r', encoding='utf-8') as txt_file:
                return txt_file.read()

        elif file_type.startswith("image/") or file_name.endswith((".jpg", ".jpeg", ".png")):
            return self._read_image(file_path)

        elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or file_name.endswith(".docx"):
            doc = Document(file_path)
            return "\n".join([para.text for para in doc.paragraphs])
        elif file_type == "message/rfc822" or file_name.endswith(".eml"):
            return self._read_eml(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
