"""
PDF document parser using pypdf.
"""

import io
from typing import Any, BinaryIO

from pypdf import PdfReader

from app.core.errors import DocumentProcessingError
from app.core.logging import get_logger
from app.ingestion.parsers.base import BaseParser, ParsedDocument

logger = get_logger(__name__)


class PdfParser(BaseParser):
    """Parser for PDF documents."""
    
    @property
    def supported_extensions(self) -> list[str]:
        return ['.pdf']
    
    @property
    def mime_types(self) -> list[str]:
        return ['application/pdf']
    
    async def parse_file(self, file_content: bytes, filename: str) -> ParsedDocument:
        """Parse PDF from bytes."""
        try:
            file_stream = io.BytesIO(file_content)
            return await self.parse_stream(file_stream, filename)
        except Exception as e:
            logger.error("PDF parsing failed", filename=filename, error=str(e))
            raise DocumentProcessingError(f"Failed to parse PDF: {str(e)}")
    
    async def parse_stream(self, file_stream: BinaryIO, filename: str) -> ParsedDocument:
        """Parse PDF from stream."""
        try:
            # Read PDF
            reader = PdfReader(file_stream)
            
            if len(reader.pages) == 0:
                raise DocumentProcessingError("PDF has no pages")
            
            # Extract text from all pages
            pages = []
            page_texts = []
            
            for page_num, page in enumerate(reader.pages):
                try:
                    text = page.extract_text()
                    if text.strip():
                        page_texts.append(text.strip())
                        pages.append({
                            "page_number": page_num + 1,
                            "text": text.strip(),
                            "char_count": len(text.strip()),
                        })
                except Exception as e:
                    logger.warning(
                        "Failed to extract text from PDF page",
                        filename=filename,
                        page_num=page_num + 1,
                        error=str(e)
                    )
                    continue
            
            if not page_texts:
                raise DocumentProcessingError("No text content found in PDF")
            
            # Combine all pages
            content = "\n\n".join(page_texts)
            content = self._validate_content(content)
            
            # Build metadata
            metadata = self._extract_basic_metadata(filename, len(content.encode('utf-8')))
            metadata.update({
                "total_pages": len(reader.pages),
                "pages_with_text": len(pages),
                "pages": pages,
                "document_info": self._extract_pdf_info(reader),
            })
            
            logger.info(
                "PDF parsed successfully",
                filename=filename,
                pages=len(reader.pages),
                text_pages=len(pages),
                content_chars=len(content),
            )
            
            return ParsedDocument.create(content, metadata)
            
        except DocumentProcessingError:
            raise
        except Exception as e:
            logger.error("PDF parsing failed", filename=filename, error=str(e))
            raise DocumentProcessingError(f"Failed to parse PDF: {str(e)}")
    
    def _extract_pdf_info(self, reader: PdfReader) -> dict[str, Any]:
        """Extract PDF document information."""
        info = {}
        
        try:
            if reader.metadata:
                metadata = reader.metadata
                
                # Common PDF metadata fields
                fields = {
                    '/Title': 'title',
                    '/Author': 'author',
                    '/Subject': 'subject',
                    '/Creator': 'creator',
                    '/Producer': 'producer',
                    '/CreationDate': 'creation_date',
                    '/ModDate': 'modification_date',
                }
                
                for pdf_key, clean_key in fields.items():
                    if pdf_key in metadata:
                        value = metadata[pdf_key]
                        if value:
                            info[clean_key] = str(value)
            
        except Exception as e:
            logger.warning("Failed to extract PDF metadata", error=str(e))
        
        return info