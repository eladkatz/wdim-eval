import json, pathlib, collections

ROOT = pathlib.Path(__file__).parent
key = json.load(open(ROOT / "grading_key.json"))
grades = []
for part in ("grades_part1.json", "grades_part2.json"):
    path = ROOT / part
    if path.exists():
        grades += json.load(open(path))["grades"]

ARMS = ["A_prod_full", "B_prod_short", "E_revised_short", "C_revised_bg_short", "D_revised_bg_full"]
by_arm = collections.defaultdict(list)
by_case_arm = collections.defaultdict(lambda: collections.defaultdict(list))
types = collections.defaultdict(collections.Counter)
for g in grades:
    k = key[g["recap_id"]]
    by_arm[k["arm"]].append(g)
    by_case_arm[k["case"]][k["arm"]].append(g)
    for e in g["errors"]:
        if e.get("severity") == "major":
            types[k["arm"]][e.get("type", "other")] += 1

print(f"{'arm':22s} n  misleading  clean  major/recap  minor/recap  major types")
for arm in ARMS:
    gs = by_arm[arm]
    if not gs:
        continue
    n = len(gs)
    misleading = sum(g["misleading"] for g in gs)
    clean = sum(1 for g in gs if g["major_count"] == 0 and g["minor_count"] == 0)
    print(f"{arm:22s} {n:2d}  {misleading:2d} ({misleading / n:4.0%})  {clean:2d} ({clean / n:4.0%})  "
          f"{sum(g['major_count'] for g in gs) / n:5.2f}  {sum(g['minor_count'] for g in gs) / n:5.2f}  {dict(types[arm])}")

print("\nmisleading recaps per case (out of 3 runs):")
print(f"{'case':8s} " + " ".join(f"{a.split('_')[0]:>3s}" for a in ARMS))
for case, arms in sorted(by_case_arm.items()):
    print(f"{case:8s} " + " ".join(f"{sum(g['misleading'] for g in arms.get(a, [])):>3d}" for a in ARMS))
