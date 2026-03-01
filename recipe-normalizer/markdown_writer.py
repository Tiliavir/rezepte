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
    "layout",
    "date",
    "title",
    "authorName",
    "authorURL",
    "sourceName",
    "sourceURL",
    "category",
    "cuisine",
    "tags",
    "yield",
    "prepTime",
    "cookTime",
    "ingredients",
    "directions",
    "components",
]


def _yaml_scalar(value: str) -> str:
    """Render a string as YAML scalar, preferring plain style like existing recipes."""
    text = re.sub(r"\s+", " ", value.strip())
    if not text:
        return '""'

    lowered = text.lower()
    reserved = {"null", "~", "true", "false", "yes", "no", "on", "off"}
    starts_with_special = text[0] in "-?:,[]{}#&*!|>'\"%@`"
    has_colon_space = ": " in text
    has_hash_space = " #" in text
    has_newline = "\n" in text or "\r" in text

    needs_quotes = (
        starts_with_special
        or has_colon_space
        or has_hash_space
        or has_newline
        or lowered in reserved
    )

    if not needs_quotes:
        return text

    escaped = text.replace('"', '\\"')
    return f'"{escaped}"'


def _parse_title_from_markdown(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def _first_non_empty_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip().strip("`")
        if stripped and stripped.lower() != "markdown":
            return stripped
    return None


def _is_h2_heading(line: str, names: tuple[str, ...]) -> bool:
    stripped = line.strip().lower()
    if not stripped.startswith("## "):
        return False
    heading = stripped[3:].strip()
    return heading in names


def _extract_section_lines(text: str, names: tuple[str, ...]) -> list[str]:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if _is_h2_heading(line, names):
            start = index + 1
            break

    if start is None:
        return []

    end = len(lines)
    for index in range(start, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("## "):
            end = index
            break

    return lines[start:end]


def _extract_bullet_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        # Ingredients should be top-level bullets only; nested bullets are often notes.
        if line[:1].isspace():
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("- ", "* ")):
            items.append(stripped[2:].strip())
    return items


def _extract_direction_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        ordered_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ordered_match:
            raw_step = ordered_match.group(1).strip()
            text = re.sub(r"\*\*(.*?)\*\*", r"\1", raw_step)
            next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
            is_section_heading = bool(re.match(r"^\*\*.+\*\*$", raw_step))
            if is_section_heading and next_line.startswith(("* ", "- ")):
                continue
            items.append(text)
            continue

        if stripped.startswith(("- ", "* ")):
            items.append(stripped[2:].strip())

    return items


def _extract_yield_value(text: str) -> str | None:
    patterns = (
        r"(?im)^\s*[-*]\s*(?:portionen|serves?|yield)\s*:\s*(.+)$",
        r"(?im)^\s*(?:portionen|serves?|yield)\s*:\s*(.+)$",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _ingredient_to_text(item: Any) -> str | None:
    if isinstance(item, str):
        value = re.sub(r"\s+", " ", item).strip()
        lowered = value.lower()
        if not value or value == '""':
            return None
        if lowered.startswith("item:"):
            value = value.split(":", 1)[1].strip()
            return value or None
        if lowered.startswith(("quantity:", "unit:", "note:")):
            return None
        return value or None
    if not isinstance(item, dict):
        return None

    name = str(item.get("item") or item.get("name") or "").strip()
    quantity = item.get("quantity")
    unit = str(item.get("unit") or "").strip()
    note = str(item.get("note") or "").strip()

    amount = ""
    if quantity not in (None, ""):
        amount = str(quantity).strip()
        if unit:
            amount = f"{amount} {unit}".strip()
    elif unit:
        amount = unit

    parts = [part for part in (amount, name) if part]
    if not parts and note:
        return note
    if not parts:
        return None

    text = " ".join(parts)
    if note:
        text = f"{text} ({note})"
    return text


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

    for key in (
        "authorName",
        "authorURL",
        "sourceName",
        "sourceURL",
        "category",
        "cuisine",
        "description",
        "prepTime",
        "cookTime",
    ):
        value = parsed.get(key)
        if value not in (None, ""):
            data[key] = value

    tags = _normalise_tags(parsed.get("tags"))
    if tags:
        data["tags"] = tags

    raw_yield = parsed.get("yield")
    if isinstance(raw_yield, dict):
        servings = raw_yield.get("servings")
        time_value = raw_yield.get("time")
        if servings not in (None, ""):
            data["yield"] = servings
        if "prepTime" not in data and time_value not in (None, ""):
            data["prepTime"] = time_value
    elif raw_yield not in (None, ""):
        data["yield"] = raw_yield

    raw_ingredients = parsed.get("ingredients", [])
    ingredients: list[str] = []
    if isinstance(raw_ingredients, list):
        for item in raw_ingredients:
            converted = _ingredient_to_text(item)
            if converted:
                ingredients.append(converted)
    if ingredients:
        data["ingredients"] = ingredients

    raw_directions = parsed.get("directions")
    if raw_directions is None:
        raw_directions = parsed.get("instructions")
    if raw_directions is None:
        raw_directions = parsed.get("steps")
    directions: list[str] = []
    if isinstance(raw_directions, list):
        for item in raw_directions:
            converted = _direction_to_text(item)
            if converted:
                directions.append(converted)
    if directions:
        data["directions"] = directions

    raw_components = parsed.get("components")
    components: list[str] = []
    if isinstance(raw_components, list):
        components = [str(item).strip() for item in raw_components if str(item).strip()]
    if components:
        data["components"] = components

    if "ingredients" not in data or "directions" not in data:
        return None

    normalised_body = _render_frontmatter(data)
    full_md = f"---\n{normalised_body}\n---\n"
    return title, full_md


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


def _sanitize_frontmatter_for_yaml(frontmatter_body: str) -> str:
    """Repair common YAML-invalid list scalars emitted by LLMs before parsing."""
    repaired: list[str] = []
    for line in frontmatter_body.splitlines():
        match = re.match(r"^(\s*-\s+)(.+)$", line)
        if not match:
            repaired.append(line)
            continue

        prefix, scalar = match.groups()
        value = scalar.strip()
        if value.startswith(("*", "&", "!")):
            repaired.append(f"{prefix}{_yaml_scalar(value)}")
            continue
        repaired.append(line)
    return "\n".join(repaired)


def _safe_load_frontmatter(frontmatter_body: str) -> dict[str, Any] | None:
    try:
        parsed = yaml.safe_load(frontmatter_body)
        return parsed if isinstance(parsed, dict) else None
    except yaml.YAMLError:
        sanitized = _sanitize_frontmatter_for_yaml(frontmatter_body)
        try:
            parsed = yaml.safe_load(sanitized)
            if isinstance(parsed, dict):
                return parsed
        except yaml.YAMLError:
            return None
    return None


def _normalise_frontmatter_body(frontmatter_body: str, iso_date: str) -> tuple[str, str] | None:
    parsed = _safe_load_frontmatter(frontmatter_body)
    if parsed is None:
        return None
    return _normalise_parsed_recipe(parsed, iso_date)


def _build_frontmatter_from_plain_markdown(llm_response: str, iso_date: str) -> tuple[str, str] | None:
    # Some providers return YAML-like recipe objects without --- fences.
    parsed_yaml_like = _safe_load_frontmatter(llm_response)
    if parsed_yaml_like is not None:
        normalised = _normalise_parsed_recipe(parsed_yaml_like, iso_date)
        if normalised is not None:
            return normalised

    title = _parse_title_from_markdown(llm_response)
    if not title:
        fallback_title = _first_non_empty_line(llm_response)
        if not fallback_title:
            return None
        title = fallback_title[:120]

    ingredient_lines = _extract_section_lines(llm_response, ("zutaten", "ingredients"))
    direction_lines = _extract_section_lines(
        llm_response,
        ("zubereitung", "anleitung", "instructions", "directions"),
    )

    ingredients = _extract_bullet_items(ingredient_lines)
    directions = _extract_direction_items(direction_lines)

    # Fallback for varied heading names: use all bullets / ordered steps globally.
    if not ingredients:
        ingredients = _extract_bullet_items(llm_response.splitlines())
    if not directions:
        directions = _extract_direction_items(llm_response.splitlines())

    # Last-resort fallback: preserve first non-empty content line as one step.
    if not ingredients and not directions:
        snippet = _first_non_empty_line(llm_response)
        if snippet:
            directions = [snippet]

    if not ingredients and not directions:
        return None

    yield_value = _extract_yield_value(llm_response)

    frontmatter_lines = [
        "layout: recipe",
        f"date: {iso_date}",
        "",
        f"title: {_yaml_scalar(title)}",
    ]

    if yield_value:
        frontmatter_lines.extend([
            "",
            f"yield: {_yaml_scalar(yield_value)}",
        ])

    frontmatter_lines.append("")
    frontmatter_lines.append("ingredients:")
    if not ingredients:
        return None
    frontmatter_lines.extend(f"- {_yaml_scalar(item)}" for item in ingredients)

    frontmatter_lines.append("")
    frontmatter_lines.append("directions:")
    if directions:
        frontmatter_lines.extend(f"- {_yaml_scalar(item)}" for item in directions)
    else:
        frontmatter_lines.append("- \"\"")

    full_md = f"---\n{'\n'.join(frontmatter_lines)}\n---\n"
    return title, full_md


def _now_iso() -> str:
    """Return the current datetime as an ISO-8601 string with UTC offset."""
    return datetime.now(tz=timezone.utc).astimezone().isoformat()


def _inject_date(frontmatter_body: str, iso_date: str) -> str:
    """Insert a ``date:`` field if not already present."""
    if re.search(r"^date:", frontmatter_body, re.MULTILINE):
        return frontmatter_body
    if re.search(r"^layout:", frontmatter_body, re.MULTILINE):
        return re.sub(
            r"(^layout:.*$)",
            rf"\1\ndate: {iso_date}",
            frontmatter_body,
            count=1,
            flags=re.MULTILINE,
        )
    return f"date: {iso_date}\n{frontmatter_body}"


def _inject_layout(frontmatter_body: str) -> str:
    """Ensure ``layout: recipe`` is present."""
    if re.search(r"^layout:", frontmatter_body, re.MULTILINE):
        return frontmatter_body
    return f"layout: recipe\n{frontmatter_body}"


def _get_title(frontmatter_body: str) -> str | None:
    match = _TITLE_RE.search(frontmatter_body)
    return match.group(1).strip() if match else None


def parse_llm_output(llm_response: str) -> list[tuple[str, str]]:
    """
    Parse LLM output into a list of ``(title, full_markdown)`` tuples.

    The LLM may return one or several fenced YAML front-matter blocks.
    Each block becomes its own recipe file.
    """
    iso_date = _now_iso()
    recipes: list[tuple[str, str]] = []

    matches = list(_FRONTMATTER_RE.finditer(llm_response))

    if not matches:
        logger.warning("LLM response contained no recognised frontmatter blocks")
        fallback = _build_frontmatter_from_plain_markdown(llm_response, iso_date)
        if fallback is None:
            return []
        logger.info("Parsed plain markdown response into recipe frontmatter")
        return [fallback]

    for match in matches:
        body = match.group(1)
        normalised = _normalise_frontmatter_body(body, iso_date)
        if normalised is None:
            body = _inject_layout(body)
            body = _inject_date(body, iso_date)
            title = _get_title(body)
            if not title:
                logger.warning("Skipping frontmatter block with no title")
                continue
            full_md = f"---\n{body}\n---\n"
            recipes.append((title, full_md))
            continue
        recipes.append(normalised)

    return recipes


def write_recipes(
    recipes: list[tuple[str, str]],
    output_dir: Path,
    *,
    dry_run: bool = False,
) -> list[Path]:
    """
    Write recipe markdown files to *output_dir*.

    Each recipe is written to:
        <output_dir>/<slug>/index.md

    Components (recipes without a ``components:`` key) are placed under
    ``components/``; the main recipe goes to ``recipes/``.

    Parameters
    ----------
    recipes:
        List of ``(title, markdown_text)`` tuples as returned by
        :func:`parse_llm_output`.
    output_dir:
        Root directory (e.g. the Hugo ``content/`` folder).
    dry_run:
        When ``True``, print output to stdout instead of writing files.

    Returns
    -------
    List of :class:`~pathlib.Path` objects for every written file.
    """
    if not recipes:
        logger.error("No recipes to write")
        return []

    main_recipes = [(title, markdown) for title, markdown in recipes if _COMPONENTS_KEY in markdown]
    components = [(title, markdown) for title, markdown in recipes if _COMPONENTS_KEY not in markdown]

    if not main_recipes and len(components) == 1:
        main_recipes = components
        components = []

    written: list[Path] = []

    for title, markdown in main_recipes:
        slug = make_slug(title)
        dest = output_dir / "recipes" / slug / "index.md"
        _write_file(dest, markdown, dry_run=dry_run)
        written.append(dest)

    for title, markdown in components:
        slug = make_slug(title)
        dest = output_dir / "components" / slug / "index.md"
        _write_file(dest, markdown, dry_run=dry_run)
        written.append(dest)

    return written


def _write_file(path: Path, content: str, *, dry_run: bool) -> None:
    if dry_run:
        sys.stdout.write(f"\n# === {path} ===\n")
        sys.stdout.write(content)
        sys.stdout.write("\n")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    logger.info("Written: %s", path)
