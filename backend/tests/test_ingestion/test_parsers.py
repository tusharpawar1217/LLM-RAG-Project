"""
Tests for document parsers.
"""

import tempfile
from pathlib import Path

import pytest
from docx import Document
from fpdf import FPDF

from app.ingestion.parsers.docx import DOCXParser
from app.ingestion.parsers.markdown import MarkdownParser
from app.ingestion.parsers.pdf import PDFParser
from app.ingestion.parsers.txt import TXTParser
from app.ingestion.parsers.url_crawler import URLCrawler


class TestTXTParser:
    """Test TXT parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = TXTParser()
    
    async def test_parse_simple_text(self):
        """Test parsing simple text file."""
        content = "Hello world!\nThis is a test document.\nIt has multiple lines."
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
        
        try:
            parsed_content, metadata = await self.parser.parse_file(temp_path)
            
            assert parsed_content == content
            assert metadata['file_size'] > 0
            assert metadata['line_count'] == 3
            assert metadata['char_count'] == len(content)
            assert 'encoding' in metadata
            
        finally:
            temp_path.unlink()
    
    async def test_parse_empty_file(self):
        """Test parsing empty text file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("")
            temp_path = Path(f.name)
        
        try:
            parsed_content, metadata = await self.parser.parse_file(temp_path)
            
            assert parsed_content == ""
            assert metadata['line_count'] == 0
            assert metadata['char_count'] == 0
            
        finally:
            temp_path.unlink()
    
    async def test_parse_large_file(self):
        """Test parsing large text file."""
        # Create a 1MB text file
        content = "This is line {}\n" * 50000  # ~1MB
        large_content = "".join([content.format(i) for i in range(50000)])
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(large_content)
            temp_path = Path(f.name)
        
        try:
            parsed_content, metadata = await self.parser.parse_file(temp_path)
            
            assert len(parsed_content) > 1000000  # ~1MB
            assert metadata['line_count'] == 50000
            assert 'file_size' in metadata
            
        finally:
            temp_path.unlink()


class TestMarkdownParser:
    """Test Markdown parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = MarkdownParser()
    
    async def test_parse_simple_markdown(self):
        """Test parsing simple markdown."""
        content = """# Main Title

This is a paragraph with **bold** and *italic* text.

## Section 1

- Item 1
- Item 2
- Item 3

### Subsection

Here's some code:

```python
def hello_world():
    print("Hello, World!")
```

## Section 2

[Link to example](https://example.com)

> This is a blockquote.
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
        
        try:
            parsed_content, metadata = await self.parser.parse_file(temp_path)
            
            # Content should be preserved
            assert "Main Title" in parsed_content
            assert "Section 1" in parsed_content
            assert "def hello_world():" in parsed_content
            assert "https://example.com" in parsed_content
            
            # Check metadata
            assert metadata['headings_count'] > 0
            assert metadata['links_count'] >= 1
            assert 'h1' in metadata['headings']
            assert 'h2' in metadata['headings']
            assert 'h3' in metadata['headings']
            
        finally:
            temp_path.unlink()
    
    async def test_parse_markdown_with_tables(self):
        """Test parsing markdown with tables."""
        content = """# Data Table

| Name | Age | City |
|------|-----|------|
| John | 30  | NYC  |
| Jane | 25  | LA   |

This table has 2 data rows.
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
        
        try:
            parsed_content, metadata = await self.parser.parse_file(temp_path)
            
            assert "Data Table" in parsed_content
            assert "John" in parsed_content
            assert "Jane" in parsed_content
            assert metadata.get('tables_count', 0) >= 1
            
        finally:
            temp_path.unlink()


class TestPDFParser:
    """Test PDF parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = PDFParser()
    
    async def test_parse_simple_pdf(self):
        """Test parsing simple PDF."""
        # Create a simple PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(40, 10, 'Test PDF Document')
        pdf.ln()
        pdf.set_font('Arial', '', 12)
        pdf.cell(40, 10, 'This is page 1 content.')
        pdf.ln()
        pdf.cell(40, 10, 'It has multiple lines of text.')
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf.output(f.name)
            temp_path = Path(f.name)
        
        try:
            parsed_content, metadata = await self.parser.parse_file(temp_path)
            
            # Content should be extracted
            assert "Test PDF Document" in parsed_content
            assert "page 1 content" in parsed_content
            assert "multiple lines" in parsed_content
            
            # Check metadata
            assert metadata['page_count'] == 1
            assert metadata['file_size'] > 0
            assert len(metadata['pages']) == 1
            assert 'page_1' in metadata['pages']
            
        finally:
            temp_path.unlink()
    
    @pytest.mark.skip(reason="Requires complex PDF creation")
    async def test_parse_multipage_pdf(self):
        """Test parsing multi-page PDF."""
        # This would require creating a more complex PDF
        # Skip for now, can be implemented with proper PDF generation
        pass


class TestDOCXParser:
    """Test DOCX parser."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = DOCXParser()
    
    async def test_parse_simple_docx(self):
        """Test parsing simple DOCX."""
        # Create a simple DOCX document
        doc = Document()
        doc.add_heading('Test Document', 0)
        doc.add_paragraph('This is the first paragraph.')
        doc.add_heading('Section 1', level=1)
        doc.add_paragraph('This is content under section 1.')
        doc.add_paragraph('Another paragraph with some text.')
        
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
            doc.save(f.name)
            temp_path = Path(f.name)
        
        try:
            parsed_content, metadata = await self.parser.parse_file(temp_path)
            
            # Content should be extracted
            assert "Test Document" in parsed_content
            assert "first paragraph" in parsed_content
            assert "Section 1" in parsed_content
            assert "section 1" in parsed_content
            
            # Check metadata
            assert metadata['paragraph_count'] >= 3
            assert metadata['heading_count'] >= 2
            
        finally:
            temp_path.unlink()
    
    async def test_parse_docx_with_formatting(self):
        """Test parsing DOCX with various formatting."""
        doc = Document()
        doc.add_heading('Formatted Document', 0)
        
        # Add paragraph with formatting
        p = doc.add_paragraph()
        p.add_run('This is ').bold = False
        p.add_run('bold text').bold = True
        p.add_run(' and this is ').bold = False
        p.add_run('italic text').italic = True
        
        # Add list
        doc.add_paragraph('Item 1', style='List Bullet')
        doc.add_paragraph('Item 2', style='List Bullet')
        
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
            doc.save(f.name)
            temp_path = Path(f.name)
        
        try:
            parsed_content, metadata = await self.parser.parse_file(temp_path)
            
            assert "Formatted Document" in parsed_content
            assert "bold text" in parsed_content
            assert "italic text" in parsed_content
            assert "Item 1" in parsed_content
            assert "Item 2" in parsed_content
            
        finally:
            temp_path.unlink()


class TestURLCrawler:
    """Test URL crawler."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = URLCrawler()
    
    @pytest.mark.asyncio
    async def test_parse_simple_html(self):
        """Test parsing simple HTML page."""
        # This would require a mock HTTP server or actual URL
        # Skip for now, can be implemented with aioresponses
        pytest.skip("Requires mock HTTP server setup")
    
    @pytest.mark.asyncio 
    async def test_parse_with_headers(self):
        """Test parsing with custom headers."""
        pytest.skip("Requires mock HTTP server setup")
    
    @pytest.mark.asyncio
    async def test_parse_invalid_url(self):
        """Test parsing invalid URL."""
        with pytest.raises(Exception):
            await self.parser.parse_url("not-a-url")
    
    @pytest.mark.asyncio
    async def test_parse_timeout(self):
        """Test parsing with timeout."""
        # Test with a URL that would timeout
        pytest.skip("Requires network timeout setup")

