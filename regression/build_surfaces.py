import json, re, pathlib, sys

ROOT = pathlib.Path(__file__).parent
sys.argv = [sys.argv[0]]
namespace = {"__file__": str(ROOT / "build_arms.py")}
exec((ROOT / "build_arms.py").read_text().split("excerpts = load_excerpts()")[0], namespace)
load_excerpts, background, cast_for, BOOKS, CASES = (namespace[k] for k in
    ("load_excerpts", "background", "cast_for", "BOOKS", "CASES"))

WPM = 160
CHAPTER = re.compile(r"(?<=[.!?] )Chapter (\d+|[A-Z][a-z]+)\b")

def tail(words, count):
    return " ".join(words[-count:]) if len(words) > count else " ".join(words)

def split_at_chapter(text):
    words = text.split()
    marks = list(CHAPTER.finditer(text))
    if not marks:
        return [], words
    cut = len(text[:marks[-1].start()].split())
    return words[:cut], words[cut:]

def chapter_rule(text, target_words, min_current_words):
    previous, current = split_at_chapter(text)
    if not previous or len(current) >= min_current_words:
        return tail(current, target_words)
    return tail(previous, target_words)

def chapter_clamp(text, target_words):
    _, current = split_at_chapter(text)
    return tail(current, target_words)

def last_sentence_split(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:-1]), parts[-1]

def characters(book_key):
    file = BOOKS[book_key]["chars"]
    return json.load(open(ROOT / file))["characters"] if file else []

def whos_who(window, book_key):
    out = []
    for c in characters(book_key):
        names = [c["name"]] + c.get("aliases", [])
        if any(len(n.strip()) > 3 and re.search(r"\b" + re.escape(n.strip()) + r"\b", window, re.I) for n in names):
            out.append(f"{c['name']} \u2014 {c['bio']}" if c.get("bio") else c["name"])
            if len(out) >= 8:
                break
    return out

def matched_names(window, book_key):
    return [entry.split(" \u2014 ")[0] for entry in whos_who(window, book_key)]

def people_block(window, book_key):
    lines = cast_for(window, BOOKS[book_key]["chars"])
    return ("People mentioned in the passage:\n" + "\n".join(lines)) if lines else ""

def book_title_line(book_key):
    line = BOOKS[book_key]["line"]
    return line.split(" (")[0].split(". Genre")[0] if line else "Unknown title by Unknown author"

LM_CURRENT = """You are a friendly audiobook assistant. Summarize what was happening when the listener last stopped.

Respond with exactly 2-3 sentences in a casual, friendly tone. Describe the last thing that happened in the story based on the excerpt. Do not use bullet points, headers, or any special formatting. Just write a short paragraph.

Rules:
- Only use information from the provided excerpt
- Focus on the most recent events (the end of the excerpt)
- Be concise and natural, as if telling a friend what just happened
- Do not speculate beyond what's in the text"""
LM_REVISED = """You remind an audiobook listener what was happening when they last stopped listening.
The passage is an automatic speech-to-text transcript. It has no speaker labels, and names may be misspelled.
Write 2 to 3 short, plain sentences about what was happening at the end of the passage.
Only say what the passage clearly shows. If you are not sure who did or said something, describe it without naming them.
Never add relationships, motives, or events that are not in the passage.
The background is only for recognizing people and places. Do not recap it.
Start directly with the recap."""

W_CURRENT = """A listener is resuming an audiobook after a break. In ONE or TWO sentences, present tense, tell them what is happening RIGHT NOW at the point they stopped, so they can dive straight back in.

Start with the people or the action \u2014 not with framing. Use the WHO'S WHO names so everyone is named correctly. Name the specific thing in play \u2014 the object, place, destination, or goal that matters at this exact moment \u2014 not just that people are talking, moving, or fighting. Write it like you're nudging a friend back into the scene they were in. Describe the scene in your own words \u2014 what people are doing, not what they're saying.

Never do any of these:
- name the book, the chapter, or say "this passage"
- begin with "At the end", "In this", "The story", "Currently", "RECENT", "The narrator"
- summarize earlier events or describe the book overall
- restate or explain the WHO'S WHO entries

Inputs: WHO'S WHO (who people are \u2014 for naming only), BOOK (ignore for content), RECENT (the verbatim end of what they heard \u2014 base everything on this)."""
W_REVISED = """You help a listener jump back into an audiobook after a break.
The passage is an automatic speech-to-text transcript. It has no speaker labels, and names may be misspelled.
In one or two short sentences, present tense, say what is happening at the end of the passage: who is there and what they are doing.
Only say what the passage clearly shows. If you are not sure who did or said something, describe it without naming them.
Never add relationships, motives, or events that are not in the passage.
The background is only for recognizing people. Do not mention or recap it.
Start directly with the people or the action."""

B_CURRENT = """You help an audiobook listener remember why a moment mattered. Later they will revisit one line they bookmarked \u2014 they already see that line. Your job is to remind them what was going on around it.

The transcript below ends at the bookmarked line, between <<MARK>> and <</MARK>>.

In 2\u20133 plain sentences, describe what is happening and who is involved as this moment arrives \u2014 the context that makes the bookmarked line land.

- Do NOT repeat or paraphrase the bookmarked line itself.
- Use ONLY the transcript below \u2014 no outside knowledge, no guessing ahead.
- No preamble; do not include the <<MARK>> tags."""
B_REVISED = """You help an audiobook listener remember why a bookmarked moment mattered. They already see the bookmarked line, which is marked <<MARK>> and <</MARK>> at the end of the transcript.
The transcript is automatic speech-to-text. It has no speaker labels, and names may be misspelled.
In 2 to 3 short, plain sentences, describe what is happening and who is involved as this moment arrives.
Only say what the transcript clearly shows. If you are not sure who did or said something, describe it without naming them.
Never add relationships, motives, or events that are not in the transcript. Do not repeat the bookmarked line.
The background is only for recognizing people. Do not recap it.
Start directly with the recap. Do not include the <<MARK>> tags."""

def wdim_style_background(book_key, window):
    bg = background(BOOKS[book_key], window)
    return f"BACKGROUND\n{bg}\n\n" if bg else ""

jobs = []
def add(case, book, arm, instructions, text, window, max_tokens):
    jobs.append({"id": f"{case}|{arm}", "case": case, "book": book, "arm": arm, "instructions": instructions,
                 "text": text, "window": window, "maxTokens": max_tokens})

excerpts = load_excerpts()
for case, book in CASES.items():
    full = excerpts[case]

    lm_current = tail(full.split(), 3 * WPM)
    lm_rule = chapter_rule(full, 3 * WPM, 3 * WPM)
    lm_people = people_block(lm_rule, book)
    add(case, book, "LM_current", LM_CURRENT,
        f"What was the last thing that happened in this audiobook excerpt?\n\n{lm_current}", lm_current, 220)
    add(case, book, "LM_486", LM_CURRENT,
        "What was the last thing that happened in this audiobook excerpt?\n\n"
        + (f"{lm_people}\n\n" if lm_people else "") + lm_rule, lm_rule, 220)
    add(case, book, "LM_487", LM_REVISED, f"{wdim_style_background(book, lm_rule)}PASSAGE\n{lm_rule}", lm_rule, 220)

    w_current = full
    w_rule = chapter_rule(full, 4 * WPM, 3 * WPM)
    def widget_prompt(window):
        parts = []
        bios = whos_who(window, book)
        if bios:
            parts.append("WHO'S WHO:\n" + "\n".join(f"- {b}" for b in bios))
        parts.append(f"BOOK: {book_title_line(book)}")
        parts.append(f"RECENT:\n{window}")
        return "\n\n".join(parts)
    add(case, book, "W_current", W_CURRENT, widget_prompt(w_current), w_current, 60)
    add(case, book, "W_486", W_CURRENT, widget_prompt(w_rule), w_rule, 60)
    add(case, book, "W_487", W_REVISED, f"{wdim_style_background(book, w_rule)}PASSAGE\n{w_rule}", w_rule, 60)

    b_window = chapter_clamp(full, 3 * WPM)
    pre, marked = last_sentence_split(b_window)
    transcript = f"{pre} <<MARK>>{marked}<</MARK>>".strip()
    meta = f"Book: {book_title_line(book)}"
    if BOOKS[book]["premise"]:
        meta += f"\nAbout: {BOOKS[book]['premise'][:250]}"
    names = matched_names(b_window, book)
    current_meta = meta + (f"\nPossible nearby character names (may be approximate): {', '.join(names)}" if names else "")
    people = people_block(b_window, book)
    add(case, book, "B_current", B_CURRENT, f"{current_meta}\n\nTranscript:\n{transcript}", b_window, 200)
    add(case, book, "B_486", B_CURRENT, f"{meta}" + (f"\n{people}" if people else "") + f"\n\nTranscript:\n{transcript}",
        b_window, 200)
    add(case, book, "B_487", B_REVISED, f"{meta}" + (f"\n{people}" if people else "") + f"\n\nTranscript:\n{transcript}",
        b_window, 200)

json.dump(jobs, open(ROOT / "surface_jobs.json", "w"))
print(len(jobs), "prompts")
for j in jobs[:9]:
    print(j["id"], len(j["window"].split()), "window words")
