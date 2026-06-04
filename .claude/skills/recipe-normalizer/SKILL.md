# Skill: recipe-normalizer

Build a CLI tool that converts recipes from any source into standardised German Markdown files
for the Hugo-based recipe site in this repository.

---

## Goal

Accept a recipe as **text, Markdown, HTML, URL, image, or PDF**, extract the recipe text,
send it to an LLM with the prompt below, and write the result as YAML front-matter Markdown
under `content/recipes/`.

All normalisation (language, units, structure) is delegated to the LLM — no custom NLP or
unit-conversion engine is needed.

---

## Supported Inputs

| Input | How to handle |
|-------|---------------|
| `.txt`, `.md` | read directly |
| `.html` | extract main article text (e.g. readability) |
| `https://…` URL | download HTML, then extract |
| `.jpg`, `.png` | OCR |
| `.pdf` | extract text; OCR as fallback |

---

## CLI

```
recipe-normalizer <INPUT> [--out <folder>] [--provider gemini|openai|rest] [--dry-run] [--log-level DEBUG|INFO|WARNING|ERROR]
```

| Argument | Required | Default | Notes |
|----------|----------|---------|-------|
| `INPUT` | ✅ | — | file path or `https://` URL |
| `--out` | ❌ | `./content` | Hugo content root |
| `--provider` | ❌ | `gemini` | LLM backend; fall back to next if unavailable |
| `--dry-run` | ❌ | false | print to stdout, write nothing |
| `--log-level` | ❌ | `INFO` | verbosity |

---

## LLM Providers

Support at least one; make them interchangeable:

- **Gemini** — `GOOGLE_API_KEY` or `GEMINI_API_KEY` env var
- **OpenAI** — locally installed `openai` CLI, no key in code
- **Generic REST** — `RECIPE_NORMALIZER_API_URL` + `RECIPE_NORMALIZER_API_KEY` env vars

---

## LLM System Prompt (use verbatim)

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

## Output Format

### Simple recipe

Path: `content/recipes/<slug>/index.md`

```yaml
---
layout: recipe
date: 2024-01-15T10:30:00Z
title: "Schokoladenkuchen"
category: Kuchen          # optional
cuisine: Deutsch          # optional
tags:                     # optional
  - Backen
  - Schokolade
yield: 12                 # optional – number of servings
prepTime: 20              # optional – minutes
cookTime: 45              # optional – minutes
ingredients:
  - 200g Mehl
  - 150g Zucker
  - 3 Eier
  - 100g Butter
  - 2 EL Kakao
directions:
  - Ofen auf 180°C vorheizen.
  - Mehl, Zucker und Kakao mischen.
  - Eier und geschmolzene Butter unterrühren.
  - 45 Minuten backen.
---
```

### Component recipe

Use when a recipe has clearly separate parts (sauce, dough, topping, etc.).

**Component** → `content/recipes/<slug-component>/index.md`

```yaml
---
layout: recipe
date: 2024-01-15T10:30:00Z
title: "Tomatensauce"
ingredients:
  - 400g Tomaten (gehackt)
  - 1 Zwiebel
  - 2 EL Olivenöl
  - Salz, Pfeffer
directions:
  - Zwiebel in Öl anschwitzen.
  - Tomaten dazugeben, 20 Minuten köcheln.
---
```

**Main recipe** → `content/recipes/<slug>/index.md`

```yaml
---
layout: recipe
date: 2024-01-15T10:30:00Z
title: "Pasta mit Tomatensauce"
components:
  - "Tomatensauce"
directions:
  - Pasta nach Packungsanleitung kochen.
  - Mit Tomatensauce servieren.
---
```

---

## Constraints

- No hardcoded API keys.
- Slugs must be URL-safe and derived from the recipe title.
- Dates in ISO 8601 format.
- UTF-8 encoding for all output files.
- Handle errors gracefully: invalid input, LLM failure, empty response.
