import json, re, pathlib, sys

ROOT = pathlib.Path(__file__).parent
sys.argv = [sys.argv[0]]
namespace = {"__file__": str(ROOT / "build_arms.py")}
source = (ROOT / "build_arms.py").read_text().split("excerpts = load_excerpts()")[0]
exec(source, namespace)
load_excerpts, background, with_background = namespace["load_excerpts"], namespace["background"], namespace["with_background"]
BOOKS, CASES, REVISED = namespace["BOOKS"], namespace["CASES"], namespace["REVISED"]

WORDS_PER_MINUTE = 160
MINUTES = [2, 3, 4, 5, 7, 10]

def tail_words(text, count):
    words = text.split()
    if len(words) <= count:
        return text
    tail = " ".join(words[-count:])
    match = re.search(r"[.!?]\s+([A-Z])", tail)
    return tail[match.start(1):] if match and match.start(1) < 300 else tail

excerpts = load_excerpts()
sweep = []
for case_id, book_key in CASES.items():
    full = excerpts[case_id]
    for minutes in MINUTES:
        window = full if minutes == 10 else tail_words(full, minutes * WORDS_PER_MINUTE)
        sweep.append({"id": f"{case_id}|C_sweep_{minutes:02d}min", "instructions": REVISED,
                      "text": with_background(BOOKS[book_key], window),
                      "case": case_id, "arm": f"C_sweep_{minutes:02d}min", "book": book_key, "window": window})

alignment = json.load(open(ROOT / "tog_ebook_alignment.json"))
split = []
for case_id, info in alignment.items():
    if not info["chapter_breaks_inside"]:
        continue
    words = excerpts[case_id].split()
    cut = info["chapter_breaks_inside"][0]["words_into_window"]
    for part, segment in (("before", " ".join(words[:cut])), ("after", " ".join(words[cut:]))):
        split.append({"id": f"{case_id}|S_split_{part}", "instructions": REVISED,
                      "text": with_background(BOOKS["tog"], segment),
                      "case": case_id, "arm": f"S_split_{part}", "book": "tog", "window": segment})

arms = [p for p in json.load(open(ROOT / "arms_passages.json")) if p["arm"] != "C_revised_bg_short"]
json.dump(sweep + split, open(ROOT / "mac_sweep_jobs.json", "w"))
json.dump(arms + sweep, open(ROOT / "device_jobs.json", "w"))
print("mac sweep+split prompts:", len(sweep) + len(split), "| device prompts:", len(arms) + len(sweep))
