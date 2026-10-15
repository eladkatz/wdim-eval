import json, random, pathlib, collections

ROOT = pathlib.Path(__file__).parent
passages = {p["id"]: p for p in json.load(open(ROOT / "arms_passages.json"))}
results = [json.loads(l) for l in open(ROOT / "arms_results.jsonl")]
CHAR_FILES = {"tog": "tog_characters.json", "starsight": "starsight_characters.json",
              "defiant": "defiant_characters.json", "wizard": "wizard_characters.json"}

random.seed(442)
key = {}
cases = collections.defaultdict(lambda: {"windows": {}, "recaps": []})
for r in results:
    p = passages[r["id"]]
    case = cases[p["case"]]
    basis = "SHORT" if "short" in p["arm"] else "FULL"
    case["windows"][basis] = p["window"]
    case["book"] = p["book"]
    rid = f"R{random.randint(100000, 999999)}"
    key[rid] = {"case": p["case"], "arm": p["arm"], "run": r["run"]}
    text = r.get("text") if r["outcome"] == "success" else f"[GENERATION ERROR: {r.get('error', '')[:120]}]"
    case["recaps"].append({"recap_id": rid, "based_on": basis, "text": text})

package = []
for case_id, case in cases.items():
    random.shuffle(case["recaps"])
    reference = []
    if case["book"] in CHAR_FILES:
        chars = json.load(open(ROOT / CHAR_FILES[case["book"]]))["characters"]
        reference = [f"{c['name']} (aliases: {', '.join(c.get('aliases', []))}): {c['bio']}" for c in chars]
    package.append({"case_id": case_id, "character_reference": reference,
                    "windows": case["windows"], "recaps": case["recaps"]})

json.dump(package, open(ROOT / "grading_package.json", "w"), indent=1)
json.dump(key, open(ROOT / "grading_key.json", "w"), indent=1)
print(len(package), "cases;", sum(len(c["recaps"]) for c in package), "recaps")
