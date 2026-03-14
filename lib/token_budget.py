"""Token estimation and budget allocation.

Since Apple's tokenCount(for:) is not available in the Python FM SDK,
we use tiktoken (cl100k_base) as a proxy estimator. The calibrate_context_limit()
function measures the actual limit empirically and derives a correction factor.
"""

from __future__ import annotations

from dataclasses import dataclass

import tiktoken

from .transcript import TranscribedSentence

# Use cl100k_base as a rough proxy for Apple's tokenizer
_encoding = tiktoken.get_encoding("cl100k_base")

# Default Apple FM context limit
DEFAULT_CONTEXT_LIMIT = 4096


@dataclass
class BudgetResult:
    """Result of token budget allocation."""

    instruction_tokens: int
    transcript_tokens: int
    response_reserve: int
    safety_margin: int
    total_used: int
    total_limit: int
    sentences_included: int
    sentences_dropped: int
    included_sentences: list[TranscribedSentence]


def estimate_tokens(text: str) -> int:
    """Estimate token count using tiktoken as a proxy."""
    return len(_encoding.encode(text))


def allocate_budget(
    instructions: str,
    sentences: list[TranscribedSentence],
    response_reserve: int = 800,
    safety_margin: int = 100,
    context_limit: int = DEFAULT_CONTEXT_LIMIT,
) -> BudgetResult:
    """Allocate token budget following the WDIM V2 plan (section A.1).

    Algorithm:
    1. Count fixed instruction tokens
    2. Compute transcript budget = limit - instructions - response_reserve - safety
    3. Pack sentences newest-to-oldest until budget is full

    Args:
        instructions: The system + user prompt text WITHOUT the transcript
        sentences: All candidate sentences (should be pre-sorted by start_time)
        response_reserve: Tokens reserved for the model's response
        safety_margin: Extra safety buffer
        context_limit: Total context window size

    Returns:
        BudgetResult with allocation details and selected sentences.
    """
    instruction_tokens = estimate_tokens(instructions)
    transcript_budget = context_limit - instruction_tokens - response_reserve - safety_margin

    if transcript_budget <= 0:
        return BudgetResult(
            instruction_tokens=instruction_tokens,
            transcript_tokens=0,
            response_reserve=response_reserve,
            safety_margin=safety_margin,
            total_used=instruction_tokens,
            total_limit=context_limit,
            sentences_included=0,
            sentences_dropped=len(sentences),
            included_sentences=[],
        )

    # Pack sentences newest-to-oldest
    included = select_recent_sentences(sentences, transcript_budget)
    transcript_text = " ".join(s.text for s in included)
    transcript_tokens = estimate_tokens(transcript_text)

    return BudgetResult(
        instruction_tokens=instruction_tokens,
        transcript_tokens=transcript_tokens,
        response_reserve=response_reserve,
        safety_margin=safety_margin,
        total_used=instruction_tokens + transcript_tokens,
        total_limit=context_limit,
        sentences_included=len(included),
        sentences_dropped=len(sentences) - len(included),
        included_sentences=included,
    )


def select_recent_sentences(
    sentences: list[TranscribedSentence],
    max_tokens: int,
) -> list[TranscribedSentence]:
    """Select sentences from newest to oldest until the token budget is full.

    Returns sentences in chronological order (oldest first) for prompt insertion.
    """
    if not sentences:
        return []

    # Walk backwards (newest first)
    selected: list[TranscribedSentence] = []
    used_tokens = 0

    for sentence in reversed(sentences):
        sentence_tokens = estimate_tokens(sentence.text)
        if used_tokens + sentence_tokens > max_tokens:
            break
        selected.append(sentence)
        used_tokens += sentence_tokens

    # Return in chronological order
    selected.reverse()
    return selected


async def calibrate_context_limit(
    call_model_fn,
    base_prompt: str = "Respond with OK.",
    filler_word: str = "test ",
    step_tokens: int = 200,
    max_attempts: int = 30,
) -> dict:
    """Empirically measure the actual context window limit.

    Sends progressively larger prompts until ExceededContextWindowSizeError fires,
    then records the tiktoken estimate at the boundary.

    Args:
        call_model_fn: An async function(prompt: str) -> str that calls the FM.
        base_prompt: Minimal prompt to start with.
        filler_word: Word to repeat as filler.
        step_tokens: How many estimated tokens to add per attempt.
        max_attempts: Safety limit on iterations.

    Returns:
        Dict with calibration results:
            - last_success_tokens: tiktoken estimate of largest successful prompt
            - first_failure_tokens: tiktoken estimate of smallest failing prompt
            - correction_factor: ratio to apply to tiktoken estimates
    """
    last_success_tokens = 0
    first_failure_tokens = None

    filler = ""
    filler_step = filler_word * (step_tokens // max(1, estimate_tokens(filler_word)))

    for attempt in range(max_attempts):
        prompt = base_prompt + "\n" + filler
        token_est = estimate_tokens(prompt)

        try:
            await call_model_fn(prompt)
            last_success_tokens = token_est
            filler += filler_step
        except Exception as e:
            error_name = type(e).__name__
            if "ContextWindow" in error_name or "context" in str(e).lower():
                first_failure_tokens = token_est
                break
            else:
                # Unexpected error — stop
                first_failure_tokens = token_est
                break

    correction_factor = 1.0
    if first_failure_tokens and last_success_tokens > 0:
        # The actual limit (in Apple tokens) is ~4096, which corresponds to
        # last_success_tokens in tiktoken units
        correction_factor = DEFAULT_CONTEXT_LIMIT / last_success_tokens

    return {
        "last_success_tokens": last_success_tokens,
        "first_failure_tokens": first_failure_tokens,
        "estimated_correction_factor": correction_factor,
        "effective_tiktoken_limit": last_success_tokens,
    }
