# recipe-normalizer

A command-line tool that converts recipes from various sources (text, HTML,
images, PDFs, or URLs) into standardised German Markdown files ready to be
used with the Hugo-based recipe site.

---

## Installation

```bash
cd recipe-normalizer
pip install -e .
# With OCR support:
pip install -e ".[ocr]"
# All extras:
pip install -e ".[all]"
```

System dependencies for OCR:

```bash
# Debian/Ubuntu
sudo apt-get install tesseract-ocr tesseract-ocr-deu poppler-utils
```

---

## Usage

```bash
recipe-normalizer <input> [--out <target-folder>] [--provider gemini|openai|rest]
                          [--dry-run] [--log-level DEBUG|INFO|WARNING|ERROR]
```

### Examples

```bash
# Plain text file
recipe-normalizer recipe.txt

# HTML file
recipe-normalizer recipe.html

# Image (requires OCR extras)
recipe-normalizer scan.jpg

# PDF (requires OCR extras)
recipe-normalizer recipe.pdf

# URL
recipe-normalizer https://example.com/recipe

# Write to custom folder
recipe-normalizer recipe.txt --out /path/to/hugo-site/content

# Only print output without writing files
recipe-normalizer recipe.txt --dry-run

# Use OpenAI instead of Gemini
recipe-normalizer recipe.txt --provider openai

# Verbose output
recipe-normalizer recipe.txt --log-level DEBUG
```

---

## Supported Input Formats

| Format         | Processing                        |
| -------------- | --------------------------------- |
| `.txt` / `.md` | read directly                     |
| `.html`        | extract readable text             |
| URL            | download HTML → extract text      |
| `.jpg` / `.png`| OCR via Tesseract                 |
| `.pdf`         | extract text or OCR fallback      |

---

## LLM Providers

### Gemini (default)

Uses API-key auth via `GOOGLE_API_KEY` (or `GEMINI_API_KEY`).
Default model is `gemini-2.5-pro` with fallback to `gemini-2.5-flash`.
You can override it with `RECIPE_NORMALIZER_GEMINI_MODEL`.
Transient API errors (including 429/rate-limit) are retried automatically,
then the CLI falls back to the next Gemini model.
If Gemini is unavailable, the CLI automatically falls back to `openai`, then `rest`
when those providers are configured.

```bash
export GOOGLE_API_KEY=your_api_key_here
export RECIPE_NORMALIZER_GEMINI_MODEL=gemini-2.5-pro  # optional
recipe-normalizer recipe.txt --provider gemini
```

You can also create a local `.env` file in `recipe-normalizer/`:

```bash
GOOGLE_API_KEY=your_api_key_here
RECIPE_NORMALIZER_GEMINI_MODEL=gemini-2.5-pro
RECIPE_NORMALIZER_GEMINI_RETRIES=2
```

The CLI loads this file automatically.

### OpenAI

Uses the locally installed `openai` CLI with existing login.

```bash
recipe-normalizer recipe.txt --provider openai
```

### Generic REST (OpenAI-compatible)

Set environment variables:

```bash
export RECIPE_NORMALIZER_API_URL=https://api.openai.com/v1
export RECIPE_NORMALIZER_API_KEY=sk-...
export RECIPE_NORMALIZER_MODEL=gpt-4o   # optional, default: gpt-4o

recipe-normalizer recipe.txt --provider rest
```

---

## Output Structure

Simple recipe:

```
content/recipes/<slug>/index.md
```

Recipe with components:

```
content/recipes/<slug>/index.md
content/components/<slug-component-1>/index.md
content/components/<slug-component-2>/index.md
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
