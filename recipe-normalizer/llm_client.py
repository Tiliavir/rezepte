"""LLM client abstraction supporting Gemini, OpenAI and generic REST providers."""

from __future__ import annotations

import json
import importlib.util
import logging
import os
import shutil
import subprocess
import time
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
    """Call Google Gemini using API-key authentication."""
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    configured_model = os.environ.get("RECIPE_NORMALIZER_GEMINI_MODEL", "").strip()
    if not api_key:
        raise RuntimeError(
            "Gemini authentication missing. Set GOOGLE_API_KEY (or GEMINI_API_KEY) "
            "and retry, or use --provider openai/rest."
        )

    try:
        from google import genai  # type: ignore[import]
        from google.genai import types  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "Gemini provider requires 'google-genai'. Install with: "
            "pip install -e '.[gemini]'"
        ) from exc

    client = genai.Client(api_key=api_key)
    default_candidates = ["gemini-2.5-pro", "gemini-2.5-flash"]
    if configured_model:
        model_candidates = [configured_model, *default_candidates]
    else:
        model_candidates = default_candidates

    max_retries = max(0, int(os.environ.get("RECIPE_NORMALIZER_GEMINI_RETRIES", "2")))

    def _is_retryable_error(message: str) -> bool:
        lowered = message.lower()
        markers = (
            "429",
            "too many requests",
            "rate limit",
            "resource_exhausted",
            "quota",
            "temporarily unavailable",
            "deadline exceeded",
            "timed out",
            "timeout",
        )
        return any(marker in lowered for marker in markers)

    tried: list[str] = []
    for model_name in model_candidates:
        if model_name in tried:
            continue
        tried.append(model_name)
        for attempt in range(max_retries + 1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=raw_text,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                )
                if not response.text:
                    raise RuntimeError("Gemini returned an empty response.")
                return response.text
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                lowered = message.lower()
                not_found_error = "not found" in lowered or "404" in lowered
                retryable_error = _is_retryable_error(message)
                has_retries_left = attempt < max_retries

                if retryable_error and has_retries_left:
                    sleep_seconds = min(8.0, 1.5 * (2 ** attempt))
                    logger.warning(
                        "Gemini model '%s' failed with transient error (%s). "
                        "Retrying in %.1fs (%d/%d).",
                        model_name,
                        message,
                        sleep_seconds,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(sleep_seconds)
                    continue

                should_try_next_model = (
                    (not_found_error or retryable_error)
                    and model_name != model_candidates[-1]
                )
                if should_try_next_model:
                    logger.warning(
                        "Gemini model '%s' failed (%s); trying fallback model.",
                        model_name,
                        message,
                    )
                    break

                raise RuntimeError(
                    "Gemini request failed for model(s) "
                    f"{', '.join(tried)}. "
                    "Set RECIPE_NORMALIZER_GEMINI_MODEL to a supported model if needed. "
                    f"Original error: {message}"
                ) from exc

    raise RuntimeError("Gemini request failed before a model call was attempted.")


def _is_provider_configured(provider: Provider) -> bool:
    """Return True if *provider* appears usable in the current environment."""
    if provider == "gemini":
        has_key = bool(os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))
        has_package = importlib.util.find_spec("google.genai") is not None
        return has_key and has_package

    if provider == "openai":
        return shutil.which("openai") is not None

    if provider == "rest":
        has_url = bool(os.environ.get("RECIPE_NORMALIZER_API_URL", "").strip())
        has_key = bool(os.environ.get("RECIPE_NORMALIZER_API_KEY", "").strip())
        return has_url and has_key

    return False


def get_available_providers() -> list[Provider]:
    """Return configured providers in priority order."""
    order: tuple[Provider, ...] = ("gemini", "openai", "rest")
    return [provider for provider in order if _is_provider_configured(provider)]


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
    result = subprocess.run(  # noqa: S603  # NOSONAR python:S4721
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

    req = urllib.request.Request(  # NOSONAR python:S5144
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as response:  # noqa: S310  # NOSONAR python:S5144
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

    if provider not in ("gemini", "openai", "rest"):
        raise ValueError(f"Unknown provider '{provider}'. Choose from: gemini, openai, rest")

    provider_chain: list[Provider] = [provider]
    if provider == "gemini":
        for fallback in ("openai", "rest"):
            if _is_provider_configured(fallback):
                provider_chain.append(fallback)

    last_exception: Exception | None = None
    for index, current_provider in enumerate(provider_chain):
        try:
            if current_provider == "gemini":
                return _call_gemini(raw_text)
            if current_provider == "openai":
                return _call_openai(raw_text)
            return _call_rest(raw_text)
        except Exception as exc:  # noqa: BLE001
            last_exception = exc
            has_next = index < len(provider_chain) - 1
            if has_next:
                logger.warning(
                    "Provider '%s' failed (%s). Falling back to '%s'.",
                    current_provider,
                    exc,
                    provider_chain[index + 1],
                )
                continue
            break

    if last_exception is not None:
        raise last_exception

    raise RuntimeError("LLM call failed before a provider request was attempted.")
