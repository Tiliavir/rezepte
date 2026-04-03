"""Unit tests for recipe-normalizer core modules."""

import sys
import os

# Add the recipe-normalizer directory to the path so we can import modules directly
sys.path.insert(0, os.path.dirname(__file__))

import pytest
import tempfile
from pathlib import Path

from slug import make_slug
from markdown_writer import parse_llm_output, write_recipes
from input_handler import is_url, load_raw_text
from llm_client import call_llm, get_available_providers


# ---------------------------------------------------------------------------
# slug tests
# ---------------------------------------------------------------------------

def test_make_slug_basic():
    assert make_slug("Hiyashi Tantan Udon") == "hiyashi-tantan-udon"


def test_make_slug_german_chars():
    slug = make_slug("Käse-Spätzle mit Öl")
    assert slug == "kase-spatzle-mit-ol"


def test_make_slug_special_chars():
    assert make_slug("  Foo & Bar! ") == "foo-bar"


# ---------------------------------------------------------------------------
# is_url tests
# ---------------------------------------------------------------------------

def test_is_url_https():
    assert is_url("https://example.com/recipe") is True


def test_is_url_http():
    assert is_url("http://example.com/recipe") is True  # NOSONAR python:S5332


def test_is_url_file_path():
    assert is_url("/home/user/recipe.txt") is False


def test_is_url_relative_path():
    assert is_url("recipe.txt") is False


# ---------------------------------------------------------------------------
# load_raw_text tests (file-based, no network)
# ---------------------------------------------------------------------------

def test_load_raw_text_txt(tmp_path):
    f = tmp_path / "recipe.txt"
    f.write_text("Zutaten:\n- 100g Mehl\n", encoding="utf-8")
    text = load_raw_text(str(f))
    assert "Mehl" in text


def test_load_raw_text_md(tmp_path):
    f = tmp_path / "recipe.md"
    f.write_text("# Rezept\n- 200g Zucker\n", encoding="utf-8")
    text = load_raw_text(str(f))
    assert "Zucker" in text


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
    f.write_text(
        "<html><body><p>Spaghetti Bolognese</p></body></html>",
        encoding="utf-8",
    )
    text = load_raw_text(str(f))
    assert "Spaghetti" in text


# ---------------------------------------------------------------------------
# parse_llm_output tests
# ---------------------------------------------------------------------------

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

PLAIN_MARKDOWN_ODD_HEADINGS = """\
# Kartoffelgericht

## Einkauf
- 500 g Kartoffeln
- Salz

## Schritte
1. Kartoffeln schälen
2. Kartoffeln kochen
"""

NESTED_FRONTMATTER_RESPONSE = """\
---
layout: recipe
title: Spaghetti Carbonara (Klassisch Römisch)
yield:
    servings: 4
ingredients:
    - item: Spaghetti
        quantity: 340
        unit: g
    - item: Guanciale
        quantity: 170
        unit: g
instructions:
    - Nudeln kochen
    - Guanciale anbraten
---
"""

YAML_LIKE_PLAIN_RESPONSE = """\
title: Amerikanische Pizza
yield:
    servings: 3
ingredients:
    - item: Mehl
        quantity: 500
        unit: g
directions:
    - title: Pizzateig
    - step: Teig kneten
    - step: Pizza backen
"""


def test_parse_simple_recipe():
    recipes = parse_llm_output(SIMPLE_LLM_RESPONSE)
    assert len(recipes) == 1
    title, md = recipes[0]
    assert title == "Pasta al Pomodoro"
    assert "layout: recipe" in md
    assert "date:" in md  # date was injected


def test_parse_component_recipe():
    recipes = parse_llm_output(COMPONENT_LLM_RESPONSE)
    assert len(recipes) == 2
    titles = [t for t, _ in recipes]
    assert "Tomatensauce" in titles
    assert "Pasta al Pomodoro" in titles


def test_parse_empty_response():
    recipes = parse_llm_output("")
    assert recipes == []


def test_parse_no_frontmatter():
    recipes = parse_llm_output("Just some plain text without frontmatter.")
    assert recipes == []


def test_parse_plain_markdown_recipe():
    recipes = parse_llm_output(PLAIN_MARKDOWN_RESPONSE)
    assert len(recipes) == 1
    title, md = recipes[0]
    assert title == "Spaghetti Carbonara"
    assert "layout: recipe" in md
    assert "ingredients:" in md
    assert "directions:" in md
    assert "layout: recipe\\ndate:" not in md
    assert "title: Spaghetti Carbonara" in md
    assert "- 340 g Spaghetti" in md


def test_parse_plain_markdown_with_odd_headings():
    recipes = parse_llm_output(PLAIN_MARKDOWN_ODD_HEADINGS)
    assert len(recipes) == 1
    title, md = recipes[0]
    assert title == "Kartoffelgericht"
    assert "ingredients:" in md
    assert "directions:" in md


def test_parse_plain_markdown_extracts_yield():
    response = """\
# Tomatensuppe

## Portionen
- Portionen: 4

## Zutaten
- 1kg Tomaten

## Zubereitung
1. Kochen
"""
    recipes = parse_llm_output(response)
    assert len(recipes) == 1
    _, md = recipes[0]
    assert "yield: 4" in md


def test_parse_nested_frontmatter_normalises_schema():
    recipes = parse_llm_output(NESTED_FRONTMATTER_RESPONSE)
    assert len(recipes) == 1
    title, md = recipes[0]
    assert title == "Spaghetti Carbonara (Klassisch Römisch)"
    assert "yield: 4" in md
    assert "instructions:" not in md
    assert "directions:" in md
    assert "- 340 g Spaghetti" in md
    assert "- 170 g Guanciale" in md


def test_parse_frontmatter_with_asterisk_bullet_does_not_crash():
        response = """\
---
layout: recipe
title: Carbonara
ingredients:
    - 340 g Spaghetti
directions:
    - **Textur-Leitfaden:**
    - Bei Bedarf Wasser zugeben
---
"""
        recipes = parse_llm_output(response)
        assert len(recipes) == 1
        _, md = recipes[0]
        assert "title: Carbonara" in md
        assert "directions:" in md


    def test_parse_yaml_like_plain_response_normalises_schema():
        recipes = parse_llm_output(YAML_LIKE_PLAIN_RESPONSE)
        assert len(recipes) == 1
        title, md = recipes[0]
        assert title == "Amerikanische Pizza"
        assert "yield: 3" in md
        assert "- 500 g Mehl" in md
        assert "- Teig kneten" in md
        assert "title: Pizzateig" not in md
        assert "step:" not in md


# ---------------------------------------------------------------------------
# write_recipes tests
# ---------------------------------------------------------------------------

def test_write_simple_recipe(tmp_path):
    recipes = parse_llm_output(SIMPLE_LLM_RESPONSE)
    written = write_recipes(recipes, tmp_path)
    assert len(written) == 1
    assert written[0] == tmp_path / "recipes" / "pasta-al-pomodoro" / "index.md"
    content = written[0].read_text(encoding="utf-8")
    assert "Pasta al Pomodoro" in content


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
    # No files should actually be written
    assert not (tmp_path / "recipes").exists()


def test_write_creates_parent_dirs(tmp_path):
    recipes = parse_llm_output(SIMPLE_LLM_RESPONSE)
    deep_dir = tmp_path / "a" / "b" / "c"
    written = write_recipes(recipes, deep_dir)
    assert written[0].exists()


# ---------------------------------------------------------------------------
# LLM provider selection tests (no network)
# ---------------------------------------------------------------------------


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
    def configured(provider: str) -> bool:
        return provider == "openai"

    monkeypatch.setattr("llm_client._is_provider_configured", configured)

    def fail_gemini(_raw_text: str) -> str:
        raise RuntimeError("Gemini auth missing")

    monkeypatch.setattr("llm_client._call_gemini", fail_gemini)
    monkeypatch.setattr("llm_client._call_openai", lambda _raw_text: "ok")

    assert call_llm("Zutaten", provider="gemini") == "ok"
