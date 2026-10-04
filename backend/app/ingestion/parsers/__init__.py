"""Document parsers package."""

from app.ingestion.parsers.base import BaseParser, ParsedDocument
from app.ingestion.parsers.docx import DocxParser
from app.ingestion.parsers.markdown import MarkdownParser
from app.ingestion.parsers.pdf import PdfParser
from app.ingestion.parsers.txt import TxtParser
from app.ingestion.parsers.url_crawler import UrlCrawler

__all__ = [
    "BaseParser",
    "ParsedDocument",
    "DocxParser",
    "MarkdownParser",
    "PdfParser",
    "TxtParser",
    "UrlCrawler",
]


