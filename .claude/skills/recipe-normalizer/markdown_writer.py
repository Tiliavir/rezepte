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
