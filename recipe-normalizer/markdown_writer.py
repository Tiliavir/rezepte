"""Parse LLM output and write recipe markdown files to disk."""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from slug import make_slug

logger = logging.getLogger(__name__)

_COMPONENTS_KEY = "components:"

# Regex to capture individual fenced markdown documents (--- ... ---)
_FRONTMATTER_RE = re.compile(  # NOSONAR python:S5852
    r"(?:^|\n)---\s*\n(.*?)\n---",
    re.DOTALL,
)

# Match the title line inside frontmatter
_TITLE_RE = re.compile(r'^title:\s*["\']?(.+?)["\']?\s*$', re.MULTILINE)  # NOSONAR python:S5852


def _now_iso() -> str:
    """Return the current datetime as an ISO-8601 string with UTC offset."""
    return datetime.now(tz=timezone.utc).astimezone().isoformat()


def _inject_date(frontmatter_body: str, iso_date: str) -> str:
    """Insert a ``date:`` field if not already present."""
    if re.search(r"^date:", frontmatter_body, re.MULTILINE):
        return frontmatter_body
    # Insert after the layout line when present, otherwise prepend
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


def _is_component(frontmatter_body: str) -> bool:
    """Heuristic: a block is a component if it has NO 'components:' list."""
    return _COMPONENTS_KEY not in frontmatter_body


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
        # The LLM returned something unexpected – wrap as plain text
        logger.warning("LLM response contained no recognised frontmatter blocks")
        return []

    for match in matches:
        body = match.group(1)
        body = _inject_layout(body)
        body = _inject_date(body, iso_date)

        title = _get_title(body)
        if not title:
            logger.warning("Skipping frontmatter block with no title")
            continue

        full_md = f"---\n{body}\n---\n"
        recipes.append((title, full_md))

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

    # Separate main recipe(s) from components.
    # Convention: the recipe with a "components:" key is the main one.
    main_recipes = [
        (t, md) for t, md in recipes if _COMPONENTS_KEY in md
    ]
    components = [
        (t, md) for t, md in recipes if _COMPONENTS_KEY not in md
    ]

    # If there is only one recipe and no components field, treat it as main recipe
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
