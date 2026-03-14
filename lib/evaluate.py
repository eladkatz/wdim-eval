"""Comparison runners and grounding checks for prompt evaluation."""

from __future__ import annotations

import asyncio
import json
from difflib import SequenceMatcher

import pandas as pd
from rich.console import Console
from rich.table import Table

from .fm_client import call_model_timed
from .prompts import get_prompt, PROMPTS
from .token_budget import estimate_tokens
from .transcript import TranscribedSentence, format_transcript

console = Console()


async def run_single(variant: str, transcript: str) -> dict:
    """Run a single prompt variant and collect metrics."""
    prompt = get_prompt(variant, transcript)
    input_tokens = estimate_tokens(prompt)

    try:
        response, latency = await call_model_timed(prompt)
        output_tokens = estimate_tokens(response)
        error = None
    except Exception as e:
        response = ""
        latency = 0.0
        output_tokens = 0
        error = str(e)

    return {
        "variant": variant,
        "response": response,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "latency_s": round(latency, 2),
        "response_chars": len(response),
        "error": error,
    }


async def run_comparison(
    sentences: list[TranscribedSentence],
    variants: list[str] | None = None,
) -> pd.DataFrame:
    """Run multiple prompt variants and collect results.

    Args:
        sentences: Transcript sentences to use.
        variants: List of prompt variant names. Defaults to all.

    Returns:
        DataFrame with one row per variant.
    """
    if variants is None:
        variants = list(PROMPTS.keys())

    transcript = format_transcript(sentences)
    results = []

    for variant in variants:
        result = await run_single(variant, transcript)
        results.append(result)

    return pd.DataFrame(results)


def display_side_by_side(df: pd.DataFrame) -> None:
    """Display comparison results in a rich table."""
    table = Table(title="Prompt Comparison Results", show_lines=True)
    table.add_column("Variant", style="cyan", width=25)
    table.add_column("Tokens (in/out)", width=14)
    table.add_column("Latency", width=8)
    table.add_column("Response", style="white", max_width=80)

    for _, row in df.iterrows():
        tokens = f"{row['input_tokens']}/{row['output_tokens']}"
        latency = f"{row['latency_s']}s"
        response = row["response"][:200] + "..." if len(row["response"]) > 200 else row["response"]
        if row["error"]:
            response = f"[red]ERROR: {row['error']}[/red]"
        table.add_row(row["variant"], tokens, latency, response)

    console.print(table)


def check_grounding(response: str, transcript: str, threshold: float = 0.6) -> list[dict]:
    """Check whether response claims are grounded in the transcript.

    Uses fuzzy substring matching to flag sentences in the response that
    don't appear to come from the transcript.

    Args:
        response: The model's response text.
        transcript: The source transcript text.
        threshold: Minimum similarity ratio to consider "grounded".

    Returns:
        List of dicts with sentence, best_match_ratio, and grounded flag.
    """
    # Try to parse as JSON (V2 format) or split into sentences
    response_sentences = _extract_response_sentences(response)

    results = []
    transcript_lower = transcript.lower()

    for sent in response_sentences:
        sent_lower = sent.lower().strip()
        if len(sent_lower) < 10:
            continue

        # Check for exact substring
        if sent_lower in transcript_lower:
            results.append({"sentence": sent, "best_match_ratio": 1.0, "grounded": True})
            continue

        # Fuzzy matching against transcript windows
        best_ratio = 0.0
        # Slide a window of similar length across the transcript
        window_size = len(sent_lower) + 50
        for i in range(0, max(1, len(transcript_lower) - window_size), 20):
            window = transcript_lower[i : i + window_size]
            ratio = SequenceMatcher(None, sent_lower, window).ratio()
            best_ratio = max(best_ratio, ratio)
            if best_ratio >= threshold:
                break

        results.append({
            "sentence": sent,
            "best_match_ratio": round(best_ratio, 3),
            "grounded": best_ratio >= threshold,
        })

    return results


def _extract_response_sentences(response: str) -> list[str]:
    """Extract individual claim sentences from a response."""
    # Try JSON parsing first (V2 format)
    try:
        data = json.loads(response)
        sentences = []
        for key in ["recapNarrative", "currentState", "optionalQuote", "headline"]:
            if key in data and data[key]:
                sentences.append(str(data[key]))
        return sentences
    except (json.JSONDecodeError, TypeError):
        pass

    # Fall back to line-by-line extraction
    sentences = []
    for line in response.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Remove bullet markers
        for prefix in ["• ", "- ", "* "]:
            if line.startswith(prefix):
                line = line[len(prefix):]
        # Remove numbered list markers
        if len(line) > 2 and line[0].isdigit() and line[1] in ".)":
            line = line[2:].strip()
        if line:
            sentences.append(line)

    return sentences
