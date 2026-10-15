import json, re, pathlib, sys

ROOT = pathlib.Path(__file__).parent
sys.argv = [sys.argv[0]]
namespace = {"__file__": str(ROOT / "build_arms.py")}
exec((ROOT / "build_arms.py").read_text().split("excerpts = load_excerpts()")[0], namespace)
load_excerpts, background, BOOKS, REVISED = (namespace[k] for k in ("load_excerpts", "background", "BOOKS", "REVISED"))

WORDS_PER_MINUTE = 160
MIN_CURRENT = 3 * WORDS_PER_MINUTE
TARGET = 4 * WORDS_PER_MINUTE
CASES = {"ahIMQ1": "tog", "nVw06Z": "tog", "tlHQ1O": "tog", "9gjvwx": "unknown"}
CHAPTER = re.compile(r"(?<=[.!?] )Chapter (\d+|[A-Z][a-z]+)\b")

INSTRUCTIONS = REVISED + "\nA context section, if present, comes from a neighboring chapter. Use it only to understand the passage. Do not recap it."

def word_index(text, char_pos):
    return len(text[:char_pos].split())

excerpts = load_excerpts()
jobs, meta = [], {}
for case, book_key in CASES.items():
    text = excerpts[case]
    words = text.split()
    match = list(CHAPTER.finditer(text))[-1]
    cut = word_index(text, match.start())
    current, previous = words[cut:], words[:cut]
    if len(current) >= MIN_CURRENT:
        target, other, label = current[-TARGET:], previous[-TARGET:], "PREVIOUS"
        branch = "current_chapter"
    else:
        target, other, label = previous[-TARGET:], current, "NEXT"
        branch = "previous_chapter"
    target_text, other_text = " ".join(target), " ".join(other)
    bg = background(BOOKS[book_key], target_text)
    head = f"BACKGROUND\n{bg}\n\n" if bg else ""
    rule_only = f"{head}PASSAGE\n{target_text}"
    with_context = (f"{head}CONTEXT FROM THE {label} CHAPTER (for understanding only, do not recap)\n{other_text}\n\n"
                    f"PASSAGE\n{target_text}")
    meta[case] = {"branch": branch, "words_into_current": len(current), "target": target_text,
                  "context": other_text, "context_label": label, "book": book_key}
    jobs.append({"id": f"{case}|R_rule", "instructions": INSTRUCTIONS, "text": rule_only})
    jobs.append({"id": f"{case}|RC_rule_context", "instructions": INSTRUCTIONS, "text": with_context})
    print(case, match.group(0), "| words into current chapter:", len(current), "| branch:", branch,
          "| target words:", len(target), "| context words:", len(other))

json.dump(jobs, open(ROOT / "context_jobs.json", "w"))
json.dump(meta, open(ROOT / "context_meta.json", "w"), indent=1)
