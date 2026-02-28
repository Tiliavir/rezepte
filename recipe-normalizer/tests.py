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
