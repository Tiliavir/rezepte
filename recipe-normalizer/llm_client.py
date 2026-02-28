"""LLM client abstraction supporting Gemini, OpenAI and generic REST providers."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import urllib.parse
import urllib.request
from typing import Literal

logger = logging.getLogger(__name__)

Provider = Literal["gemini", "openai", "rest"]

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
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
9. Kein erklärender Text.\
"""


def build_user_prompt(raw_text: str) -> str:
    return raw_text


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------


def _call_gemini(raw_text: str) -> str:
    """Call Google Gemini via the `gcloud` SDK (application-default credentials)."""
    try:
        import google.generativeai as genai  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "google-generativeai is required for the Gemini provider. "
            "Install it with: pip install google-generativeai"
        ) from exc

    import google.auth  # type: ignore[import]
    import google.auth.transport.requests  # type: ignore[import]

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(google.auth.transport.requests.Request())

    genai.configure(credentials=credentials)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        system_instruction=SYSTEM_PROMPT,
    )
    response = model.generate_content(raw_text)
    return response.text


def _call_openai(raw_text: str) -> str:
    """Call OpenAI via the locally installed `openai` CLI."""
    openai_exe = shutil.which("openai")
    if openai_exe is None:
        raise RuntimeError(
            "'openai' CLI not found on PATH. "
            "Install it with: pip install openai"
        )
    payload = json.dumps(
        {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
        }
    )
    result = subprocess.run(  # noqa: S603
        [openai_exe, "api", "chat.completions.create", "--json"],
        input=payload,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    return data["choices"][0]["message"]["content"]


def _call_rest(raw_text: str) -> str:
    """
    Call a generic OpenAI-compatible REST endpoint.

    Required environment variables:
        RECIPE_NORMALIZER_API_URL   – base URL, e.g. https://api.openai.com/v1
        RECIPE_NORMALIZER_API_KEY   – bearer token
        RECIPE_NORMALIZER_MODEL     – model name (default: gpt-4o)
    """
    base_url = os.environ.get("RECIPE_NORMALIZER_API_URL", "").rstrip("/")
    api_key = os.environ.get("RECIPE_NORMALIZER_API_KEY", "")
    model = os.environ.get("RECIPE_NORMALIZER_MODEL", "gpt-4o")

    if not base_url:
        raise ValueError(
            "RECIPE_NORMALIZER_API_URL environment variable must be set for the 'rest' provider."
        )
    if not api_key:
        raise ValueError(
            "RECIPE_NORMALIZER_API_KEY environment variable must be set for the 'rest' provider."
        )

    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"RECIPE_NORMALIZER_API_URL must use http or https, got scheme: {parsed.scheme!r}"
        )
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as response:  # noqa: S310
        data = json.loads(response.read().decode("utf-8"))

    return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def call_llm(raw_text: str, provider: Provider = "gemini") -> str:
    """
    Send *raw_text* to the configured LLM provider and return the response.

    Parameters
    ----------
    raw_text:
        The plain-text recipe content.
    provider:
        Which LLM backend to use: ``"gemini"``, ``"openai"``, or ``"rest"``.
    """
    logger.info("Calling LLM provider '%s'", provider)

    if provider == "gemini":
        return _call_gemini(raw_text)
    if provider == "openai":
        return _call_openai(raw_text)
    if provider == "rest":
        return _call_rest(raw_text)

    raise ValueError(f"Unknown provider '{provider}'. Choose from: gemini, openai, rest")
