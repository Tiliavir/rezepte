# Skill: recipe-normalizer

Implement the `recipe-normalizer` Python CLI tool under `recipe-normalizer/` in this repository.
The tool converts recipes from arbitrary sources into standardised German Markdown files
compatible with the Hugo-based recipe site in this repo.

---

## Goal

Create a Python 3.11+ CLI that:

1. Accepts a recipe as text, HTML, image, PDF, or URL
2. Extracts plain text (OCR when needed)
3. Sends the text to an LLM to normalise it into German Markdown
4. Writes the result as YAML front-matter Markdown files under `content/`

No custom NLP, no unit-conversion engine, no GUI — all semantic transformation is done by the LLM.

---

## Directory Layout to Create

Place all files inside `recipe-normalizer/`:

```
recipe-normalizer/
  pyproject.toml       # package metadata and entry-point
  slug.py              # URL slug generation
  html_extractor.py    # HTML → plain text
  ocr.py               # OCR for images and PDFs
  input_handler.py     # detect input type, return raw text
  llm_client.py        # LLM provider abstraction
  markdown_writer.py   # parse LLM output, write .md files
  main.py              # typer CLI entry-point
  tests.py             # pytest unit tests
```

Copy each file from this skill directory verbatim — they are production-ready:

| File | Reference |
|------|-----------|
| `pyproject.toml` | [pyproject.toml](pyproject.toml) |
| `slug.py` | [slug.py](slug.py) |
| `html_extractor.py` | [html_extractor.py](html_extractor.py) |
| `ocr.py` | [ocr.py](ocr.py) |
| `input_handler.py` | [input_handler.py](input_handler.py) |
| `llm_client.py` | [llm_client.py](llm_client.py) |
| `markdown_writer.py` | [markdown_writer.py](markdown_writer.py) |
| `main.py` | [main.py](main.py) |
| `tests.py` | [tests.py](tests.py) |

---

## Output Format

### Simple recipe → `content/recipes/<slug>/index.md`

```yaml
---
layout: recipe
date: <ISO-8601 timestamp>
title: "Titel"
category: <optional>
cuisine: <optional>
tags:
  - tag
yield: 4
prepTime: 10
cookTime: 30
ingredients:
  - 200g Mehl
  - 2 EL Zucker
directions:
  - Mehl sieben.
  - Teig kneten.
---
```

### Component recipe

Components are placed in `content/components/<slug>/index.md`.
The main recipe references them by title:

```yaml
---
layout: recipe
date: <ISO-8601 timestamp>
title: "Hauptrezept"
components:
  - "Tomatensauce"
  - "Basilikum-Pesto"
directions:
  - Komponenten zubereiten und kombinieren.
---
```

---

## LLM System Prompt (fixed — do not modify)

```
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
9. Kein erklärender Text.
```

---

## CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `INPUT` | (required) | file path (`.txt .md .html .jpg .png .pdf`) or `https://` URL |
| `--out PATH` | `./content` | target Hugo content directory |
| `--provider` | `gemini` | LLM backend: `gemini` \| `openai` \| `rest` |
| `--dry-run` | false | print Markdown to stdout, do not write files |
| `--log-level` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |

---

## LLM Providers

### Gemini (default)

Requires `GOOGLE_API_KEY` or `GEMINI_API_KEY` environment variable.
Optional env overrides: `RECIPE_NORMALIZER_GEMINI_MODEL`, `RECIPE_NORMALIZER_GEMINI_RETRIES`.
API key source: <https://aistudio.google.com/api-keys>

### OpenAI

Uses the locally installed `openai` CLI binary (resolved via `shutil.which`).
No API key in code.

### Generic REST (OpenAI-compatible)

Requires `RECIPE_NORMALIZER_API_URL` and `RECIPE_NORMALIZER_API_KEY`.
Optional: `RECIPE_NORMALIZER_MODEL` (default `gpt-4o`).

### Provider fallback

When `--provider gemini` is specified and Gemini fails, the client automatically falls back
to `openai` then `rest` if those are configured.

---

## `.gitignore` additions required

Add to the root `.gitignore`:

```
__pycache__/
*.egg-info/
.pytest_cache/
```

---

## Security requirements

- No hardcoded API keys.
- Validate URL scheme (`http`/`https` only) before any `urlopen` call.
- Resolve subprocess executables with `shutil.which` — never pass a bare binary name.
- Mark intentional SonarCloud false-positives with `# NOSONAR <rule-id>` on the flagged line.

---

## Tests

Run with pytest from inside the skill directory:

```
pip install -e ".[all]"
pytest tests.py -v
```

All 20 tests should pass without network access.
