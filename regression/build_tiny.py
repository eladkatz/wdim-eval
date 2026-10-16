import json, re, pathlib, sys

ROOT = pathlib.Path(__file__).parent
sys.argv = [sys.argv[0]]
namespace = {"__file__": str(ROOT / "build_arms.py")}
exec((ROOT / "build_arms.py").read_text().split("excerpts = load_excerpts()")[0], namespace)
load_excerpts, with_background, BOOKS, CASES, REVISED = (namespace[k] for k in
    ("load_excerpts", "with_background", "BOOKS", "CASES", "REVISED"))

SIZES = [1, 2, 3, 5, 8]
CHAPTER = re.compile(r"(?<=[.!?] )Chapter (\d+|[A-Z][a-z]+)\b")
SYNTHETIC = {
    "credits_starsight": ("starsight", "Audible Studios presents Starsight by Brandon Sanderson, narrated by Suzy Jackson."),
    "chapter_heading": ("unknown", "Chapter One."),
    "credits_tog": ("tog", "Throne of Glass by Sarah J. Maas. Read by Elizabeth Evans."),
    "heading_plus_line": ("tog", "Chapter One. After a year of slavery in the Salt Mines of Endovier, Celaena Sardothien was accustomed to being escorted everywhere in chains and at sword-point."),
}

def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]

jobs = []
excerpts = load_excerpts()
for case, book in CASES.items():
    text = excerpts[case]
    marks = list(CHAPTER.finditer(text))
    start_text = text[marks[-1].start():] if marks else text
    parts = sentences(start_text)
    for n in SIZES:
        snippet = " ".join(parts[:n])
        jobs.append({"id": f"{case}|tiny_{n:02d}s", "case": case, "book": book, "arm": f"tiny_{n:02d}s",
                     "words": len(snippet.split()), "instructions": REVISED,
                     "text": with_background(BOOKS[book], snippet), "window": snippet, "maxTokens": 220})
for key, (book, snippet) in SYNTHETIC.items():
    jobs.append({"id": f"{key}|synthetic", "case": key, "book": book, "arm": "synthetic",
                 "words": len(snippet.split()), "instructions": REVISED,
                 "text": with_background(BOOKS[book], snippet), "window": snippet, "maxTokens": 220})

json.dump(jobs, open(ROOT / "tiny_jobs.json", "w"))
print(len(jobs), "prompts")
for size in SIZES:
    words = [j["words"] for j in jobs if j["arm"] == f"tiny_{size:02d}s"]
    print(f"{size} sentences: {min(words)}-{max(words)} words")
