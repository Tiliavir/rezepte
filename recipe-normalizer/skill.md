# Skill: recipe-normalizer

A CLI tool that converts recipes from various sources (text, HTML, images, PDFs, or URLs)
into standardised German Markdown files ready for the Hugo-based recipe site.

---

## Usage

```bash
recipe-normalizer <input> [--out <target-folder>] [--provider gemini|openai|rest]
                          [--dry-run] [--log-level DEBUG|INFO|WARNING|ERROR]
```

## Installation

```bash
cd recipe-normalizer
pip install -e .
# With OCR support:
pip install -e ".[ocr]"
```

System dependencies for OCR:

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-deu poppler-utils
```

---

## Architecture

| File                 | Responsibility                              |
| -------------------- | ------------------------------------------- |
| `main.py`            | CLI entry point (typer)                     |
| `input_handler.py`   | Detect input type and load raw text         |
| `html_extractor.py`  | Extract readable text from HTML             |
| `ocr.py`             | OCR for images and PDFs                     |
| `llm_client.py`      | LLM provider abstraction                    |
| `markdown_writer.py` | Parse LLM output and write Markdown files   |
| `slug.py`            | URL-slug generation from recipe titles      |
| `tests.py`           | pytest unit tests                           |
| `pyproject.toml`     | Package metadata and entry point            |

---

## Output Structure

Simple recipe → `content/recipes/<slug>/index.md`

Recipe with components:
```
content/recipes/<slug>/index.md
content/components/<slug-component-1>/index.md
content/components/<slug-component-2>/index.md
```

---

## LLM Providers

| Provider | Authentication |
|----------|---------------|
| `gemini` (default) | `GOOGLE_API_KEY` or `GEMINI_API_KEY` env var |
| `openai` | locally installed `openai` CLI |
| `rest`   | `RECIPE_NORMALIZER_API_URL` + `RECIPE_NORMALIZER_API_KEY` env vars |

---

## File: `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "recipe-normalizer"
version = "0.1.0"
description = "Convert any recipe into a standardised German Markdown file."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = [
    "typer>=0.12",
    "requests>=2.31",
    "PyYAML>=6.0",
    "readability-lxml>=0.8",
    "beautifulsoup4>=4.12",
    "python-slugify>=8.0",
    "google-genai>=1.34",
]

[project.optional-dependencies]
ocr = [
    "pytesseract>=0.3",
    "Pillow>=10",
    "pdfplumber>=0.11",
    "pdf2image>=1.16",
]
all = [
    "recipe-normalizer[ocr]",
]

[project.scripts]
recipe-normalizer = "main:cli"

[tool.setuptools]
py-modules = [
    "main",
    "input_handler",
    "html_extractor",
    "ocr",
    "llm_client",
    "markdown_writer",
    "slug",
]
```

---

## File: `slug.py`

```python
"""Slug generation for recipe titles."""

from slugify import slugify as _slugify


def make_slug(title: str) -> str:
    """Convert a recipe title into a URL-friendly slug."""
    return _slugify(title, allow_unicode=False, separator="-")
```

---

## File: `html_extractor.py`

```python
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
```

---

## File: `ocr.py`

```python
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
```

---

## File: `input_handler.py`

```python
"""Input detection and raw-text extraction for various file/URL types."""

import logging
import urllib.parse
import urllib.request
from pathlib import Path

from html_extractor import extract_text_from_html

logger = logging.getLogger(__name__)

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

    raise ValueError(f"Unsupported input type: {path.suffix!r}")


def _load_url(url: str) -> str:
    """Download a URL and return its main readable text."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Only http/https URLs are supported, got: {parsed.scheme!r}")

    logger.debug("Downloading URL %s", url)
    req = urllib.request.Request(  # NOSONAR python:S5144
        url,
        headers={"User-Agent": "recipe-normalizer/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310  # NOSONAR python:S5144
        content_type = response.headers.get("Content-Type", "")
        raw_bytes = response.read()

    charset = "utf-8"
    if "charset=" in content_type:
        charset = content_type.split("charset=")[-1].split(";")[0].strip()

    html = raw_bytes.decode(charset, errors="replace")
    return extract_text_from_html(html)
```

---

## File: `llm_client.py`

```python
"""LLM client abstraction supporting Gemini, OpenAI and generic REST providers."""

from __future__ import annotations

import json
import importlib.util
import logging
import os
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from typing import Literal

logger = logging.getLogger(__name__)

Provider = Literal["gemini", "openai", "rest"]

SYSTEM_PROMPT = """\
Du bist ein Rezept-Normalisierer.

Aufgabe:
Konvertiere das folgende Rezept in ein deutsches Markdown-Rezept im exakt definierten Format.

Regeln:
1. Sprache immer Deutsch.
2. Alle Einheiten in metrische deutsche Einheiten konvertieren:
   - tbsp → EL
   - tsp → TL
   - cups → je nach Kontext: ml/l oder g/kg
   - ounces → g
   - pounds → g oder kg
   - inches/feet/yards → cm oder m
3. Mengen korrekt umrechnen.
4. Anleitung:
   - präzise
   - kurz
   - aktiv formuliert
   - keine Füllsätze
5. Zutaten NICHT ergänzen.
6. Wenn mehrere klar getrennte Bestandteile existieren (z.B. Sauce, Topping, Teig),
   erstelle separate Rezept-Komponenten.
7. Komponenten werden im Hauptrezept unter "components" per Titel referenziert.
8. Gib ausschließlich gültiges Markdown im vorgegebenen Format zurück.
9. Kein erklärender Text.\
"""


def build_user_prompt(raw_text: str) -> str:
    return raw_text


def _call_gemini(raw_text: str) -> str:
    """Call Google Gemini using API-key authentication."""
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    configured_model = os.environ.get("RECIPE_NORMALIZER_GEMINI_MODEL", "").strip()
    if not api_key:
        raise RuntimeError(
            "Gemini authentication missing. Set GOOGLE_API_KEY (or GEMINI_API_KEY) "
            "and retry, or use --provider openai/rest."
        )

    try:
        from google import genai  # type: ignore[import]
        from google.genai import types  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "Gemini provider requires 'google-genai'. Install with: "
            "pip install -e '.[gemini]'"
        ) from exc

    client = genai.Client(api_key=api_key)
    default_candidates = ["gemini-2.5-pro", "gemini-2.5-flash"]
    if configured_model:
        model_candidates = [configured_model, *default_candidates]
    else:
        model_candidates = default_candidates

    max_retries = max(0, int(os.environ.get("RECIPE_NORMALIZER_GEMINI_RETRIES", "2")))

    def _is_retryable_error(message: str) -> bool:
        lowered = message.lower()
        markers = (
            "429", "too many requests", "rate limit", "resource_exhausted",
            "quota", "temporarily unavailable", "deadline exceeded",
            "timed out", "timeout",
        )
        return any(marker in lowered for marker in markers)

    tried: list[str] = []
    for model_name in model_candidates:
        if model_name in tried:
            continue
        tried.append(model_name)
        for attempt in range(max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=raw_text,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                )
                if not response.text:
                    raise RuntimeError("Gemini returned an empty response.")
                return response.text
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                lowered = message.lower()
                not_found_error = "not found" in lowered or "404" in lowered
                retryable_error = _is_retryable_error(message)
                has_retries_left = attempt < max_retries

                if retryable_error and has_retries_left:
                    sleep_seconds = min(8.0, 1.5 * (2 ** attempt))
                    logger.warning(
                        "Gemini model '%s' transient error; retrying in %.1fs (%d/%d).",
                        model_name, sleep_seconds, attempt + 1, max_retries,
                    )
                    time.sleep(sleep_seconds)
                    continue

                should_try_next_model = (
                    (not_found_error or retryable_error)
                    and model_name != model_candidates[-1]
                )
                if should_try_next_model:
                    logger.warning(
                        "Gemini model '%s' failed (%s); trying fallback model.",
                        model_name, message,
                    )
                    break

                raise RuntimeError(
                    f"Gemini request failed for model(s) {', '.join(tried)}. "
                    f"Original error: {message}"
                ) from exc

    raise RuntimeError("Gemini request failed before a model call was attempted.")


def _is_provider_configured(provider: Provider) -> bool:
    if provider == "gemini":
        has_key = bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))
        has_package = importlib.util.find_spec("google.genai") is not None
        return has_key and has_package
    if provider == "openai":
        return shutil.which("openai") is not None
    if provider == "rest":
        has_url = bool(os.environ.get("RECIPE_NORMALIZER_API_URL", "").strip())
        has_key = bool(os.environ.get("RECIPE_NORMALIZER_API_KEY", "").strip())
        return has_url and has_key
    return False


def get_available_providers() -> list[Provider]:
    order: tuple[Provider, ...] = ("gemini", "openai", "rest")
    return [provider for provider in order if _is_provider_configured(provider)]


def _call_openai(raw_text: str) -> str:
    """Call OpenAI via the locally installed `openai` CLI."""
    openai_exe = shutil.which("openai")
    if openai_exe is None:
        raise RuntimeError("'openai' CLI not found on PATH. Install with: pip install openai")
    payload = json.dumps({
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
    })
    result = subprocess.run(  # noqa: S603  # NOSONAR python:S4721
        [openai_exe, "api", "chat.completions.create", "--json"],
        input=payload,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    return data["choices"][0]["message"]["content"]


def _call_rest(raw_text: str) -> str:
    """Call a generic OpenAI-compatible REST endpoint."""
    base_url = os.environ.get("RECIPE_NORMALIZER_API_URL", "").rstrip("/")
    api_key = os.environ.get("RECIPE_NORMALIZER_API_KEY", "")
    model = os.environ.get("RECIPE_NORMALIZER_MODEL", "gpt-4o")

    if not base_url:
        raise ValueError("RECIPE_NORMALIZER_API_URL must be set for the 'rest' provider.")
    if not api_key:
        raise ValueError("RECIPE_NORMALIZER_API_KEY must be set for the 'rest' provider.")

    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"RECIPE_NORMALIZER_API_URL must use http or https, got: {parsed.scheme!r}")

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
    }).encode("utf-8")

    req = urllib.request.Request(  # NOSONAR python:S5144
        f"{base_url}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"******"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as response:  # noqa: S310  # NOSONAR python:S5144
        data = json.loads(response.read().decode("utf-8"))

    return data["choices"][0]["message"]["content"]


def call_llm(raw_text: str, provider: Provider = "gemini") -> str:
    """Send *raw_text* to the configured LLM provider and return the response."""
    logger.info("Calling LLM provider '%s'", provider)
    if provider not in ("gemini", "openai", "rest"):
        raise ValueError(f"Unknown provider '{provider}'. Choose from: gemini, openai, rest")

    provider_chain: list[Provider] = [provider]
    if provider == "gemini":
        for fallback in ("openai", "rest"):
            if _is_provider_configured(fallback):
                provider_chain.append(fallback)

    last_exception: Exception | None = None
    for index, current_provider in enumerate(provider_chain):
        try:
            if current_provider == "gemini":
                return _call_gemini(raw_text)
            if current_provider == "openai":
                return _call_openai(raw_text)
            return _call_rest(raw_text)
        except Exception as exc:  # noqa: BLE001
            last_exception = exc
            has_next = index < len(provider_chain) - 1
            if has_next:
                logger.warning(
                    "Provider '%s' failed (%s). Falling back to '%s'.",
                    current_provider, exc, provider_chain[index + 1],
                )
                continue
            break

    if last_exception is not None:
        raise last_exception
    raise RuntimeError("LLM call failed before a provider request was attempted.")
```

---

## File: `markdown_writer.py`

```python
"""Parse LLM output and write recipe markdown files to disk."""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import]

from slug import make_slug

logger = logging.getLogger(__name__)

_COMPONENTS_KEY = "components:"

# Regex to capture individual fenced markdown documents (--- ... ---)
_FRONTMATTER_RE = re.compile(
    r"(?:^|\n)---\s*\n(.*?)\n---",  # NOSONAR python:S5852
    re.DOTALL,
)

# Match the title line inside frontmatter
_TITLE_RE = re.compile(r'^title:\s*["\']?(.+?)["\']?\s*$', re.MULTILINE)  # NOSONAR python:S5852

_FRONTMATTER_ORDER = [
    "layout", "date", "title", "authorName", "authorURL", "sourceName", "sourceURL",
    "category", "cuisine", "tags", "yield", "prepTime", "cookTime",
    "ingredients", "directions", "components",
]


def _yaml_scalar(value: str) -> str:
    text = re.sub(r"\s+", " ", value.strip())
    if not text:
        return '""'
    lowered = text.lower()
    reserved = {"null", "~", "true", "false", "yes", "no", "on", "off"}
    needs_quotes = (
        text[0] in "-?:,[]{}#&*!|>'\"%@`"
        or ": " in text
        or " #" in text
        or "\n" in text or "\r" in text
        or lowered in reserved
    )
    if not needs_quotes:
        return text
    return f'"{text.replace(chr(34), chr(92) + chr(34))}"'


def _render_frontmatter(data: dict[str, Any]) -> str:
    lines: list[str] = []
    for key in _FRONTMATTER_ORDER:
        if key not in data:
            continue
        value = data[key]
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"- {_yaml_scalar(str(item))}")
            lines.append("")
            continue
        lines.append(f"{key}: {_yaml_scalar(str(value))}")
        if key in {"date", "title", "sourceURL", "cookTime"}:
            lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _ingredient_to_text(item: Any) -> str | None:
    if isinstance(item, str):
        value = re.sub(r"\s+", " ", item).strip()
        if not value or value == '""':
            return None
        lowered = value.lower()
        if lowered.startswith("item:"):
            return value.split(":", 1)[1].strip() or None
        if lowered.startswith(("quantity:", "unit:", "note:")):
            return None
        return value
    if not isinstance(item, dict):
        return None
    name = str(item.get("item") or item.get("name") or "").strip()
    quantity = item.get("quantity")
    unit = str(item.get("unit") or "").strip()
    note = str(item.get("note") or "").strip()
    amount = ""
    if quantity not in (None, ""):
        amount = f"{str(quantity).strip()} {unit}".strip() if unit else str(quantity).strip()
    elif unit:
        amount = unit
    parts = [p for p in (amount, name) if p]
    if not parts and note:
        return note
    if not parts:
        return None
    text = " ".join(parts)
    return f"{text} ({note})" if note else text


def _direction_to_text(item: Any) -> str | None:
    if isinstance(item, str):
        value = re.sub(r"\s+", " ", item).strip()
        lowered = value.lower()
        if lowered.startswith("step:"):
            value = value.split(":", 1)[1].strip()
        if lowered.startswith("title:"):
            return None
        return value or None
    if isinstance(item, dict):
        for key in ("step", "instruction", "text", "description"):
            value = item.get(key)
            if value:
                return re.sub(r"\s+", " ", str(value)).strip() or None
    return None


def _normalise_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalise_parsed_recipe(parsed: dict[str, Any], iso_date: str) -> tuple[str, str] | None:
    title = str(parsed.get("title") or "").strip()
    if not title:
        return None
    data: dict[str, Any] = {
        "layout": "recipe",
        "date": str(parsed.get("date") or iso_date),
        "title": title,
    }
    for key in ("authorName", "authorURL", "sourceName", "sourceURL",
                "category", "cuisine", "description", "prepTime", "cookTime"):
        value = parsed.get(key)
        if value not in (None, ""):
            data[key] = value
    tags = _normalise_tags(parsed.get("tags"))
    if tags:
        data["tags"] = tags
    raw_yield = parsed.get("yield")
    if isinstance(raw_yield, dict):
        servings = raw_yield.get("servings")
        if servings not in (None, ""):
            data["yield"] = servings
    elif raw_yield not in (None, ""):
        data["yield"] = raw_yield
    raw_ingredients = parsed.get("ingredients", [])
    ingredients = [
        _ingredient_to_text(item)
        for item in (raw_ingredients if isinstance(raw_ingredients, list) else [])
    ]
    ingredients = [i for i in ingredients if i]
    if ingredients:
        data["ingredients"] = ingredients
    raw_directions = parsed.get("directions") or parsed.get("instructions") or parsed.get("steps")
    directions = [
        _direction_to_text(item)
        for item in (raw_directions if isinstance(raw_directions, list) else [])
    ]
    directions = [d for d in directions if d]
    if directions:
        data["directions"] = directions
    raw_components = parsed.get("components")
    if isinstance(raw_components, list):
        components = [str(c).strip() for c in raw_components if str(c).strip()]
        if components:
            data["components"] = components
    if "ingredients" not in data or "directions" not in data:
        return None
    return title, f"---\n{_render_frontmatter(data)}\n---\n"


def _safe_load_frontmatter(frontmatter_body: str) -> dict[str, Any] | None:
    try:
        parsed = yaml.safe_load(frontmatter_body)
        return parsed if isinstance(parsed, dict) else None
    except yaml.YAMLError:
        pass
    # Repair bullet scalars that start with YAML-special characters
    repaired = "\n".join(
        f"{m.group(1)}{_yaml_scalar(m.group(2).strip())}"
        if (m := re.match(r"^(\s*-\s+)(.+)$", line)) and m.group(2).strip()[:1] in "*&!"
        else line
        for line in frontmatter_body.splitlines()
    )
    try:
        parsed = yaml.safe_load(repaired)
        return parsed if isinstance(parsed, dict) else None
    except yaml.YAMLError:
        return None


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).astimezone().isoformat()


def _inject_date(body: str, iso_date: str) -> str:
    if re.search(r"^date:", body, re.MULTILINE):
        return body
    if re.search(r"^layout:", body, re.MULTILINE):
        return re.sub(r"(^layout:.*$)", rf"\1\ndate: {iso_date}", body, count=1, flags=re.MULTILINE)
    return f"date: {iso_date}\n{body}"


def _inject_layout(body: str) -> str:
    if re.search(r"^layout:", body, re.MULTILINE):
        return body
    return f"layout: recipe\n{body}"


def _get_title(body: str) -> str | None:
    match = _TITLE_RE.search(body)
    return match.group(1).strip() if match else None


def _build_frontmatter_from_plain_markdown(llm_response: str, iso_date: str) -> tuple[str, str] | None:
    parsed = _safe_load_frontmatter(llm_response)
    if parsed is not None:
        normalised = _normalise_parsed_recipe(parsed, iso_date)
        if normalised is not None:
            return normalised

    title = next(
        (line.strip()[2:].strip() for line in llm_response.splitlines() if line.strip().startswith("# ")),
        None,
    )
    if not title:
        for line in llm_response.splitlines():
            stripped = line.strip().strip("`")
            if stripped and stripped.lower() != "markdown":
                title = stripped[:120]
                break
    if not title:
        return None

    def _section(names: tuple[str, ...]) -> list[str]:
        lines = llm_response.splitlines()
        start = next((i + 1 for i, l in enumerate(lines)
                      if l.strip().lower().startswith("## ") and l.strip().lower()[3:].strip() in names), None)
        if start is None:
            return []
        end = next((i for i in range(start, len(lines)) if lines[i].strip().startswith("## ")), len(lines))
        return lines[start:end]

    ingredient_lines = _section(("zutaten", "ingredients")) or llm_response.splitlines()
    direction_lines = _section(("zubereitung", "anleitung", "instructions", "directions")) or llm_response.splitlines()

    ingredients = [l.strip()[2:].strip() for l in ingredient_lines
                   if l.strip().startswith(("- ", "* ")) and not l[:1].isspace()]
    directions = []
    for i, l in enumerate(direction_lines):
        m = re.match(r"^\d+\.\s+(.*)$", l.strip())
        if m:
            raw = m.group(1).strip()
            text = re.sub(r"\*\*(.*?)\*\*", r"\1", raw)
            if re.match(r"^\*\*.+\*\*$", raw) and (i + 1 < len(direction_lines)) and direction_lines[i + 1].strip().startswith(("* ", "- ")):
                continue
            directions.append(text)
        elif l.strip().startswith(("- ", "* ")):
            directions.append(l.strip()[2:].strip())

    if not ingredients and not directions:
        return None

    fm = ["layout: recipe", f"date: {iso_date}", "", f"title: {_yaml_scalar(title)}", "", "ingredients:"]
    if not ingredients:
        return None
    fm.extend(f"- {_yaml_scalar(i)}" for i in ingredients)
    fm.append("")
    fm.append("directions:")
    fm.extend(f"- {_yaml_scalar(d)}" for d in directions) if directions else fm.append('- ""')
    return title, f"---\n{chr(10).join(fm)}\n---\n"


def parse_llm_output(llm_response: str) -> list[tuple[str, str]]:
    """Parse LLM output into a list of (title, full_markdown) tuples."""
    iso_date = _now_iso()
    matches = list(_FRONTMATTER_RE.finditer(llm_response))

    if not matches:
        logger.warning("LLM response contained no recognised frontmatter blocks")
        fallback = _build_frontmatter_from_plain_markdown(llm_response, iso_date)
        if fallback is None:
            return []
        logger.info("Parsed plain markdown response into recipe frontmatter")
        return [fallback]

    recipes: list[tuple[str, str]] = []
    for match in matches:
        body = match.group(1)
        normalised = _normalise_parsed_recipe(_safe_load_frontmatter(body) or {}, iso_date) \
            if _safe_load_frontmatter(body) is not None else None
        if normalised is None:
            body = _inject_layout(_inject_date(body, iso_date))
            title = _get_title(body)
            if not title:
                logger.warning("Skipping frontmatter block with no title")
                continue
            recipes.append((title, f"---\n{body}\n---\n"))
        else:
            recipes.append(normalised)
    return recipes


def write_recipes(
    recipes: list[tuple[str, str]],
    output_dir: Path,
    *,
    dry_run: bool = False,
) -> list[Path]:
    """Write recipe markdown files to *output_dir*."""
    if not recipes:
        logger.error("No recipes to write")
        return []

    main_recipes = [(t, m) for t, m in recipes if _COMPONENTS_KEY in m]
    components = [(t, m) for t, m in recipes if _COMPONENTS_KEY not in m]

    if not main_recipes and len(components) == 1:
        main_recipes, components = components, []

    written: list[Path] = []
    for title, markdown in main_recipes:
        dest = output_dir / "recipes" / make_slug(title) / "index.md"
        _write_file(dest, markdown, dry_run=dry_run)
        written.append(dest)
    for title, markdown in components:
        dest = output_dir / "components" / make_slug(title) / "index.md"
        _write_file(dest, markdown, dry_run=dry_run)
        written.append(dest)
    return written


def _write_file(path: Path, content: str, *, dry_run: bool) -> None:
    if dry_run:
        sys.stdout.write(f"\n# === {path} ===\n{content}\n")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    logger.info("Written: %s", path)
```

---

## File: `main.py`

```python
"""recipe-normalizer – convert any recipe into a standardised German Markdown file."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="recipe-normalizer",
    help="Convert any recipe (text, HTML, image, PDF or URL) "
         "into a standardised German Markdown file.",
    add_completion=False,
)


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        format="%(levelname)s: %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        stream=sys.stderr,
    )


def _load_env_file() -> None:
    """Load environment variables from a local .env file if present."""
    env_path = Path.cwd() / ".env"
    if not env_path.exists() or not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


@app.command()
def main(
    source: str = typer.Argument(..., help="Input: file path or HTTP/HTTPS URL.", metavar="INPUT"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Target content folder.", show_default=False),
    provider: str = typer.Option("gemini", "--provider", "-p", help="LLM provider: gemini|openai|rest."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print to stdout instead of writing files."),
    log_level: str = typer.Option("INFO", "--log-level", help="DEBUG|INFO|WARNING|ERROR."),
) -> None:
    """Convert *INPUT* into standardised German Markdown recipe files."""
    _load_env_file()
    _setup_logging(log_level)
    logger = logging.getLogger(__name__)

    valid_providers = ("gemini", "openai", "rest")
    if provider not in valid_providers:
        typer.echo(f"Error: unknown provider '{provider}'. Choose from: {', '.join(valid_providers)}", err=True)
        raise typer.Exit(code=1)

    if out is None:
        out = Path.cwd() / "content"

    from input_handler import load_raw_text
    try:
        logger.info("Loading input: %s", source)
        raw_text = load_raw_text(source)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Error loading input: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not raw_text.strip():
        typer.echo("Error: input produced empty text.", err=True)
        raise typer.Exit(code=1)

    from llm_client import call_llm
    try:
        logger.info("Sending to LLM provider '%s'…", provider)
        llm_response = call_llm(raw_text, provider=provider)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Error calling LLM: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not llm_response.strip():
        typer.echo("Error: LLM returned an empty response.", err=True)
        raise typer.Exit(code=1)

    from markdown_writer import parse_llm_output, write_recipes
    recipes = parse_llm_output(llm_response)
    if not recipes:
        typer.echo("Error: could not parse any recipe. Try --log-level DEBUG.", err=True)
        raise typer.Exit(code=1)

    written = write_recipes(recipes, out, dry_run=dry_run)
    if not dry_run:
        for path in written:
            typer.echo(str(path))


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()
```

---

## File: `tests.py`

```python
"""Unit tests for recipe-normalizer core modules."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import pytest
from pathlib import Path

from slug import make_slug
from markdown_writer import parse_llm_output, write_recipes
from input_handler import is_url, load_raw_text
from llm_client import call_llm, get_available_providers


def test_make_slug_basic():
    assert make_slug("Hiyashi Tantan Udon") == "hiyashi-tantan-udon"


def test_make_slug_german_chars():
    assert make_slug("Käse-Spätzle mit Öl") == "kase-spatzle-mit-ol"


def test_make_slug_special_chars():
    assert make_slug("  Foo & Bar! ") == "foo-bar"


def test_is_url_https():
    assert is_url("https://example.com/recipe") is True


def test_is_url_http():
    assert is_url("http://example.com/recipe") is True  # NOSONAR python:S5332


def test_is_url_file_path():
    assert is_url("/home/user/recipe.txt") is False


def test_is_url_relative_path():
    assert is_url("recipe.txt") is False


def test_load_raw_text_txt(tmp_path):
    f = tmp_path / "recipe.txt"
    f.write_text("Zutaten:\n- 100g Mehl\n", encoding="utf-8")
    assert "Mehl" in load_raw_text(str(f))


def test_load_raw_text_md(tmp_path):
    f = tmp_path / "recipe.md"
    f.write_text("# Rezept\n- 200g Zucker\n", encoding="utf-8")
    assert "Zucker" in load_raw_text(str(f))


def test_load_raw_text_missing_file():
    with pytest.raises(FileNotFoundError):
        load_raw_text("/nonexistent/file.txt")


def test_load_raw_text_unsupported_extension(tmp_path):
    f = tmp_path / "recipe.xyz"
    f.write_text("data", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported input type"):
        load_raw_text(str(f))


def test_load_raw_text_html(tmp_path):
    f = tmp_path / "recipe.html"
    f.write_text("<html><body><p>Spaghetti Bolognese</p></body></html>", encoding="utf-8")
    assert "Spaghetti" in load_raw_text(str(f))


SIMPLE_LLM_RESPONSE = """\
---
layout: recipe
title: "Pasta al Pomodoro"
ingredients:
  - 200g Nudeln
  - 100ml Tomatensauce
directions:
  - Nudeln kochen
  - Sauce erhitzen und vermischen
---
"""

COMPONENT_LLM_RESPONSE = """\
---
layout: recipe
title: "Tomatensauce"
ingredients:
  - 400g Tomaten
  - 1 Zwiebel
directions:
  - Zwiebel andünsten
  - Tomaten hinzufügen und köcheln lassen
---

---
layout: recipe
title: "Pasta al Pomodoro"
components:
  - "Tomatensauce"
directions:
  - Nudeln kochen
  - Mit Tomatensauce servieren
---
"""

PLAIN_MARKDOWN_RESPONSE = """\
# Spaghetti Carbonara

## Zutaten
- 340 g Spaghetti
- 170 g Guanciale

## Zubereitung
1. Nudeln kochen
2. Guanciale anbraten
"""


def test_parse_simple_recipe():
    recipes = parse_llm_output(SIMPLE_LLM_RESPONSE)
    assert len(recipes) == 1
    title, md = recipes[0]
    assert title == "Pasta al Pomodoro"
    assert "layout: recipe" in md
    assert "date:" in md


def test_parse_component_recipe():
    recipes = parse_llm_output(COMPONENT_LLM_RESPONSE)
    assert len(recipes) == 2
    titles = [t for t, _ in recipes]
    assert "Tomatensauce" in titles
    assert "Pasta al Pomodoro" in titles


def test_parse_empty_response():
    assert parse_llm_output("") == []


def test_parse_no_frontmatter():
    assert parse_llm_output("Just some plain text without frontmatter.") == []


def test_parse_plain_markdown_recipe():
    recipes = parse_llm_output(PLAIN_MARKDOWN_RESPONSE)
    assert len(recipes) == 1
    title, md = recipes[0]
    assert title == "Spaghetti Carbonara"
    assert "layout: recipe" in md
    assert "ingredients:" in md
    assert "directions:" in md


def test_write_simple_recipe(tmp_path):
    recipes = parse_llm_output(SIMPLE_LLM_RESPONSE)
    written = write_recipes(recipes, tmp_path)
    assert len(written) == 1
    assert written[0] == tmp_path / "recipes" / "pasta-al-pomodoro" / "index.md"
    assert "Pasta al Pomodoro" in written[0].read_text(encoding="utf-8")


def test_write_component_recipe(tmp_path):
    recipes = parse_llm_output(COMPONENT_LLM_RESPONSE)
    written = write_recipes(recipes, tmp_path)
    assert len(written) == 2
    paths = {str(p) for p in written}
    assert str(tmp_path / "recipes" / "pasta-al-pomodoro" / "index.md") in paths
    assert str(tmp_path / "components" / "tomatensauce" / "index.md") in paths


def test_write_dry_run(tmp_path, capsys):
    recipes = parse_llm_output(SIMPLE_LLM_RESPONSE)
    write_recipes(recipes, tmp_path, dry_run=True)
    captured = capsys.readouterr()
    assert "Pasta al Pomodoro" in captured.out
    assert not (tmp_path / "recipes").exists()


def test_write_creates_parent_dirs(tmp_path):
    recipes = parse_llm_output(SIMPLE_LLM_RESPONSE)
    written = write_recipes(recipes, tmp_path / "a" / "b" / "c")
    assert written[0].exists()


def test_get_available_providers(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("RECIPE_NORMALIZER_API_URL", raising=False)
    monkeypatch.delenv("RECIPE_NORMALIZER_API_KEY", raising=False)
    monkeypatch.setattr("llm_client.importlib.util.find_spec", lambda _name: None)
    monkeypatch.setattr("llm_client.shutil.which", lambda _name: None)
    assert get_available_providers() == []

    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr("llm_client.importlib.util.find_spec", lambda _name: object())
    monkeypatch.setattr("llm_client.shutil.which", lambda _name: "/usr/bin/openai")
    monkeypatch.setenv("RECIPE_NORMALIZER_API_URL", "https://example.com/v1")
    monkeypatch.setenv("RECIPE_NORMALIZER_API_KEY", "test-rest-key")
    assert get_available_providers() == ["gemini", "openai", "rest"]


def test_call_llm_falls_back_from_gemini_to_openai(monkeypatch):
    monkeypatch.setattr("llm_client._is_provider_configured", lambda p: p == "openai")
    monkeypatch.setattr("llm_client._call_gemini", lambda _: (_ for _ in ()).throw(RuntimeError("Gemini auth missing")))
    monkeypatch.setattr("llm_client._call_openai", lambda _: "ok")
    assert call_llm("Zutaten", provider="gemini") == "ok"
```

---

## `.gitignore` additions

```
__pycache__/
*.egg-info/
.pytest_cache/
```
