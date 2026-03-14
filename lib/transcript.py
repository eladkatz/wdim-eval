"""Transcript data model and JSON fixture I/O.

Mirrors the Swift app's TranscribedSentence struct so prompts tested here
translate directly back to the app.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class TranscribedSentence:
    """A single transcribed sentence with timestamps.

    Matches Swift: AudioBookPlayer/Models/Models.swift → TranscribedSentence
    """

    text: str
    start_time: float  # seconds
    end_time: float  # seconds
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class Chapter:
    """Chapter metadata extracted from an m4b file."""

    index: int
    title: str
    start_time: float  # seconds
    end_time: float  # seconds

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


# ---------------------------------------------------------------------------
# Fixture I/O
# ---------------------------------------------------------------------------

def save_fixture(sentences: list[TranscribedSentence], path: str | Path) -> Path:
    """Save sentences to a JSON fixture file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(s) for s in sentences]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return path


def load_fixture(path: str | Path) -> list[TranscribedSentence]:
    """Load sentences from a JSON fixture file."""
    path = Path(path)
    data = json.loads(path.read_text())
    return [TranscribedSentence(**item) for item in data]


def save_chapters(chapters: list[Chapter], path: str | Path) -> Path:
    """Save chapter metadata to JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(c) for c in chapters]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return path


def load_chapters(path: str | Path) -> list[Chapter]:
    """Load chapter metadata from JSON."""
    path = Path(path)
    data = json.loads(path.read_text())
    return [Chapter(**item) for item in data]


# ---------------------------------------------------------------------------
# Transcript formatting
# ---------------------------------------------------------------------------

def format_transcript(sentences: list[TranscribedSentence]) -> str:
    """Plain text transcript for prompt insertion (matches Swift's joined separator)."""
    return " ".join(s.text for s in sentences)


def format_transcript_display(sentences: list[TranscribedSentence]) -> str:
    """Transcript with [MM:SS] timestamps for notebook viewing."""
    lines = []
    for s in sentences:
        mins, secs = divmod(int(s.start_time), 60)
        lines.append(f"[{mins:02d}:{secs:02d}] {s.text}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sub-segment selection (mirrors app's loadSentences query)
# ---------------------------------------------------------------------------

def select_sentences(
    sentences: list[TranscribedSentence],
    start_time: float,
    end_time: float,
) -> list[TranscribedSentence]:
    """Select sentences within a time range.

    Matches the app's SQL query:
        WHERE start_time >= ? AND start_time < ?
        ORDER BY start_time ASC
    """
    return [
        s for s in sentences
        if s.start_time >= start_time and s.start_time < end_time
    ]


def select_window(
    sentences: list[TranscribedSentence],
    position: float,
    window_minutes: float = 5.0,
    overlap_seconds: float = 15.0,
) -> list[TranscribedSentence]:
    """Select sentences for a WDIM-style window ending at `position`.

    Mirrors MissedSummaryService.queryTranscript():
        windowEnd = currentTime
        windowStart = max(0, currentTime - windowDuration)
        overlapStart = max(0, windowStart - overlapDuration)
    """
    window_seconds = window_minutes * 60
    window_start = max(0, position - window_seconds)
    # Load with overlap, then filter to actual window
    overlap_start = max(0, window_start - overlap_seconds)
    all_in_range = select_sentences(sentences, overlap_start, position)
    # Filter to actual window (exclude overlap-only sentences)
    return [s for s in all_in_range if s.start_time >= window_start]
