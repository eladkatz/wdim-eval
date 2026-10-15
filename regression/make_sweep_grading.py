import json, pathlib, random, sys, collections

ROOT = pathlib.Path(__file__).parent
label, jobs_file, results_file = sys.argv[1], sys.argv[2], sys.argv[3]
sys.argv = [sys.argv[0]]
namespace = {"__file__": str(ROOT / "align_ebook.py")}
exec((ROOT / "align_ebook.py").read_text().split("words, chapters = load_book()")[0], namespace)
load_book, norm, best_offset = namespace["load_book"], namespace["norm"], namespace["best_offset"]
words, _ = load_book()
book_norm = [norm(w) for w in words]
alignment = json.load(open(ROOT / "tog_ebook_alignment.json"))
CHAR_FILES = {"tog": "tog_characters.json", "starsight": "starsight_characters.json",
              "defiant": "defiant_characters.json", "wizard": "wizard_characters.json"}

def normalized(text):
    return [w for w in (norm(x) for x in text.split()) if w]

full_spans = {}
def ebook_span(case, window):
    if case not in full_spans:
        full_start, _ = best_offset(book_norm, normalized(alignment[case]["ebook_text"])[:60])
        full_spans[case] = (full_start, full_start + alignment[case]["ebook_words"])
    full_start, full_end = full_spans[case]
    probe = normalized(window)
    start, _ = best_offset(book_norm, probe[:60], max(0, full_start - 50))
    end_start, _ = best_offset(book_norm, probe[-60:], start)
    return " ".join(words[start:min(end_start + 60, full_end)])

jobs = {j["id"]: j for j in json.load(open(ROOT / jobs_file))}
results = [json.loads(l) for l in open(ROOT / results_file)]
random.seed(hash(label) % 10000)
key, cases = {}, collections.defaultdict(lambda: {"bases": {}, "recaps": []})
for r in results:
    job = jobs[r["id"]]
    case = cases[job["case"]]
    case["book"] = job["book"]
    basis = job["arm"]
    if basis not in case["bases"]:
        entry = {"transcript": job["window"]}
        if job["book"] == "tog":
            entry["ebook_text"] = ebook_span(job["case"], job["window"])
        case["bases"][basis] = entry
    rid = f"{label[0].upper()}{random.randint(100000, 999999)}"
    key[rid] = {"case": job["case"], "arm": job["arm"], "run": r["run"]}
    text = r.get("text") if r["outcome"] == "success" else f"[GENERATION ERROR: {r.get('error', '')[:120]}]"
    case["recaps"].append({"recap_id": rid, "basis": basis, "text": text})

package = []
for case_id, case in cases.items():
    random.shuffle(case["recaps"])
    names = list(case["bases"])
    random.shuffle(names)
    alias = {name: f"S{i + 1}" for i, name in enumerate(names)}
    for recap in case["recaps"]:
        recap["basis"] = alias[recap["basis"]]
    reference = []
    if case["book"] in CHAR_FILES:
        chars = json.load(open(ROOT / CHAR_FILES[case["book"]]))["characters"]
        reference = [f"{c['name']} (aliases: {', '.join(c.get('aliases', []))}): {c['bio']}" for c in chars]
    package.append({"case_id": case_id, "character_reference": reference,
                    "stretches": {alias[n]: case["bases"][n] for n in names}, "recaps": case["recaps"]})

json.dump(package, open(ROOT / f"{label}_grading_package.json", "w"), indent=1)
json.dump(key, open(ROOT / f"{label}_grading_key.json", "w"), indent=1)
print(label, len(package), "cases;", sum(len(c["recaps"]) for c in package), "recaps")
