"""m4b chapter extraction and audio slicing via ffmpeg.

Requires: brew install ffmpeg
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .transcript import Chapter


# ---------------------------------------------------------------------------
# Cue-sheet parsing (fallback when ffprobe finds no embedded chapters)
# ---------------------------------------------------------------------------

def _cue_index_to_seconds(index_str: str) -> float:
    """Convert a CUE INDEX timestamp (MM:SS:FF) to seconds.

    CUE frames are 1/75th of a second.
    """
    parts = index_str.strip().split(":")
    if len(parts) == 3:
        minutes, seconds, frames = int(parts[0]), int(parts[1]), int(parts[2])
        return minutes * 60 + seconds + frames / 75.0
    return 0.0


def _parse_cue_file(cue_path: Path, total_duration: float) -> list[Chapter]:
    """Parse a .cue file and return Chapter objects."""
    text = cue_path.read_text(encoding="utf-8", errors="replace")
    tracks: list[tuple[str, float]] = []

    current_title = ""
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r'TITLE\s+"(.+)"', line)
        if m:
            current_title = m.group(1)
        m = re.match(r"INDEX\s+01\s+(.+)", line)
        if m:
            tracks.append((current_title or f"Track {len(tracks) + 1}", _cue_index_to_seconds(m.group(1))))
            current_title = ""

    chapters = []
    for i, (title, start) in enumerate(tracks):
        end = tracks[i + 1][1] if i + 1 < len(tracks) else total_duration
        chapters.append(Chapter(index=i, title=title, start_time=start, end_time=end))

    return chapters


def _find_cue_file(m4b_path: Path) -> Path | None:
    """Look for a .cue sidecar next to the m4b."""
    cue = m4b_path.with_suffix(".cue")
    if cue.exists():
        return cue
    # Also check for any .cue in the same directory
    for p in m4b_path.parent.glob("*.cue"):
        return p
    return None


# ---------------------------------------------------------------------------
# ffprobe helpers
# ---------------------------------------------------------------------------

def _run_ff(args: list[str], m4b_path: Path, **kwargs) -> subprocess.CompletedProcess:
    """Run an ffmpeg/ffprobe command from the file's parent directory.

    This avoids issues with special characters (brackets, apostrophes) in
    full paths — we cd into the directory and use just the filename.
    """
    # TODO: Fix proper escaping for ffmpeg/ffprobe so special chars work
    # without needing to rename files.  For now we warn and require clean names.
    return subprocess.run(args, cwd=m4b_path.parent, **kwargs)


_UNSAFE_CHARS = re.compile(r"[\[\]''\u2018\u2019\u201c\u201d]")


def check_path_safe(path: str | Path) -> None:
    """Raise ValueError if the path contains characters that break ffmpeg.

    Known issue: brackets [], smart quotes, and curly apostrophes in file or
    folder names cause ffprobe/ffmpeg to fail.  Rename the file/folder to
    remove these characters before proceeding.
    """
    s = str(path)
    found = _UNSAFE_CHARS.findall(s)
    if found:
        chars = ", ".join(repr(c) for c in set(found))
        raise ValueError(
            f"Path contains special characters that break ffmpeg: {chars}\n"
            f"  Path: {s}\n"
            f"  Please rename the file/folder to remove these characters."
        )


def _get_duration(m4b_path: Path) -> float:
    """Get total duration using ffprobe -show_entries."""
    result = _run_ff(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", m4b_path.name],
        m4b_path, capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except (ValueError, TypeError):
        return 0.0


def extract_chapters(m4b_path: str | Path) -> list[Chapter]:
    """Extract chapter metadata from an m4b file.

    Tries ffprobe embedded chapters first, then falls back to a sidecar
    .cue file if present.  If neither exists, returns a single chapter
    spanning the entire file.
    """
    m4b_path = Path(m4b_path)
    check_path_safe(m4b_path)

    # Try ffprobe for embedded chapters (don't check=True; some files return
    # non-zero even when readable).  Run from parent dir to avoid path issues.
    result = _run_ff(
        [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_chapters",
            "-show_format",
            m4b_path.name,
        ],
        m4b_path, capture_output=True, text=True,
    )

    data = {}
    if result.stdout.strip():
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            pass

    raw_chapters = data.get("chapters", [])

    if raw_chapters:
        chapters = []
        for i, ch in enumerate(raw_chapters):
            title = ch.get("tags", {}).get("title", f"Chapter {i + 1}")
            start = float(ch["start_time"])
            end = float(ch["end_time"])
            chapters.append(Chapter(index=i, title=title, start_time=start, end_time=end))
        return chapters

    # Fallback: look for a sidecar .cue file
    duration = float(data.get("format", {}).get("duration", 0)) or _get_duration(m4b_path)
    cue = _find_cue_file(m4b_path)
    if cue:
        chapters = _parse_cue_file(cue, duration)
        if chapters:
            return chapters

    # Last resort: single chapter for the whole file
    return [Chapter(index=0, title="Full Book", start_time=0.0, end_time=duration)]


def extract_audio_slice(
    m4b_path: str | Path,
    start_seconds: float,
    end_seconds: float,
    output_path: str | Path,
) -> Path:
    """Extract a WAV audio slice from an m4b file.

    Uses ffmpeg to decode the specified time range to WAV (16kHz mono),
    which is the format Whisper expects.
    """
    m4b_path = Path(m4b_path)
    check_path_safe(m4b_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    duration = end_seconds - start_seconds

    # Use absolute path for output since we cwd into the m4b's directory
    abs_output = str(output_path.resolve())

    _run_ff(
        [
            "ffmpeg",
            "-y",  # overwrite
            "-i", m4b_path.name,
            "-ss", str(start_seconds),
            "-t", str(duration),
            "-ar", "16000",  # 16kHz for Whisper
            "-ac", "1",  # mono
            "-f", "wav",
            abs_output,
        ],
        m4b_path, capture_output=True, check=True,
    )

    return output_path


def extract_chapter_audio(
    m4b_path: str | Path,
    chapter: Chapter,
    output_dir: str | Path,
) -> Path:
    """Extract a single chapter's audio as a WAV file."""
    output_dir = Path(output_dir)
    safe_title = f"ch{chapter.index:02d}"
    output_path = output_dir / f"{safe_title}.wav"
    return extract_audio_slice(m4b_path, chapter.start_time, chapter.end_time, output_path)
