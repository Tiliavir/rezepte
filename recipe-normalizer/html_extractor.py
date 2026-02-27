"""Extract readable plain text from HTML content."""

import logging

from readability import Document
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_text_from_html(html: str) -> str:
    """Extract the main readable text from an HTML string."""
    try:
        doc = Document(html)
        readable_html = doc.summary()
        soup = BeautifulSoup(readable_html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        logger.debug("Extracted %d characters from HTML via readability", len(text))
        return text
    except Exception as exc:
        logger.warning("readability failed (%s), falling back to plain BeautifulSoup", exc)
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        return text
