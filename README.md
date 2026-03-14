# WDIM Evaluation Playground

Test and iterate on "What Did I Miss?" prompts against Apple's on-device Foundation Model — from your Mac.

See [docs/EVAL_PLAYGROUND.md](docs/EVAL_PLAYGROUND.md) for the full technical reference, user guide, and agent instructions.

## Prerequisites

- **macOS 26+** (Tahoe) on **Apple Silicon**
- **Python 3.10+** (native ARM, not Rosetta)
- **ffmpeg**: `brew install ffmpeg`
- **Apple Intelligence** enabled in System Settings

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

Verify the Foundation Model is available:

```bash
python3 -c "import apple_fm_sdk as fm; m = fm.SystemLanguageModel(); print(m.is_available())"
# Should print: (True, None)
```

## Quick Start

```bash
source .venv/bin/activate
jupyter notebook notebooks/
```

1. **01 — Transcribe**: Set `m4b_path` to your audiobook, run all cells. Extracts chapters and transcribes with Whisper.
2. **02 — Explore**: Browse the transcript with timestamps and token counts.
3. **03 — Prompt Playground**: Send prompts to the Foundation Model, iterate on wording, check grounding.
4. **04 — Compare Formats**: Run all prompt variants side-by-side on the same transcript window.

## Agent-Driven Testing

Notebooks are [papermill](https://papermill.readthedocs.io/)-parameterized. Claude Code (or any agent) can drive them:

```bash
papermill notebooks/03_prompt_playground.ipynb notebooks/results/run_001.ipynb \
  -p book_slug "my-book" \
  -p chapter_index 3 \
  -p window_minutes 5.0 \
  -p prompt_variant "v2_narrative"
```

Open the output notebook in Jupyter or VS Code to see visual results.

## Prompt Variants

| Variant | Description | Status |
|---------|-------------|--------|
| `current_bullets` | Production WDIM (5-8 bullets) | Production |
| `current_mini_recap_default` | Library insights recap | Production |
| `current_mini_recap_sleep` | Sleep timer recap | Production |
| `current_mini_recap_interrupted` | Interruption recap | Production |
| `v2_narrative` | Narrative-first with structured JSON | Experimental |
| `v2_narrative_simple` | Lighter narrative variant | Experimental |

Prompts live in `lib/prompts.py` and mirror the Swift production code exactly.

## Key Differences from the iOS App

- **Transcription**: Uses Whisper (not Apple SpeechTranscriber). Sentence boundaries may differ slightly.
- **Token counting**: Uses tiktoken as a proxy. Run the calibration cell in notebook 03 to measure actual FM limits.
- **Same model**: The Python FM SDK calls the exact same on-device Foundation Model as the iOS app.

## Project Structure

```
├── lib/              # Python modules (importable + CLI-drivable)
│   ├── audio.py          Chapter extraction (ffmpeg + cue fallback)
│   ├── whisper_transcribe.py  Whisper transcription → sentence fixtures
│   ├── transcript.py     Data model, JSON I/O, windowing
│   ├── prompts.py        Prompt templates (mirrors Swift exactly)
│   ├── token_budget.py   Token estimation, budget allocation
│   ├── fm_client.py      Apple FM SDK wrapper
│   └── evaluate.py       Comparison runners, grounding checks
├── notebooks/        # Jupyter notebooks (numbered workflow)
├── fixtures/         # Saved transcript JSON (audio gitignored)
├── docs/             # Full documentation (SSOT)
└── pyproject.toml    # Dependencies
```
