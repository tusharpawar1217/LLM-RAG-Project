"""
URL crawler for fetching and parsing web content.
"""

import asyncio
import io
from typing import Any, BinaryIO
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.errors import DocumentProcessingError
from app.core.logging import get_logger
from app.ingestion.parsers.base import BaseParser, ParsedDocument

logger = get_logger(__name__)


class UrlCrawler(BaseParser):
    """Crawler for fetching and parsing web content."""
    
    def __init__(self, timeout: int = 30, max_content_length: int = 10_000_000):
        """
        Initialize URL crawler.
        
        Args:
            timeout: HTTP request timeout in seconds
            max_content_length: Maximum content size to download
        """
        self.timeout = timeout
        self.max_content_length = max_content_length
    
    @property
    def supported_extensions(self) -> list[str]:
        return []  # URLs don't have extensions
    
    @property
    def mime_types(self) -> list[str]:
        return [
            'text/html',
            'application/xhtml+xml',
            'text/plain',
            'text/markdown',
        ]
    
    def can_parse(self, filename: str) -> bool:
        """Check if the input looks like a URL."""
        return self._is_valid_url(filename)
    
    async def parse_file(self, file_content: bytes, filename: str) -> ParsedDocument:
        """Not applicable for URLs - use fetch_and_parse instead."""
        raise NotImplementedError("Use fetch_and_parse for URLs")
    
    async def parse_stream(self, file_stream: BinaryIO, filename: str) -> ParsedDocument:
        """Not applicable for URLs - use fetch_and_parse instead."""
        raise NotImplementedError("Use fetch_and_parse for URLs")
    
    async def fetch_and_parse(self, url: str) -> ParsedDocument:
        """
        Fetch URL content and parse it.
        
        Args:
            url: URL to fetch and parse
            
        Returns:
            ParsedDocument with extracted content
            
        Raises:
            DocumentProcessingError: If fetching or parsing fails
        """
        if not self._is_valid_url(url):
            raise DocumentProcessingError(f"Invalid URL: {url}")
        
        try:
            logger.info("Fetching URL", url=url)
            
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                limits=httpx.Limits(max_connections=10)
            ) as client:
                
                # Make HEAD request first to check content type and size
                try:
                    head_response = await client.head(url)
                    content_type = head_response.headers.get('content-type', '').lower()
                    content_length = head_response.headers.get('content-length')
                    
                    if content_length and int(content_length) > self.max_content_length:
                        raise DocumentProcessingError(
                            f"Content too large: {content_length} bytes (max: {self.max_content_length})"
                        )
                    
                    # Check if content type is supported
                    if not any(mime_type in content_type for mime_type in self.mime_types):
                        logger.warning(f"Potentially unsupported content type: {content_type}")
                
                except httpx.HTTPError:
                    # HEAD request failed, continue with GET
                    logger.debug("HEAD request failed, proceeding with GET")
                
                # Fetch the actual content
                response = await client.get(url)
                response.raise_for_status()
                
                content_type = response.headers.get('content-type', '').lower()
                
                # Check content length
                if len(response.content) > self.max_content_length:
                    raise DocumentProcessingError(
                        f"Content too large: {len(response.content)} bytes (max: {self.max_content_length})"
                    )
                
                # Parse based on content type
                if 'html' in content_type:
                    return await self._parse_html_content(response.content, url, response.headers)
                else:
                    # Treat as plain text
                    return await self._parse_text_content(response.content, url, response.headers)
        
        except httpx.HTTPError as e:
            logger.error("HTTP request failed", url=url, error=str(e))
            raise DocumentProcessingError(f"Failed to fetch URL: {str(e)}")
        except Exception as e:
            logger.error("URL parsing failed", url=url, error=str(e))
            raise DocumentProcessingError(f"Failed to parse URL content: {str(e)}")
    
    async def _parse_html_content(
        self, 
        content: bytes, 
        url: str, 
        headers: dict
    ) -> ParsedDocument:
        """Parse HTML content from URL."""
        try:
            # Parse HTML
            soup = BeautifulSoup(content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extract text content
            text_content = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text_content.splitlines())
            text_content = '\n'.join(line for line in lines if line)
            
            if not text_content.strip():
                raise DocumentProcessingError("No text content found in HTML")
            
            text_content = self._validate_content(text_content)
            
            # Extract metadata
            metadata = self._extract_basic_metadata(url, len(content))
            metadata.update({
                'url': url,
                'content_type': headers.get('content-type'),
                'html_metadata': self._extract_html_metadata(soup),
                'page_structure': self._analyze_html_structure(soup),
                'response_headers': dict(headers),
            })
            
            logger.info(
                "HTML content parsed successfully",
                url=url,
                content_chars=len(text_content),
                title=metadata.get('html_metadata', {}).get('title', 'No title'),
            )
            
            return ParsedDocument.create(text_content, metadata)
            
        except Exception as e:
            logger.error("HTML parsing failed", url=url, error=str(e))
            raise DocumentProcessingError(f"Failed to parse HTML: {str(e)}")
    
    async def _parse_text_content(
        self, 
        content: bytes, 
        url: str, 
        headers: dict
    ) -> ParsedDocument:
        """Parse plain text content from URL."""
        try:
            # Decode content
            text_content = self._decode_content(content)
            
            if not text_content.strip():
                raise DocumentProcessingError("No text content found")
            
            text_content = self._validate_content(text_content)
            
            # Extract metadata
            metadata = self._extract_basic_metadata(url, len(content))
            metadata.update({
                'url': url,
                'content_type': headers.get('content-type'),
                'response_headers': dict(headers),
            })
            
            logger.info(
                "Text content parsed successfully",
                url=url,
                content_chars=len(text_content),
            )
            
            return ParsedDocument.create(text_content, metadata)
            
        except Exception as e:
            logger.error("Text parsing failed", url=url, error=str(e))
            raise DocumentProcessingError(f"Failed to parse text: {str(e)}")
    
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
    
    def _extract_html_metadata(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract metadata from HTML document."""
        metadata = {}
        
        # Title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text().strip()
        
        # Meta tags
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            name = meta.get('name') or meta.get('property')
            content = meta.get('content')
            
            if name and content:
                # Common meta tags
                if name.lower() in ['description', 'keywords', 'author']:
                    metadata[name.lower()] = content
                elif name.lower() in ['og:title', 'og:description', 'twitter:title', 'twitter:description']:
                    metadata[name.lower().replace(':', '_')] = content
        
        # Language
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            metadata['language'] = html_tag.get('lang')
        
        return metadata
    
    def _analyze_html_structure(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Analyze HTML document structure."""
        structure = {
            'headings': [],
            'links': [],
            'images': [],
            'paragraphs': 0,
        }
        
        # Extract headings
        for level in range(1, 7):  # H1 through H6
            headings = soup.find_all(f'h{level}')
            for heading in headings:
                text = heading.get_text().strip()
                if text:
                    structure['headings'].append({
                        'level': level,
                        'text': text,
                    })
        
        # Count paragraphs
        paragraphs = soup.find_all('p')
        structure['paragraphs'] = len([p for p in paragraphs if p.get_text().strip()])
        
        # Extract links
        links = soup.find_all('a', href=True)
        for link in links[:10]:  # Limit to first 10 links
            href = link.get('href')
            text = link.get_text().strip()
            if href and text:
                structure['links'].append({
                    'url': href,
                    'text': text,
                })
        
        # Count images
        images = soup.find_all('img', src=True)
        structure['images'] = len(images)
        
        return structure
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if string is a valid URL."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
        except Exception:
            return False

