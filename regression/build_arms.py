import json, os, re, random, html, pathlib

ROOT = pathlib.Path(__file__).parent
FEEDBACK_DUMP = os.environ.get("WDIM_FEEDBACK_DUMP", str(ROOT / "private" / "feedback_dump.yaml"))
SHORT_WORDS = 640  # about 4 minutes of narration

PRODUCTION = (
    "You are a voice audiobook assistant.\n"
    "Give a detailed, natural spoken recap of what the listener missed and nothing else, limited to 2-4 sentences."
)
REVISED = (
    "You recap audiobook passages for a listener who zoned out.\n"
    "The passage is an automatic speech-to-text transcript. It has no speaker labels, and names may be misspelled.\n"
    "Write 2 to 4 short, plain sentences about what happens in the passage, in the order it happens.\n"
    "Only say what the passage clearly shows. If you are not sure who did or said something, describe it without naming them.\n"
    "Never add relationships, motives, or events that are not in the passage.\n"
    "The background is only for recognizing people and places. Do not recap it.\n"
    "Start directly with the recap."
)

STARSIGHT_PREMISE = (
    "All her life, Spensa has dreamed of becoming a pilot. She made it to the sky, but the truths she learned "
    "about her father were crushing: he deserted his flight during battle against the Krell and attacked his team. "
    "Spensa is sure there's more to the story. Everything she has been taught about her world is a lie, and she'll "
    "travel to the end of the galaxy to save humankind if she needs to."
)

BOOKS = {
    "tog": {"line": "Throne of Glass by Sarah J. Maas", "premise": None, "chars": "tog_characters.json"},
    "starsight": {"line": "Starsight by Brandon Sanderson (The Skyward Series, book 2). Genre: young adult science fiction.",
                  "premise": STARSIGHT_PREMISE, "chars": "starsight_characters.json"},
    "defiant": {"line": "Defiant by Brandon Sanderson", "premise": None, "chars": "defiant_characters.json"},
    "wizard": {"line": "Off to Be the Wizard by Scott Meyer", "premise": None, "chars": "wizard_characters.json"},
    "unknown": {"line": None, "premise": None, "chars": None},
}
CASES = {
    "4GfFVI": "tog", "TIPJdZ": "tog", "ahIMQ1": "tog", "eZ6fzf": "tog", "nVw06Z": "tog", "tlHQ1O": "tog",
    "0FaGjC": "starsight", "gdj4Qv": "defiant", "yUYiRq": "wizard", "9gjvwx": "unknown",
}

def load_excerpts():
    import yaml
    data = yaml.safe_load(open(FEEDBACK_DUMP).read())
    out = {}
    for d in data["documents"]:
        doc_id = d["__path__"].split("/")[-1][:6]
        if doc_id in CASES and d.get("logs"):
            out[doc_id] = json.loads(d["logs"])["transcript_excerpt"]
    return out

def short_window(text):
    words = text.split()
    if len(words) <= SHORT_WORDS:
        return text
    tail = " ".join(words[-SHORT_WORDS:])
    match = re.search(r"[.!?]\s+([A-Z])", tail)
    return tail[match.start(1):] if match and match.start(1) < 400 else tail

def cast_for(window, chars_file):
    if not chars_file:
        return []
    characters = json.load(open(ROOT / chars_file))["characters"]
    lowered = window.lower()
    picked = []
    for c in characters:
        forms = [c["name"]] + c.get("aliases", [])
        heard, count = [], 0
        for form in forms:
            hits = len(re.findall(r"\b" + re.escape(form.lower()) + r"\b", lowered))
            if hits:
                heard.append(form)
                count += hits
        if count:
            picked.append((count, c, heard))
    picked.sort(key=lambda x: -x[0])
    lines = []
    for _, c, heard in picked[:8]:
        variants = [h for h in heard if h != c["name"]]
        also = f" (heard as: {', '.join(variants)})" if variants else ""
        lines.append(f"- {c['name']}{also}: {c['bio']}")
    return lines

def background(book, window):
    parts = []
    if book["line"]:
        parts.append(f"Book: {book['line']}")
    if book["premise"]:
        parts.append(f"Premise: {book['premise']}")
    cast = cast_for(window, book["chars"])
    if cast:
        parts.append("People mentioned in the passage:\n" + "\n".join(cast))
    return "\n".join(parts)

def with_background(book, window):
    bg = background(book, window)
    return (f"BACKGROUND\n{bg}\n\nPASSAGE\n{window}") if bg else f"PASSAGE\n{window}"

excerpts = load_excerpts()
passages = []
for case_id, book_key in CASES.items():
    full = excerpts[case_id]
    short = short_window(full)
    book = BOOKS[book_key]
    arms = {
        "A_prod_full": (PRODUCTION, full),
        "B_prod_short": (PRODUCTION, short),
        "E_revised_short": (REVISED, f"PASSAGE\n{short}"),
        "C_revised_bg_short": (REVISED, with_background(book, short)),
        "D_revised_bg_full": (REVISED, with_background(book, full)),
    }
    for arm, (instructions, prompt) in arms.items():
        passages.append({"id": f"{case_id}|{arm}", "instructions": instructions, "text": prompt,
                         "case": case_id, "arm": arm, "book": book_key, "window": short if "short" in arm else full})

json.dump(passages, open(ROOT / "arms_passages.json", "w"))
print(len(passages), "prompts")
sample = next(p for p in passages if p["id"] == "ahIMQ1|C_revised_bg_short")
print(sample["text"][:1500])
