"""
Document chunking service using LangChain text splitters.
"""

from typing import Any

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.core.config import settings
from app.core.errors import DocumentProcessingError
from app.core.logging import get_logger
from app.ingestion.parsers.base import ParsedDocument

logger = get_logger(__name__)


class DocumentChunk:
    """Represents a chunk of document content."""
    
    def __init__(
        self,
        content: str,
        metadata: dict[str, Any],
        chunk_index: int,
        page_number: int | None = None,
        section_heading: str | None = None,
    ):
        self.content = content
        self.metadata = metadata
        self.chunk_index = chunk_index
        self.page_number = page_number
        self.section_heading = section_heading
        self.token_count = self._estimate_tokens(content)
    
    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count using simple heuristic (4 chars = ~1 token)."""
        return len(text) // 4
    
    def to_dict(self) -> dict[str, Any]:
        """Convert chunk to dictionary for storage."""
        return {
            "content": self.content,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "section_heading": self.section_heading,
            "token_count": self.token_count,
            "metadata": self.metadata,
        }


class ChunkingService:
    """Service for chunking documents using different strategies."""
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        strategy: str = None,
    ):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self.strategy = strategy or settings.CHUNKING_STRATEGY
        
        # Initialize text splitters
        self._init_splitters()
    
    def _init_splitters(self):
        """Initialize LangChain text splitters."""
        # Recursive character text splitter (default)
        self.recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )
        
        # Markdown header text splitter
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "Header 1"),
                ("##", "Header 2"),
                ("###", "Header 3"),
                ("####", "Header 4"),
                ("#####", "Header 5"),
                ("######", "Header 6"),
            ]
        )
    
    async def chunk_document(self, document: ParsedDocument) -> list[DocumentChunk]:
        """
        Chunk a parsed document using the configured strategy.
        
        Args:
            document: ParsedDocument to chunk
            
        Returns:
            List of DocumentChunk objects
            
        Raises:
            DocumentProcessingError: If chunking fails
        """
        try:
            if not document.content.strip():
                raise DocumentProcessingError("Document content is empty")
            
            logger.info(
                "Starting document chunking",
                strategy=self.strategy,
                content_length=len(document.content),
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
            
            if self.strategy == "markdown":
                chunks = await self._chunk_with_markdown_strategy(document)
            elif self.strategy == "recursive":
                chunks = await self._chunk_with_recursive_strategy(document)
            else:
                logger.warning(f"Unknown chunking strategy: {self.strategy}, using recursive")
                chunks = await self._chunk_with_recursive_strategy(document)
            
            if not chunks:
                raise DocumentProcessingError("No chunks generated from document")
            
            logger.info(
                "Document chunking completed",
                chunks_generated=len(chunks),
                avg_chunk_size=sum(len(chunk.content) for chunk in chunks) // len(chunks),
                total_tokens=sum(chunk.token_count for chunk in chunks),
            )
            
            return chunks
            
        except DocumentProcessingError:
            raise
        except Exception as e:
            logger.error("Document chunking failed", error=str(e))
            raise DocumentProcessingError(f"Failed to chunk document: {str(e)}")
    
    async def _chunk_with_recursive_strategy(self, document: ParsedDocument) -> list[DocumentChunk]:
        """Chunk document using recursive character text splitter."""
        try:
            # Split the text
            text_chunks = self.recursive_splitter.split_text(document.content)
            
            chunks = []
            for i, chunk_text in enumerate(text_chunks):
                # Try to extract page number and section info from metadata
                page_number = self._extract_page_for_chunk(document, chunk_text, i)
                section_heading = self._extract_section_for_chunk(document, chunk_text, i)
                
                chunk = DocumentChunk(
                    content=chunk_text.strip(),
                    metadata={
                        **document.metadata,
                        "chunking_strategy": "recursive",
                        "original_length": len(document.content),
                    },
                    chunk_index=i,
                    page_number=page_number,
                    section_heading=section_heading,
                )
                chunks.append(chunk)
            
            return chunks
            
        except Exception as e:
            logger.error("Recursive chunking failed", error=str(e))
            raise DocumentProcessingError(f"Recursive chunking failed: {str(e)}")
    
    async def _chunk_with_markdown_strategy(self, document: ParsedDocument) -> list[DocumentChunk]:
        """Chunk document using markdown-aware strategy."""
        try:
            # Check if document looks like markdown
            is_markdown = self._is_markdown_document(document)
            
            if is_markdown:
                # Use markdown header splitter first
                header_splits = self.markdown_splitter.split_text(document.content)
                
                chunks = []
                chunk_index = 0
                
                for split in header_splits:
                    content = split.page_content
                    metadata = split.metadata
                    
                    # If the split is still too large, further split it
                    if len(content) > self.chunk_size:
                        sub_chunks = self.recursive_splitter.split_text(content)
                        
                        for sub_chunk_text in sub_chunks:
                            chunk = DocumentChunk(
                                content=sub_chunk_text.strip(),
                                metadata={
                                    **document.metadata,
                                    **metadata,
                                    "chunking_strategy": "markdown",
                                    "original_length": len(document.content),
                                },
                                chunk_index=chunk_index,
                                section_heading=self._get_section_from_metadata(metadata),
                            )
                            chunks.append(chunk)
                            chunk_index += 1
                    else:
                        chunk = DocumentChunk(
                            content=content.strip(),
                            metadata={
                                **document.metadata,
                                **metadata,
                                "chunking_strategy": "markdown",
                                "original_length": len(document.content),
                            },
                            chunk_index=chunk_index,
                            section_heading=self._get_section_from_metadata(metadata),
                        )
                        chunks.append(chunk)
                        chunk_index += 1
                
                return chunks
            else:
                # Fall back to recursive strategy
                logger.info("Document doesn't appear to be markdown, using recursive strategy")
                return await self._chunk_with_recursive_strategy(document)
            
        except Exception as e:
            logger.error("Markdown chunking failed", error=str(e))
            raise DocumentProcessingError(f"Markdown chunking failed: {str(e)}")
    
    def _is_markdown_document(self, document: ParsedDocument) -> bool:
        """Check if document appears to be markdown."""
        # Check file extension from metadata
        filename = document.metadata.get("filename", "")
        if any(filename.lower().endswith(ext) for ext in ['.md', '.markdown', '.mdown', '.mkd']):
            return True
        
        # Check for markdown features in metadata
        markdown_features = document.metadata.get("markdown_features", {})
        if markdown_features.get("headings") or markdown_features.get("code_blocks"):
            return True
        
        # Simple content analysis
        content = document.content
        markdown_indicators = [
            content.count('#') > 2,  # Headers
            '```' in content,         # Code blocks
            content.count('*') > 5,   # Emphasis/lists
            content.count('[') > 0 and content.count('](') > 0,  # Links
        ]
        
        return sum(markdown_indicators) >= 2
    
    def _extract_page_for_chunk(
        self, 
        document: ParsedDocument, 
        chunk_text: str, 
        chunk_index: int
    ) -> int | None:
        """Try to extract page number for a chunk."""
        # For PDF documents, try to map chunk to page
        pages = document.metadata.get("pages", [])
        if not pages:
            return None
        
        # Simple heuristic: find the page that contains part of this chunk
        chunk_start = chunk_text[:100].strip()
        
        for page in pages:
            if chunk_start in page.get("text", ""):
                return page.get("page_number")
        
        # Fallback: estimate based on chunk position
        if len(pages) > 0:
            total_chunks_estimated = len(document.content) // self.chunk_size
            if total_chunks_estimated > 0:
                page_ratio = chunk_index / total_chunks_estimated
                estimated_page = int(page_ratio * len(pages)) + 1
                return min(estimated_page, len(pages))
        
        return None
    
    def _extract_section_for_chunk(
        self,
        document: ParsedDocument,
        chunk_text: str,
        chunk_index: int
    ) -> str | None:
        """Try to extract section heading for a chunk."""
        # For markdown documents
        headings = document.metadata.get("structure", {}).get("headings", [])
        if headings:
            # Find the most recent heading before this chunk
            chunk_start_pos = document.content.find(chunk_text[:50])
            
            best_heading = None
            for heading in headings:
                heading_text = heading.get("text", "")
                heading_pos = document.content.find(heading_text)
                
                if heading_pos >= 0 and heading_pos <= chunk_start_pos:
                    if not best_heading or heading_pos > document.content.find(best_heading):
                        best_heading = heading_text
            
            return best_heading
        
        # For other document types, try to find potential headers
        potential_headers = document.metadata.get("structure", {}).get("potential_headers", [])
        if potential_headers:
            # Use similar logic as above
            chunk_start_pos = document.content.find(chunk_text[:50])
            
            best_header = None
            for header in potential_headers:
                header_text = header.get("text", "")
                header_pos = document.content.find(header_text)
                
                if header_pos >= 0 and header_pos <= chunk_start_pos:
                    best_header = header_text
            
            return best_header
        
        return None
    
    def _get_section_from_metadata(self, metadata: dict[str, Any]) -> str | None:
        """Extract section heading from LangChain split metadata."""
        # Look for header information in metadata
        for key, value in metadata.items():
            if "header" in key.lower() and value:
                return str(value)
        
        return None
    
    def validate_chunks(self, chunks: list[DocumentChunk]) -> bool:
        """Validate that chunks meet quality criteria."""
        if not chunks:
            return False
        
        # Check that chunks aren't too small or too large
        for chunk in chunks:
            content_length = len(chunk.content)
            
            # Minimum chunk size (unless it's the last small chunk)
            if content_length < 50 and len(chunks) > 1:
                logger.warning(f"Chunk {chunk.chunk_index} is very small: {content_length} chars")
            
            # Maximum chunk size
            if content_length > self.chunk_size * 1.5:
                logger.warning(f"Chunk {chunk.chunk_index} is too large: {content_length} chars")
        
        # Check for reasonable overlap
        if len(chunks) > 1:
            overlaps = []
            for i in range(len(chunks) - 1):
                current = chunks[i].content
                next_chunk = chunks[i + 1].content
                
                # Find common substring at the end of current and start of next
                max_overlap = min(len(current), len(next_chunk), self.chunk_overlap)
                
                for j in range(max_overlap, 0, -1):
                    if current[-j:] == next_chunk[:j]:
                        overlaps.append(j)
                        break
                else:
                    overlaps.append(0)
            
            avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0
            logger.info(f"Average chunk overlap: {avg_overlap} characters")
        
        return True

