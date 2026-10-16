import json, pathlib, sys, collections, glob

ROOT = pathlib.Path(__file__).parent
label = sys.argv[1]
key = json.load(open(ROOT / f"{label}_grading_key.json"))
grades = [g for path in sorted(glob.glob(str(ROOT / f"{label}_grades_part*.json"))) for g in json.load(open(path))["grades"]]
TOG = {"4GfFVI", "TIPJdZ", "ahIMQ1", "eZ6fzf", "nVw06Z", "tlHQ1O"}
CROSSING = {"ahIMQ1", "nVw06Z", "tlHQ1O"}

by_arm = collections.defaultdict(list)
for g in grades:
    k = key.get(g["recap_id"])
    if k:
        by_arm[k["arm"]].append((k, g))

def row(name, items):
    n = len(items)
    if not n:
        return
    mis = sum(g["misleading"] for _, g in items)
    clean = sum(1 for _, g in items if g["major_count"] == 0 and g["minor_count"] == 0)
    fmt = sum(bool(g.get("format_issue")) for _, g in items)
    tog = [(k, g) for k, g in items if k["case"] in TOG]
    tog_mis = sum(g["misleading"] for _, g in tog)
    print(f"{name:22s} n={n:3d}  misleading {mis:3d} ({mis / n:4.0%})  clean {clean:3d} ({clean / n:4.0%})  "
          f"format {fmt:2d}  | ToG misleading {tog_mis}/{len(tog)}")

print(f"== {label}: {len(grades)} graded")
for arm in sorted(by_arm):
    row(arm, by_arm[arm])

crossing_full = [(k, g) for arm in ("C_sweep_10min", "C_sweep_07min") for k, g in by_arm.get(arm, []) if k["case"] in CROSSING]
if crossing_full:
    row("crossing 7+10min", crossing_full)
split = by_arm.get("S_split_before", []) + by_arm.get("S_split_after", [])
if split:
    pairs = collections.defaultdict(list)
    for k, g in split:
        pairs[(k["case"], k["run"])].append(g)
    combined = sum(any(g["misleading"] for g in gs) for gs in pairs.values())
    print(f"split pairs (before+after shown together): misleading {combined}/{len(pairs)}")
