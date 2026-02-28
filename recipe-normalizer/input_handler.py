"""Input detection and raw-text extraction for various file/URL types."""

import logging
import urllib.parse
import urllib.request
from pathlib import Path

from html_extractor import extract_text_from_html

logger = logging.getLogger(__name__)

# File extensions handled per category
_TEXT_EXTENSIONS = {".txt", ".md"}
_HTML_EXTENSIONS = {".html", ".htm"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}
_PDF_EXTENSIONS = {".pdf"}


def is_url(value: str) -> bool:
    """Return True when *value* looks like an HTTP/HTTPS URL."""
    return value.startswith("http://") or value.startswith("https://")  # NOSONAR python:S5332


def load_raw_text(source: str) -> str:
    """
    Detect the type of *source* (URL, file path) and return its plain text.

    Raises
    ------
    ValueError
        When the source type is unsupported.
    FileNotFoundError
        When the given file path does not exist.
    """
    if is_url(source):
        return _load_url(source)

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {source}")

    ext = path.suffix.lower()

    if ext in _TEXT_EXTENSIONS:
        logger.debug("Reading plain text from %s", path)
        return path.read_text(encoding="utf-8")

    if ext in _HTML_EXTENSIONS:
        logger.debug("Extracting text from local HTML file %s", path)
        html = path.read_text(encoding="utf-8")
        return extract_text_from_html(html)

    if ext in _IMAGE_EXTENSIONS:
        logger.debug("Running OCR on image %s", path)
        from ocr import extract_text_from_image
        return extract_text_from_image(path)

    if ext in _PDF_EXTENSIONS:
        logger.debug("Extracting text from PDF %s", path)
        from ocr import extract_text_from_pdf
        return extract_text_from_pdf(path)

    raise ValueError(
        f"Unsupported input type '{ext}'. "
        "Supported: .txt .md .html .htm .jpg .jpeg .png .gif .bmp .tiff .webp .pdf"
    )


def _load_url(url: str) -> str:
    """Download a URL and extract readable text from its HTML."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Only http/https URLs are supported, got scheme: {parsed.scheme!r}")
    logger.info("Downloading %s", url)
    req = urllib.request.Request(  # NOSONAR python:S5144
        url,
        headers={"User-Agent": "recipe-normalizer/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310  # NOSONAR python:S5144
        content_type = response.headers.get("Content-Type", "")
        raw_bytes = response.read()

    # Detect encoding from Content-Type header
    encoding = "utf-8"
    if "charset=" in content_type:
        encoding = content_type.split("charset=")[-1].split(";")[0].strip()

    html = raw_bytes.decode(encoding, errors="replace")
    logger.debug("Downloaded %d bytes from %s", len(raw_bytes), url)
    return extract_text_from_html(html)
