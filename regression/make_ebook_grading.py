import json, pathlib, sys

ROOT = pathlib.Path(__file__).parent
sys.argv = [sys.argv[0]]
source = (ROOT / "align_ebook.py").read_text().split("words, chapters = load_book()")[0]
namespace = {"__file__": str(ROOT / "align_ebook.py")}
exec(source, namespace)
load_book, norm, best_offset = namespace["load_book"], namespace["norm"], namespace["best_offset"]

words, _ = load_book()
book_norm = [norm(w) for w in words]
alignment = json.load(open(ROOT / "tog_ebook_alignment.json"))
passages = {(p["case"], p["arm"]): p for p in json.load(open(ROOT / "arms_passages.json"))}
package = {p["case_id"]: p for p in json.load(open(ROOT / "grading_package.json"))}

def normalized(text):
    return [w for w in (norm(x) for x in text.split()) if w]

out = []
for case, info in alignment.items():
    full = normalized(passages[(case, "A_prod_full")]["window"])
    full_start, _ = best_offset(book_norm, full[:60])
    full_end = full_start + info["ebook_words"]
    short = normalized(passages[(case, "B_prod_short")]["window"])
    short_start, quality = best_offset(book_norm, short[:60], full_start)
    out.append({
        "case_id": case,
        "ebook_reference": {"FULL": " ".join(words[full_start:full_end]),
                            "SHORT": " ".join(words[short_start:full_end])},
        "recaps": package[case]["recaps"],
    })
    print(case, "short alignment", round(quality, 2), "short words", full_end - short_start)

json.dump(out, open(ROOT / "ebook_grading_package.json", "w"), indent=1)
