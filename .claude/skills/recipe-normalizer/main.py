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
