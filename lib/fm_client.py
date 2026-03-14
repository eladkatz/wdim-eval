"""Apple Foundation Models SDK wrapper.

Mirrors the Swift app's callModel() pattern in MissedSummaryService.swift.

Requires: macOS 26+ (Tahoe), Apple Silicon, apple-fm-sdk installed.
"""

from __future__ import annotations

import time

try:
    import apple_fm_sdk as fm
except ImportError:
    fm = None  # Allow importing module for docs/tests even without SDK


def check_availability() -> tuple[bool, str]:
    """Check if Apple Foundation Models are available.

    Returns:
        (is_available, reason) tuple.
    """
    if fm is None:
        return False, "apple-fm-sdk not installed. Run: pip install apple-fm-sdk"

    try:
        model = fm.SystemLanguageModel()
        available, reason = model.is_available()
        return available, reason or "Available"
    except Exception as e:
        return False, str(e)


async def call_model(combined_prompt: str) -> str:
    """Call the on-device Foundation Model with a combined prompt.

    Mirrors Swift:
        let session = LanguageModelSession()
        let response = try await session.respond(to: combinedPrompt)
        return response.content

    Args:
        combined_prompt: System + user prompt concatenated (as the Swift app does).

    Returns:
        The model's response text.

    Raises:
        RuntimeError: If the FM SDK is not available.
        Exception: FM SDK errors (ExceededContextWindowSizeError, GuardrailViolationError, etc.)
    """
    if fm is None:
        raise RuntimeError("apple-fm-sdk not installed")

    session = fm.LanguageModelSession()
    response = await session.respond(combined_prompt)
    # SDK returns a string directly (unlike Swift which returns .content)
    return response if isinstance(response, str) else response.content


async def call_model_timed(combined_prompt: str) -> tuple[str, float]:
    """Call the model and return (response_text, latency_seconds)."""
    start = time.perf_counter()
    response = await call_model(combined_prompt)
    latency = time.perf_counter() - start
    return response, latency


async def call_model_structured(prompt: str, schema_class):
    """Call the model with structured generation (guided output).

    Uses the FM SDK's @fm.generable decorator for constrained decoding.

    Args:
        prompt: The prompt text.
        schema_class: A class decorated with @fm.generable.

    Returns:
        An instance of schema_class populated by the model.
    """
    if fm is None:
        raise RuntimeError("apple-fm-sdk not installed")

    session = fm.LanguageModelSession()
    result = await session.respond(prompt, generating=schema_class)
    return result
