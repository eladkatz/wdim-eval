"""Whisper-based transcription that produces TranscribedSentence objects.

Uses OpenAI's Whisper model locally. The `small` model is recommended for
audiobooks (clean studio audio, English).

Note: This is NOT identical to Apple's SpeechTranscriber — sentence boundaries
will differ. It's close enough for prompt evaluation purposes.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import whisper

from .transcript import TranscribedSentence, save_fixture


def load_model(model_size: str = "small") -> whisper.Whisper:
    """Load a Whisper model. Cached after first download."""
    return whisper.load_model(model_size)


def transcribe_audio(
    audio_path: str | Path,
    model: whisper.Whisper | None = None,
    model_size: str = "small",
    language: str = "en",
    chapter_offset: float = 0.0,
) -> list[TranscribedSentence]:
    """Transcribe an audio file and return TranscribedSentence objects.

    Args:
        audio_path: Path to WAV (or any ffmpeg-supported) audio file.
        model: Pre-loaded Whisper model (avoids reloading).
        model_size: Whisper model size if model is None.
        language: Language code.
        chapter_offset: Time offset to add to all timestamps (e.g., chapter
            start time within the full book). This makes timestamps absolute
            within the book, matching the app's behavior.

    Returns:
        List of TranscribedSentence with timestamps relative to the book.
    """
    if model is None:
        model = load_model(model_size)

    result = model.transcribe(
        str(audio_path),
        language=language,
        word_timestamps=True,
        verbose=False,
    )

    sentences = _segments_to_sentences(result["segments"], chapter_offset)
    return sentences


def transcribe_and_save(
    audio_path: str | Path,
    fixture_path: str | Path,
    model: whisper.Whisper | None = None,
    model_size: str = "small",
    language: str = "en",
    chapter_offset: float = 0.0,
) -> list[TranscribedSentence]:
    """Transcribe and auto-save as a JSON fixture."""
    sentences = transcribe_audio(
        audio_path, model, model_size, language, chapter_offset
    )
    save_fixture(sentences, fixture_path)
    return sentences


# ---------------------------------------------------------------------------
# Post-processing: Whisper segments → clean sentences
# ---------------------------------------------------------------------------

# Sentence-ending punctuation
_SENTENCE_END = re.compile(r'[.!?]["\'»)}\]]*\s*$')


def _segments_to_sentences(
    segments: list[dict],
    time_offset: float = 0.0,
) -> list[TranscribedSentence]:
    """Convert Whisper segments into sentence-aligned TranscribedSentence objects.

    Whisper segments don't always align to sentence boundaries. This function:
    1. Merges short fragments that don't end with sentence punctuation.
    2. Splits segments that contain multiple sentences.
    """
    sentences: list[TranscribedSentence] = []
    buffer_text = ""
    buffer_start: float | None = None
    buffer_end: float = 0.0

    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue

        start = seg["start"] + time_offset
        end = seg["end"] + time_offset

        if buffer_start is None:
            buffer_start = start

        buffer_text = (buffer_text + " " + text).strip() if buffer_text else text
        buffer_end = end

        # Flush if the accumulated text ends with sentence punctuation
        if _SENTENCE_END.search(buffer_text):
            sentences.append(TranscribedSentence(
                id=str(uuid.uuid4()),
                text=buffer_text,
                start_time=buffer_start,
                end_time=buffer_end,
            ))
            buffer_text = ""
            buffer_start = None

    # Flush any remaining text
    if buffer_text and buffer_start is not None:
        sentences.append(TranscribedSentence(
            id=str(uuid.uuid4()),
            text=buffer_text,
            start_time=buffer_start,
            end_time=buffer_end,
        ))

    return sentences
