"""recipe-normalizer – convert any recipe into a standardised German Markdown file.

Usage
-----
    recipe-normalizer <input> [--out <target-folder>] [--provider gemini|openai|rest]
                              [--dry-run] [--log-level DEBUG|INFO|WARNING|ERROR]
"""

from __future__ import annotations

import logging
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
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(levelname)s: %(message)s",
        level=numeric,
        stream=sys.stderr,
    )


@app.command()
def main(
    source: str = typer.Argument(
        ...,
        help="Input: file path (.txt .md .html .jpg .png .pdf) or HTTP/HTTPS URL.",
        metavar="INPUT",
    ),
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        "-o",
        help="Target folder for generated files (defaults to ./content).",
        show_default=False,
    ),
    provider: str = typer.Option(
        "gemini",
        "--provider",
        "-p",
        help="LLM provider to use: gemini | openai | rest.",
        show_default=True,
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print generated Markdown to stdout instead of writing files.",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        help="Logging verbosity: DEBUG | INFO | WARNING | ERROR.",
        show_default=True,
    ),
) -> None:
    """Convert *INPUT* into standardised German Markdown recipe files."""
    _setup_logging(log_level)
    logger = logging.getLogger(__name__)

    # Validate provider early
    valid_providers = ("gemini", "openai", "rest")
    if provider not in valid_providers:
        typer.echo(
            f"Error: unknown provider '{provider}'. "
            f"Choose from: {', '.join(valid_providers)}",
            err=True,
        )
        raise typer.Exit(code=1)

    # Determine output directory
    if out is None:
        out = Path.cwd() / "content"

    # -----------------------------------------------------------------------
    # Step 1 – load raw text
    # -----------------------------------------------------------------------
    from input_handler import load_raw_text

    try:
        logger.info("Loading input: %s", source)
        raw_text = load_raw_text(source)
    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Error loading input: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not raw_text.strip():
        typer.echo("Error: input produced empty text.", err=True)
        raise typer.Exit(code=1)

    logger.debug("Raw text (%d chars):\n%s", len(raw_text), raw_text[:500])

    # -----------------------------------------------------------------------
    # Step 2 – call LLM
    # -----------------------------------------------------------------------
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

    logger.debug("LLM response:\n%s", llm_response[:1000])

    # -----------------------------------------------------------------------
    # Step 3 – parse and write
    # -----------------------------------------------------------------------
    from markdown_writer import parse_llm_output, write_recipes

    recipes = parse_llm_output(llm_response)
    if not recipes:
        typer.echo(
            "Error: could not parse any recipe from LLM response. "
            "Try --log-level DEBUG to inspect the raw output.",
            err=True,
        )
        raise typer.Exit(code=1)

    written = write_recipes(recipes, out, dry_run=dry_run)

    if not dry_run:
        for path in written:
            typer.echo(str(path))


def cli() -> None:
    """Entry point registered in pyproject.toml."""
    app()


if __name__ == "__main__":
    cli()
