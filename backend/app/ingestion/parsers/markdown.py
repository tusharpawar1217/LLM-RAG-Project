"""
Markdown document parser.
"""

import io
import re
from typing import Any, BinaryIO

import markdown
from markdown.extensions import codehilite, fenced_code, tables, toc

from app.core.errors import DocumentProcessingError
from app.core.logging import get_logger
from app.ingestion.parsers.base import BaseParser, ParsedDocument

logger = get_logger(__name__)


class MarkdownParser(BaseParser):
    """Parser for Markdown documents."""
    
    @property
    def supported_extensions(self) -> list[str]:
        return ['.md', '.markdown', '.mdown', '.mkd']
    
    @property
    def mime_types(self) -> list[str]:
        return ['text/markdown', 'text/x-markdown']
    
    async def parse_file(self, file_content: bytes, filename: str) -> ParsedDocument:
        """Parse Markdown from bytes."""
        try:
            # Decode content
            content = self._decode_content(file_content)
            return await self._parse_markdown_content(content, filename)
        except Exception as e:
            logger.error("Markdown parsing failed", filename=filename, error=str(e))
            raise DocumentProcessingError(f"Failed to parse Markdown: {str(e)}")
    
    async def parse_stream(self, file_stream: BinaryIO, filename: str) -> ParsedDocument:
        """Parse Markdown from stream."""
        try:
            content_bytes = file_stream.read()
            content = self._decode_content(content_bytes)
            return await self._parse_markdown_content(content, filename)
        except Exception as e:
            logger.error("Markdown parsing failed", filename=filename, error=str(e))
            raise DocumentProcessingError(f"Failed to parse Markdown: {str(e)}")
    
    async def _parse_markdown_content(self, content: str, filename: str) -> ParsedDocument:
        """Parse Markdown content and extract structure."""
        if not content.strip():
            raise DocumentProcessingError("Markdown content is empty")
        
        # Set up markdown processor with extensions
        md = markdown.Markdown(
            extensions=[
                'toc',          # Table of contents
                'tables',       # Table support
                'fenced_code',  # Fenced code blocks
                'codehilite',   # Code syntax highlighting
                'attr_list',    # Attribute lists
                'def_list',     # Definition lists
            ],
            extension_configs={
                'toc': {
                    'anchorlink': True,
                    'permalink': True,
                }
            }
        )
        
        # Convert to HTML (for structure analysis)
        html_content = md.convert(content)
        
        # Extract structure information
        structure = self._extract_markdown_structure(content)
        
        # Get table of contents if available
        toc = getattr(md, 'toc', '')
        toc_tokens = getattr(md, 'toc_tokens', [])
        
        # Clean content for text processing
        clean_content = self._clean_markdown_content(content)
        clean_content = self._validate_content(clean_content)
        
        # Build metadata
        metadata = self._extract_basic_metadata(filename, len(content.encode('utf-8')))
        metadata.update({
            "raw_content": content,
            "html_content": html_content,
            "structure": structure,
            "toc": toc,
            "toc_tokens": toc_tokens,
            "markdown_features": self._detect_markdown_features(content),
        })
        
        logger.info(
            "Markdown parsed successfully",
            filename=filename,
            content_chars=len(clean_content),
            headings=len(structure.get('headings', [])),
            code_blocks=len(structure.get('code_blocks', [])),
            tables=len(structure.get('tables', [])),
        )
        
        return ParsedDocument.create(clean_content, metadata)
    
    def _decode_content(self, content_bytes: bytes) -> str:
        """Decode bytes to string with encoding detection."""
        # Try UTF-8 first
        try:
            return content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            pass
        
        # Try other common encodings
        encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                return content_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        
        # Fallback with error handling
        return content_bytes.decode('utf-8', errors='replace')
    
    def _extract_markdown_structure(self, content: str) -> dict[str, Any]:
        """Extract structural elements from Markdown."""
        structure = {
            'headings': [],
            'code_blocks': [],
            'tables': [],
            'links': [],
            'images': [],
        }
        
        lines = content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Extract headings
            heading_match = re.match(r'^(#{1,6})\s+(.+)', line_stripped)
            if heading_match:
                level = len(heading_match.group(1))
                text = heading_match.group(2).strip()
                structure['headings'].append({
                    'level': level,
                    'text': text,
                    'line_number': line_num,
                })
                continue
            
            # Extract fenced code blocks
            if line_stripped.startswith('```'):
                language = line_stripped[3:].strip()
                structure['code_blocks'].append({
                    'language': language if language else 'text',
                    'line_number': line_num,
                })
                continue
        
        # Extract links
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        for match in re.finditer(link_pattern, content):
            structure['links'].append({
                'text': match.group(1),
                'url': match.group(2),
            })
        
        # Extract images
        image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        for match in re.finditer(image_pattern, content):
            structure['images'].append({
                'alt_text': match.group(1),
                'url': match.group(2),
            })
        
        # Extract tables (simple detection)
        table_pattern = r'\|.+\|'
        table_lines = [i for i, line in enumerate(lines) if re.match(table_pattern, line.strip())]
        if table_lines:
            structure['tables'].append({
                'line_numbers': table_lines,
                'estimated_rows': len(table_lines),
            })
        
        return structure
    
    def _clean_markdown_content(self, content: str) -> str:
        """Clean Markdown content for text processing."""
        # Remove Markdown syntax while preserving content
        cleaned = content
        
        # Remove headers but keep the text
        cleaned = re.sub(r'^#{1,6}\s+', '', cleaned, flags=re.MULTILINE)
        
        # Remove emphasis markers but keep text
        cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)  # Bold
        cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)      # Italic
        cleaned = re.sub(r'__([^_]+)__', r'\1', cleaned)      # Bold
        cleaned = re.sub(r'_([^_]+)_', r'\1', cleaned)        # Italic
        
        # Remove links but keep text
        cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)
        
        # Remove images
        cleaned = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', cleaned)
        
        # Remove code blocks
        cleaned = re.sub(r'```[^`]*```', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)  # Inline code
        
        # Remove horizontal rules
        cleaned = re.sub(r'^[-*_]{3,}$', '', cleaned, flags=re.MULTILINE)
        
        # Remove blockquote markers but keep content
        cleaned = re.sub(r'^>\s*', '', cleaned, flags=re.MULTILINE)
        
        # Clean up list markers
        cleaned = re.sub(r'^\s*[-*+]\s+', '', cleaned, flags=re.MULTILINE)  # Unordered
        cleaned = re.sub(r'^\s*\d+\.\s+', '', cleaned, flags=re.MULTILINE)  # Ordered
        
        # Clean up extra whitespace
        cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)  # Multiple newlines
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)            # Multiple spaces/tabs
        
        return cleaned.strip()
    
    def _detect_markdown_features(self, content: str) -> dict[str, bool]:
        """Detect which Markdown features are used in the document."""
        features = {
            'headings': bool(re.search(r'^#{1,6}\s+', content, re.MULTILINE)),
            'emphasis': bool(re.search(r'[*_]{1,2}[^*_]+[*_]{1,2}', content)),
            'code_blocks': bool(re.search(r'```', content)),
            'inline_code': bool(re.search(r'`[^`]+`', content)),
            'links': bool(re.search(r'\[[^\]]+\]\([^)]+\)', content)),
            'images': bool(re.search(r'!\[[^\]]*\]\([^)]+\)', content)),
            'tables': bool(re.search(r'\|.+\|', content)),
            'lists': bool(re.search(r'^\s*[-*+]\s+', content, re.MULTILINE)),
            'ordered_lists': bool(re.search(r'^\s*\d+\.\s+', content, re.MULTILINE)),
            'blockquotes': bool(re.search(r'^>\s*', content, re.MULTILINE)),
            'horizontal_rules': bool(re.search(r'^[-*_]{3,}$', content, re.MULTILINE)),
        }
        
        return features