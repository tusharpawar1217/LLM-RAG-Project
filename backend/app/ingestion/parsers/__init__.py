"""Document parsers package."""

from app.ingestion.parsers.base import BaseParser, ParseResult
from app.ingestion.parsers.docx import DOCXParser
from app.ingestion.parsers.markdown import MarkdownParser
from app.ingestion.parsers.pdf import PDFParser
from app.ingestion.parsers.txt import TXTParser
from app.ingestion.parsers.url_crawler import URLCrawler

__all__ = [
    "BaseParser",
    "ParseResult",
    "PDFParser", 
    "DOCXParser",
    "MarkdownParser",
    "TXTParser",
    "URLCrawler",
]