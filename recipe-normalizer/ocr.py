"""OCR support for images and PDF files."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_text_from_image(path: Path) -> str:
    """Run Tesseract OCR on an image file and return the extracted text."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise ImportError(
            "pytesseract and Pillow are required for image OCR. "
            "Install them with: pip install pytesseract Pillow"
        ) from exc

    image = Image.open(path)
    text = pytesseract.image_to_string(image, lang="deu+eng")
    logger.debug("OCR extracted %d characters from %s", len(text), path)
    return text


def extract_text_from_pdf(path: Path) -> str:
    """Extract text from a PDF file. Falls back to OCR if no text layer found."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError(
            "pdfplumber is required for PDF extraction. "
            "Install it with: pip install pdfplumber"
        ) from exc

    text_parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    if text_parts:
        result = "\n".join(text_parts)
        logger.debug("pdfplumber extracted %d characters from %s", len(result), path)
        return result

    # Fallback: render pages as images and OCR them
    logger.info("No text layer found in PDF, falling back to OCR")
    return _pdf_ocr_fallback(path)


def _pdf_ocr_fallback(path: Path) -> str:
    """Convert PDF pages to images and run OCR on each."""
    try:
        import pdf2image
        import pytesseract
    except ImportError as exc:
        raise ImportError(
            "pdf2image and pytesseract are required for PDF OCR fallback. "
            "Install them with: pip install pdf2image pytesseract"
        ) from exc

    images = pdf2image.convert_from_path(str(path))
    parts = [pytesseract.image_to_string(img, lang="deu+eng") for img in images]
    result = "\n".join(parts)
    logger.debug("PDF OCR fallback extracted %d characters from %s", len(result), path)
    return result
