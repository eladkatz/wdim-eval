# WDIM Evaluation Playground

**Source of truth** for the eval tool that tests "What Did I Miss?" prompts against Apple's on-device Foundation Model from a Mac.

---

## Purpose

The WDIM feature uses Apple's on-device Foundation Model to summarize recent audiobook content. Prompt iteration previously required deploying to an iPhone, which made systematic testing impractical. This playground runs the **same Foundation Model** locally on a Mac via Apple's Python FM SDK, enabling rapid prompt development with real audiobook transcripts.

The tool supports the [WDIM V2 Plan](../../docs/technical/WDIM_V2_PLAN.md) goals:

- Narrative-first prompts (replacing bullets)
- Token-aware budgeting (measuring real context limits)
- Source grounding (verifying claims trace to transcript)
- Structured generation (JSON output for reliable parsing)
- Evaluation harness (repeatable, comparable runs)

---

## Architecture

```
eval/
├── docs/
│   └── EVAL_PLAYGROUND.md      ← You are here (SSOT)
├── lib/                        ← Reusable Python modules
│   ├── audio.py                   Chapter extraction, audio slicing (ffmpeg)
│   ├── whisper_transcribe.py      Whisper transcription → sentence fixtures
│   ├── transcript.py              Data model (TranscribedSentence, Chapter), JSON I/O
│   ├── prompts.py                 Prompt templates (mirrors Swift exactly)
│   ├── token_budget.py            Token estimation (tiktoken), budget allocation
│   ├── fm_client.py               Apple FM SDK wrapper (call_model, structured gen)
│   └── evaluate.py                Comparison runners, grounding checks
├── notebooks/                  ← Numbered workflow (also papermill-parameterized)
│   ├── 01_extract_and_transcribe.ipynb
│   ├── 02_explore_transcript.ipynb
│   ├── 03_prompt_playground.ipynb
│   ├── 04_compare_formats.ipynb
│   └── results/                   Papermill output notebooks
├── fixtures/                   ← Saved transcript JSON (audio gitignored)
│   └── <book-slug>/
│       ├── chapters.json
│       ├── transcript_ch00.json
│       ├── transcript_ch01.json
│       └── audio/                 WAV slices (gitignored)
├── pyproject.toml              ← Dependencies
└── README.md                   ← Quick-start setup
```

### Module Dependency Graph

```
audio.py ──→ transcript.py (Chapter dataclass)
whisper_transcribe.py ──→ transcript.py (TranscribedSentence, save_fixture)
prompts.py ──→ (standalone, no internal deps)
token_budget.py ──→ transcript.py (TranscribedSentence)
fm_client.py ──→ apple_fm_sdk
evaluate.py ──→ prompts.py, token_budget.py, fm_client.py, transcript.py
```

---

## Data Model

### TranscribedSentence

Mirrors the Swift app's `TranscribedSentence` model:

```python
@dataclass
class TranscribedSentence:
    text: str           # Sentence text
    start_time: float   # Seconds from book start
    end_time: float     # Seconds from book start
    id: str             # UUID
```

### Chapter

```python
@dataclass
class Chapter:
    index: int          # 0-based chapter number
    title: str          # Chapter title from metadata
    start_time: float   # Seconds from book start
    end_time: float     # Seconds from book start
```

### Fixture JSON format

Each `transcript_chNN.json` is a JSON array of `TranscribedSentence` dicts:

```json
[
  {"text": "Mr and Mrs Dursley...", "start_time": 63.5, "end_time": 81.0, "id": "uuid"},
  ...
]
```

---

## Key Differences from the iOS App

| Aspect | iOS App | Eval Playground |
|--------|---------|-----------------|
| **Transcription** | Apple `SpeechTranscriber` | OpenAI Whisper (`small` model) |
| **Token counting** | `tokenCount(for:)` | `tiktoken` (`cl100k_base`) as proxy |
| **Token correction** | N/A | Empirical calibration (notebook 03) |
| **Foundation Model** | Same on-device FM | Same on-device FM (via Python SDK) |
| **Prompt construction** | `systemPrompt + "\n\n" + userPrompt` | Identical concatenation in `build_combined_prompt()` |
| **Context limit** | 4096 tokens (Apple tokenizer) | ~1105 tiktoken tokens ≈ 4096 Apple tokens (3.7x factor) |

### Transcription differences

Whisper produces slightly different sentence boundaries than Apple's `SpeechTranscriber`. For prompt evaluation this is acceptable — the content and word-level accuracy are comparable for clean audiobook audio. The `_segments_to_sentences()` function in `whisper_transcribe.py` merges Whisper segments at sentence boundaries (periods, question marks, exclamation marks) to approximate the app's sentence-level output.

### Token counting

The Apple FM SDK does not expose `tokenCount(for:)` in Python. We use tiktoken's `cl100k_base` encoder as a proxy. The calibration cell in notebook 03 empirically measures the actual context limit by binary-searching with increasingly large prompts until `ExceededContextWindowSizeError` fires. As of initial testing:

- **Effective tiktoken limit**: ~1,105 tokens
- **Correction factor**: ~3.7x (1 tiktoken token ≈ 3.7 Apple tokens)
- **Practical guidance**: Budget prompts to stay under ~1,000 tiktoken tokens for safety

---

## Prompt Variants

All prompts live in `lib/prompts.py` as `(system_prompt, user_prompt)` tuples. The `{transcript}` placeholder is the only variable.

| Variant | Description | Swift origin | Status |
|---------|-------------|-------------|--------|
| `current_bullets` | 5-8 bullets + "Where we are now" | `buildPrompts()` | Production |
| `current_mini_recap_default` | 2-3 friendly sentences | `buildMiniRecapPrompt()` | Production |
| `current_mini_recap_sleep` | Sleep timer variant | `buildMiniRecapPrompt()` | Production |
| `current_mini_recap_interrupted` | Interruption variant | `buildMiniRecapPrompt()` | Production |
| `v2_narrative` | Structured JSON (headline, recapNarrative, currentState, optionalQuote, suggestedFollowUps) | New (WDIM V2) | Experimental |
| `v2_narrative_simple` | Same without suggestedFollowUps (saves tokens) | New (WDIM V2) | Experimental |

**To add a new variant:** Add constants to `prompts.py`, register in the `PROMPTS` dict, and it will automatically appear in notebook 04's comparison runs.

**To port back to Swift:** Copy the system/user strings from `prompts.py` into `MissedSummaryService.swift`. The format is identical.

---

## Known Limitations and Workarounds

### File path special characters

ffmpeg/ffprobe fail on paths containing brackets `[]`, smart quotes, or curly apostrophes. The `check_path_safe()` function in `audio.py` validates paths and raises a clear error with instructions to rename. **Workaround**: Rename files/folders to remove special characters before processing. A TODO exists to fix proper escaping.

### Chapter extraction

Not all m4b files have embedded chapter markers. The tool falls back to parsing sidecar `.cue` files (common with Libation/Audible exports). If neither exists, the entire file is treated as a single chapter.

### Papermill `position_seconds` parameter

Papermill's CLI cannot parse negative default values in notebook parameter cells (e.g., `position_seconds = -1`). When driving via papermill, omit this parameter to use the notebook's default (end of chapter), or pass a positive value.

### Fixture path resolution

Notebooks use `../fixtures/{book_slug}` relative paths. When run via papermill (whose CWD is `eval/`), this resolves to `eval/fixtures/`. The notebooks include a fallback path resolver. If fixtures aren't found, check that they're in `eval/fixtures/`, not the project root.

---

## Dependencies

Defined in `pyproject.toml`:

| Package | Purpose |
|---------|---------|
| `openai-whisper` | Local transcription (alternative to Apple SpeechTranscriber) |
| `ffmpeg-python` | Audio processing helper |
| `jupyter` | Notebook environment |
| `ipywidgets` | Interactive notebook widgets |
| `tiktoken` | Token estimation proxy for Apple's tokenizer |
| `apple-fm-sdk` | Apple Foundation Models Python bindings |
| `rich` | Terminal/notebook tables |
| `pandas` | DataFrame for comparison results |
| `papermill` | Parameterized notebook execution |

**System dependency**: `ffmpeg` must be installed via `brew install ffmpeg`.

**Runtime requirement**: macOS 26+ (Tahoe), Apple Silicon, Apple Intelligence enabled.

---

## User Guide

### Jupyter Notebook Survival Guide

If you're new to Jupyter, read this section first. It will save you time.

**What is a notebook?** A notebook is a script split into "cells" that you run one at a time. Each cell can have code or text. Cells run in the order you click them, and they share state (variables, imports) with each other.

**The golden rule:** Cells depend on earlier cells. If you restart the kernel (or open the notebook fresh), you must re-run cells from the top. The most common error — `NameError: name 'X' is not defined` — means an earlier cell wasn't run yet.

#### How to read cell status

| Indicator | Meaning |
|-----------|---------|
| `In [ ]:` (empty) | Cell has never been run in this session |
| `In [*]:` (asterisk) | Cell is **currently running** — wait for it |
| `In [5]:` (number) | Cell ran successfully; it was the 5th cell executed |
| Red error block | Cell ran but hit an error — read the last line for the cause |

#### Common operations

| What you want | What to do |
|---------------|------------|
| Run everything from scratch | **Kernel → Restart & Run All** |
| Run just the cells above the current one | **Cell → Run All Above**, then run current cell |
| Re-run one cell after editing it | Click the cell, press **Shift+Enter** |
| Fix weird state / "nothing works" | **Kernel → Restart & Run All** |
| See if something is still running | Look for `In [*]` — asterisk means running |

#### External edits (Claude Code, git, VS Code)

If someone (Claude Code, a git pull, or VS Code) edits the notebook file while you have it open in Jupyter, **your browser tab won't update automatically**. You must:

1. **Close the tab** in the browser
2. Re-open the notebook from `http://localhost:8888`
3. Do **Kernel → Restart & Run All**

If you skip this, you'll be running stale code and getting confusing errors.

#### Editing the "Custom prompt" cell

The custom prompt cell near the bottom of notebook 03 is designed for quick iteration. To use it:

1. First, run all cells above it (so imports, data loading, and FM calls are done)
2. Edit the `custom_system` and `custom_user` strings
3. Press **Shift+Enter** to run just that cell
4. See results immediately below
5. Edit and re-run as many times as you want — no need to re-run earlier cells

If you get a `NameError`, it means the earlier cells lost their state. Do **Cell → Run All Above** first.

### Monitoring Progress

**In the Jupyter UI:**
- Watch `In [*]` indicators — asterisk = currently running
- Each cell prints progress messages as it runs (e.g., "Loading Whisper model...", "Calling Foundation Model...")
- FM calls typically take 3-8 seconds; Whisper transcription takes roughly 1x real-time

**In the terminal:**
- The terminal where you ran `jupyter notebook` shows a live server log — kernel activity, errors, and cell executions
- Keep this terminal visible in a side window for debugging

**For papermill (agent-driven) runs:**
- The terminal shows a progress bar: `Executing: 70%|███████ | 14/20 [00:05<00:02]`
- Output notebooks capture all cell outputs — open them in Jupyter to inspect

**What "hanging" looks like vs normal:**
- FM call on `In [*]` for 3-10 seconds = normal (model is generating)
- Whisper transcription on `In [*]` for minutes = normal (processing audio)
- Import cell on `In [*]` for more than 10 seconds = something is wrong (restart kernel)

### Initial Setup

```bash
cd eval
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install apple-fm-sdk openai-whisper jupyter tiktoken rich pandas papermill ipywidgets ffmpeg-python
```

Verify everything works:

```bash
python3 -c "import apple_fm_sdk as fm; m = fm.SystemLanguageModel(); print(m.is_available())"
```

Should print `(True, None)`.

### Workflow 1: Manual (Jupyter UI)

**Step 1 — Transcribe a book**

```bash
jupyter notebook notebooks/01_extract_and_transcribe.ipynb
```

In the first code cell, set:
- `m4b_path` — full path to your `.m4b` file (no brackets or smart quotes in the path)
- `book_slug` — short name like `"hp-book1"` (used for fixture directory)
- `chapters_to_transcribe` — list of chapter indices, e.g., `[1, 2, 3]` (empty = all)
- `whisper_model_size` — `"small"` is a good default (balance of speed and quality)

Run all cells. Transcription takes roughly 1x real-time (a 30-minute chapter takes ~3 minutes with `small`).

**Step 2 — Explore the transcript**

Open `02_explore_transcript.ipynb`, set `book_slug` and `chapter_index`, run all cells. You'll see the full timestamped transcript and stats.

**Step 3 — Test prompts**

Open `03_prompt_playground.ipynb`, set:
- `book_slug` and `chapter_index` — which transcript to use
- `window_minutes` — how many minutes of recent transcript to include (default: 5)
- `prompt_variant` — which prompt to test (e.g., `"current_bullets"`, `"v2_narrative"`)

Run all cells. You'll see:
- **Token budget analysis** — how many tokens are used by instructions vs transcript vs response
- **Transcript preview** — the exact text the model will receive
- **FM response** — the model's output with latency
- **Grounding check** — whether response claims match the transcript

The "Custom prompt" cell at the bottom lets you edit prompts inline and re-run without changing `prompts.py`.

**Step 4 — Compare all variants**

Open `04_compare_formats.ipynb` to run all prompt variants on the same transcript window and see responses side-by-side.

### Workflow 2: Agent-Driven (Claude Code)

Claude Code can drive the playground via papermill. Example commands:

**Transcribe chapters 1-3:**
```bash
papermill notebooks/01_extract_and_transcribe.ipynb notebooks/results/01_run.ipynb \
  -p m4b_path "/path/to/book.m4b" \
  -p book_slug "my-book" \
  -p whisper_model_size "small"
```

**Test a prompt variant:**
```bash
papermill notebooks/03_prompt_playground.ipynb notebooks/results/03_run.ipynb \
  -p book_slug "my-book" \
  -p chapter_index 3 \
  -p window_minutes 5.0 \
  -p prompt_variant "v2_narrative"
```

**Compare all variants:**
```bash
papermill notebooks/04_compare_formats.ipynb notebooks/results/04_run.ipynb \
  -p book_slug "my-book" \
  -p chapter_index 3 \
  -p window_minutes 5.0
```

Output notebooks are saved in `notebooks/results/` and can be opened in Jupyter or VS Code for visual inspection.

### Reading the Outputs

**Token budget table** — Shows how the 4096-token context window is allocated. Key numbers:
- `Instruction tokens`: Fixed cost of the prompt template
- `Transcript tokens`: How much transcript text fits
- `Sentences dropped`: If > 0, the window was too large and oldest sentences were trimmed

**FM response** — The model's actual output. Compare across variants for tone, detail, and accuracy.

**Grounding check** — Each sentence in the response is matched against the transcript using fuzzy substring matching. A score of 0.6+ means grounded. Low scores mean the model may be paraphrasing heavily or hallucinating. Note: the threshold may need tuning — correct paraphrases can score below 0.6.

**Calibration results** — Run once to measure the actual context window. The `effective_tiktoken_limit` tells you the max tiktoken token count you can safely use.

---

## Guide for LLM Agents

This section is for any AI agent that picks up this tool in the future.

### How to run a prompt test

1. Ensure the venv is activated: `cd eval && source .venv/bin/activate`
2. Check if fixtures exist: `ls fixtures/<book-slug>/transcript_ch*.json`
3. If no fixtures, run notebook 01 first via papermill
4. Run notebook 03 via papermill with desired parameters
5. Read the output notebook to see results

### How to add a new prompt variant

1. Add `NEW_VARIANT_SYSTEM` and `NEW_VARIANT_USER` constants to `lib/prompts.py`
2. Add an entry to the `PROMPTS` dict: `"new_variant": (NEW_VARIANT_SYSTEM, NEW_VARIANT_USER)`
3. The `{transcript}` placeholder in the user prompt is required
4. Test it: `papermill notebooks/03_prompt_playground.ipynb results/test.ipynb -p prompt_variant "new_variant" -p book_slug "hp-book1-ss" -p chapter_index 1`

### How to add a new book fixture

1. Get an m4b file with clean path (no brackets/smart quotes)
2. Choose a slug (e.g., `"my-book"`)
3. Run: `papermill notebooks/01_extract_and_transcribe.ipynb results/transcribe.ipynb -p m4b_path "/path/to/file.m4b" -p book_slug "my-book"`
4. Fixtures appear in `fixtures/my-book/`

### How the modules connect

```
User provides: m4b file path, book slug
         ↓
audio.py: extract chapters (ffprobe + cue fallback) → Chapter objects
audio.py: extract chapter audio (ffmpeg) → WAV files
         ↓
whisper_transcribe.py: transcribe WAV → TranscribedSentence list → JSON fixture
         ↓
transcript.py: load fixture → select_window(position, minutes) → sentence slice
         ↓
prompts.py: get_prompt(variant, transcript_text) → combined prompt string
token_budget.py: allocate_budget(instructions, sentences) → BudgetResult (trim if needed)
         ↓
fm_client.py: call_model(prompt) → response string
fm_client.py: call_model_structured(prompt, schema) → typed object
         ↓
evaluate.py: check_grounding(response, transcript) → grounding report
evaluate.py: run_comparison(sentences, variants) → DataFrame
```

### Key API signatures

```python
# Transcribe
model = load_model("small")
sentences = transcribe_and_save(wav_path, fixture_path, model=model, chapter_offset=0.0)

# Load and window
sentences = load_fixture("fixtures/book/transcript_ch01.json")
window = select_window(sentences, position=1800.0, window_minutes=5.0)

# Budget
budget = allocate_budget(instructions_text, window, context_limit=4096)

# Prompt
combined = get_prompt("v2_narrative", format_transcript(budget.included_sentences))

# Call FM
response = await call_model(combined)
response, latency = await call_model_timed(combined)

# Evaluate
grounding = check_grounding(response, transcript_text)
df = await run_comparison(window, ["current_bullets", "v2_narrative"])
```

### Important behaviors to know

- `call_model()` and `call_model_timed()` are **async** — notebooks handle this natively, but CLI scripts need `asyncio.run()`
- `allocate_budget()` packs sentences newest-to-oldest and drops the oldest if over budget
- The FM SDK returns strings directly (not `.content` objects like Swift)
- `check_grounding()` uses difflib fuzzy matching, not semantic similarity — threshold may need tuning
- Whisper's `small` model is the default; `medium` or `large` give better accuracy but are slower

---

## Existing Fixtures

| Slug | Book | Chapters transcribed | Notes |
|------|------|---------------------|-------|
| `hp-book1-ss` | Harry Potter and the Sorcerer's Stone (Full-Cast Edition) | All 19 (ch00–ch18) | Full-cast edition, chapters extracted via cue file |

---

## Relationship to Other Docs

These documents live in the parent AudioBook Player project (`docs/technical/`):

- **WDIM_V2_PLAN.md** — Product plan that this tool supports. Section A.8 ("Build an evaluation harness") is implemented here.
- **LLM_INSIGHTS_VS_WDIM.md** — Comparison of Library Insights and WDIM features. The eval playground tests both prompt families.
- **WHAT_DID_I_MISS.md** — Original WDIM feature spec.
- **MissedSummaryService.swift** — The Swift production code. Prompts in `lib/prompts.py` are exact copies and can be ported back directly.

When this tool is extracted to a standalone repo, copies of the relevant docs should be placed in `docs/reference/`.
