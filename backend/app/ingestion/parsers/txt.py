"""
Plain text document parser.
"""

import io
from typing import Any, BinaryIO

from app.core.errors import DocumentProcessingError
from app.core.logging import get_logger
from app.ingestion.parsers.base import BaseParser, ParsedDocument

logger = get_logger(__name__)


class TxtParser(BaseParser):
    """Parser for plain text documents."""
    
    @property
    def supported_extensions(self) -> list[str]:
        return ['.txt', '.text', '.log', '.csv', '.tsv', '.json']
    
    @property
    def mime_types(self) -> list[str]:
        return [
            'text/plain',
            'text/csv', 
            'text/tab-separated-values',
            'application/json',
            'application/x-javascript',
            'text/x-log',
        ]
    
    async def parse_file(self, file_content: bytes, filename: str) -> ParsedDocument:
        """Parse text from bytes."""
        try:
            content = self._decode_content(file_content)
            return await self._parse_text_content(content, filename)
        except Exception as e:
            logger.error("Text parsing failed", filename=filename, error=str(e))
            raise DocumentProcessingError(f"Failed to parse text: {str(e)}")
    
    async def parse_stream(self, file_stream: BinaryIO, filename: str) -> ParsedDocument:
        """Parse text from stream."""
        try:
            content_bytes = file_stream.read()
            content = self._decode_content(content_bytes)
            return await self._parse_text_content(content, filename)
        except Exception as e:
            logger.error("Text parsing failed", filename=filename, error=str(e))
            raise DocumentProcessingError(f"Failed to parse text: {str(e)}")
    
    async def _parse_text_content(self, content: str, filename: str) -> ParsedDocument:
        """Process text content and extract structure."""
        if not content.strip():
            raise DocumentProcessingError("Text content is empty")
        
        # Clean and validate content
        content = self._clean_text_content(content)
        content = self._validate_content(content)
        
        # Analyze text structure
        structure = self._analyze_text_structure(content)
        
        # Build metadata
        metadata = self._extract_basic_metadata(filename, len(content.encode('utf-8')))
        metadata.update({
            "structure": structure,
            "encoding_detected": self._detect_encoding_info(content),
            "text_features": self._detect_text_features(content, filename),
        })
        
        logger.info(
            "Text parsed successfully",
            filename=filename,
            content_chars=len(content),
            lines=structure.get('line_count', 0),
            paragraphs=structure.get('paragraph_count', 0),
        )
        
        return ParsedDocument.create(content, metadata)
    
    def _decode_content(self, content_bytes: bytes) -> str:
        """Decode bytes to string with encoding detection."""
        # Try UTF-8 first
        try:
            return content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            pass
        
        # Try other common encodings
        encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1', 'ascii']
        
        for encoding in encodings:
            try:
                return content_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        
        # Fallback with error handling
        return content_bytes.decode('utf-8', errors='replace')
    
    def _clean_text_content(self, content: str) -> str:
        """Clean and normalize text content."""
        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove null bytes and other control characters (except common ones)
        content = ''.join(char for char in content if ord(char) >= 32 or char in '\n\t')
        
        # Normalize multiple spaces (but preserve intentional formatting)
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Strip trailing whitespace but preserve leading whitespace for structure
            cleaned_line = line.rstrip()
            cleaned_lines.append(cleaned_line)
        
        content = '\n'.join(cleaned_lines)
        
        # Remove excessive empty lines (more than 2 consecutive)
        while '\n\n\n\n' in content:
            content = content.replace('\n\n\n\n', '\n\n\n')
        
        return content.strip()
    
    def _analyze_text_structure(self, content: str) -> dict[str, Any]:
        """Analyze the structure of the text document."""
        lines = content.split('\n')
        
        structure = {
            'line_count': len(lines),
            'paragraph_count': 0,
            'empty_line_count': 0,
            'average_line_length': 0,
            'max_line_length': 0,
            'indented_lines': 0,
            'potential_headers': [],
            'bullet_points': 0,
            'numbered_items': 0,
        }
        
        if not lines:
            return structure
        
        # Analyze lines
        non_empty_lines = []
        current_paragraph = []
        paragraph_count = 0
        
        for line_num, line in enumerate(lines, 1):
            if not line.strip():
                structure['empty_line_count'] += 1
                if current_paragraph:
                    paragraph_count += 1
                    current_paragraph = []
            else:
                non_empty_lines.append(line)
                current_paragraph.append(line)
                
                # Check for indentation
                if line.startswith((' ', '\t')):
                    structure['indented_lines'] += 1
                
                # Check for bullet points
                stripped = line.strip()
                if stripped.startswith(('•', '●', '○', '-', '*', '+')):
                    structure['bullet_points'] += 1
                
                # Check for numbered items
                import re
                if re.match(r'^\s*\d+[\.\)]\s+', line):
                    structure['numbered_items'] += 1
                
                # Potential headers (short lines, maybe all caps or title case)
                if len(stripped) < 50 and not stripped.endswith('.'):
                    if (stripped.isupper() and len(stripped.split()) > 1) or \
                       (stripped.istitle() and len(stripped.split()) <= 6):
                        structure['potential_headers'].append({
                            'line_number': line_num,
                            'text': stripped,
                            'type': 'uppercase' if stripped.isupper() else 'title_case'
                        })
        
        # Final paragraph count
        if current_paragraph:
            paragraph_count += 1
        
        structure['paragraph_count'] = paragraph_count
        
        # Calculate statistics
        if non_empty_lines:
            line_lengths = [len(line) for line in non_empty_lines]
            structure['average_line_length'] = sum(line_lengths) / len(line_lengths)
            structure['max_line_length'] = max(line_lengths)
        
        return structure
    
    def _detect_encoding_info(self, content: str) -> dict[str, Any]:
        """Detect information about the text encoding and character usage."""
        info = {
            'has_unicode': False,
            'has_special_chars': False,
            'character_sets': [],
        }
        
        for char in content:
            if ord(char) > 127:
                info['has_unicode'] = True
                break
        
        # Check for special characters
        special_chars = set('!@#$%^&*()_+-=[]{}|;:,.<>?')
        if any(char in special_chars for char in content):
            info['has_special_chars'] = True
        
        return info
    
    def _detect_text_features(self, content: str, filename: str) -> dict[str, bool]:
        """Detect specific features based on filename and content."""
        features = {
            'is_csv': False,
            'is_json': False,
            'is_log_file': False,
            'is_code': False,
            'has_timestamps': False,
            'has_urls': False,
            'has_emails': False,
        }
        
        # File extension based detection
        if filename.lower().endswith('.csv'):
            features['is_csv'] = True
        elif filename.lower().endswith('.json'):
            features['is_json'] = True
        elif filename.lower().endswith('.log'):
            features['is_log_file'] = True
        
        # Content-based detection
        import re
        
        # Check for JSON structure
        if content.strip().startswith(('{', '[')):
            try:
                import json
                json.loads(content)
                features['is_json'] = True
            except:
                pass
        
        # Check for CSV structure
        if ',' in content and content.count('\n') > 1:
            lines = content.split('\n')[:5]  # Check first 5 lines
            comma_counts = [line.count(',') for line in lines if line.strip()]
            if len(set(comma_counts)) <= 2:  # Consistent comma count
                features['is_csv'] = True
        
        # Check for code-like patterns
        code_patterns = [
            r'function\s+\w+\s*\(',
            r'class\s+\w+\s*[:\{]',
            r'import\s+\w+',
            r'#include\s*<',
            r'def\s+\w+\s*\(',
            r'public\s+class\s+\w+',
        ]
        
        if any(re.search(pattern, content) for pattern in code_patterns):
            features['is_code'] = True
        
        # Check for timestamps
        timestamp_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{2}:\d{2}:\d{2}',  # HH:MM:SS
        ]
        
        if any(re.search(pattern, content) for pattern in timestamp_patterns):
            features['has_timestamps'] = True
        
        # Check for URLs
        if re.search(r'https?://[^\s]+', content):
            features['has_urls'] = True
        
        # Check for email addresses
        if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content):
            features['has_emails'] = True
        
        return features