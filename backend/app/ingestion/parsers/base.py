"""
Base parser interface for document processing.
"""

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, BinaryIO

from app.core.errors import DocumentProcessingError, UnsupportedFileTypeError


@dataclass
class ParsedDocument:
    """Represents a parsed document with content and metadata."""
    
    content: str
    metadata: dict[str, Any]
    content_hash: str
    
    @classmethod
    def create(cls, content: str, metadata: dict[str, Any] | None = None) -> "ParsedDocument":
        """Create a ParsedDocument with computed content hash."""
        if metadata is None:
            metadata = {}
            
        # Compute SHA256 hash of content for idempotency
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        return cls(
            content=content,
            metadata=metadata,
            content_hash=content_hash,
        )


class BaseParser(ABC):
    """Abstract base class for document parsers."""
    
    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions (e.g., ['.pdf', '.txt'])."""
        pass
    
    @property
    @abstractmethod
    def mime_types(self) -> list[str]:
        """Return list of supported MIME types."""
        pass
    
    @abstractmethod
    async def parse_file(self, file_content: bytes, filename: str) -> ParsedDocument:
        """
        Parse file content and return ParsedDocument.
        
        Args:
            file_content: Raw file bytes
            filename: Original filename
            
        Returns:
            ParsedDocument with extracted content and metadata
            
        Raises:
            DocumentProcessingError: If parsing fails
        """
        pass
    
    @abstractmethod
    async def parse_stream(self, file_stream: BinaryIO, filename: str) -> ParsedDocument:
        """
        Parse file from stream and return ParsedDocument.
        
        Args:
            file_stream: File stream
            filename: Original filename
            
        Returns:
            ParsedDocument with extracted content and metadata
            
        Raises:
            DocumentProcessingError: If parsing fails
        """
        pass
    
    def can_parse(self, filename: str) -> bool:
        """Check if parser can handle the given filename."""
        if not filename:
            return False
            
        # Check extension
        for ext in self.supported_extensions:
            if filename.lower().endswith(ext.lower()):
                return True
                
        return False
    
    def can_parse_mime_type(self, mime_type: str) -> bool:
        """Check if parser can handle the given MIME type."""
        return mime_type in self.mime_types
    
    def _validate_content(self, content: str, max_size_chars: int = 10_000_000) -> str:
        """
        Validate and clean extracted content.
        
        Args:
            content: Extracted text content
            max_size_chars: Maximum allowed content size in characters
            
        Returns:
            Cleaned content
            
        Raises:
            DocumentProcessingError: If content is invalid
        """
        if not content or not content.strip():
            raise DocumentProcessingError("Extracted content is empty")
        
        # Check size
        if len(content) > max_size_chars:
            raise DocumentProcessingError(
                f"Document too large: {len(content)} chars (max: {max_size_chars})"
            )
        
        # Clean content
        content = content.strip()
        
        # Remove excessive whitespace
        lines = [line.strip() for line in content.split('\n')]
        content = '\n'.join(line for line in lines if line)
        
        return content
    
    def _extract_basic_metadata(self, filename: str, file_size: int | None = None) -> dict[str, Any]:
        """Extract basic metadata from filename and file info."""
        metadata = {
            "filename": filename,
            "parser": self.__class__.__name__,
        }
        
        if file_size is not None:
            metadata["file_size_bytes"] = file_size
        
        # Extract file extension
        if '.' in filename:
            metadata["file_extension"] = filename.split('.')[-1].lower()
        
        return metadata

