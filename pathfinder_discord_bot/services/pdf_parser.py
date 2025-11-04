"""PDF parsing service using PyMuPDF."""
import logging
from pathlib import Path
from typing import NamedTuple

import pymupdf  # PyMuPDF

logger = logging.getLogger(__name__)


class PageText(NamedTuple):
    """Text extracted from a single PDF page."""

    page_number: int
    text: str
    char_count: int


class PDFParserService:
    """Parses PDF files and extracts text content."""

    @staticmethod
    def extract_text_from_pdf(pdf_path: str | Path) -> list[PageText]:
        """Extract text from all pages of a PDF and return list of PageText objects."""
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        logger.info(f"Extracting text from PDF: {pdf_path.name}")

        pages = []

        try:
            with pymupdf.open(pdf_path) as doc:
                total_pages = len(doc)
                logger.info(f"PDF has {total_pages} pages")

                for page_num, page in enumerate(doc, start=1):
                    text = page.get_text()
                    char_count = len(text)

                    pages.append(
                        PageText(
                            page_number=page_num,
                            text=text,
                            char_count=char_count,
                        )
                    )

                    if page_num % 50 == 0:
                        logger.info(f"Processed {page_num}/{total_pages} pages...")

                logger.info(
                    f"Extraction complete: {total_pages} pages, "
                    f"{sum(p.char_count for p in pages):,} total characters"
                )

        except Exception as e:
            logger.exception(f"Error parsing PDF {pdf_path.name}: {e}")
            raise

        return pages

    @staticmethod
    def get_pdf_metadata(pdf_path: str | Path) -> dict[str, str]:
        """Extract metadata (title, author, etc.) from PDF file."""
        pdf_path = Path(pdf_path)

        with pymupdf.open(pdf_path) as doc:
            metadata = doc.metadata or {}

        return {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
            "creator": metadata.get("creator", ""),
        }
