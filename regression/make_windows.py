import json, re, pathlib, sys

ROOT = pathlib.Path(__file__).parent
BOOKS = ROOT / "books"
WINDOW = 1500
STEP = 250
PER_BOOK = 3
KEYWORDS = re.compile(
    r"\b(blood\w*|bled|kill\w*|murder\w*|corpse\w*|dead|death|die[ds]?|dying|knife|knives|dagger|stab\w*|throat|"
    r"axe|hatchet|strangl\w*|suicide|drown\w*|poison\w*|torture\w*|scream\w*|wound\w*|slain|slay\w*|"
    r"butcher\w*|flesh|bones?|skull|shot|gun|pistol|rifle|bayonet|hang(ed|ing)|gallows|guillotine|"
    r"naked|bosom|breasts?|thighs?|bed|kiss\w*|embrace\w*|lust\w*|passion\w*|ravish\w*|"
    r"eat(en|ing)?|devour\w*|roast\w*|cannibal\w*|fiend\w*|vampire\w*|beast\w*|savage\w*)\b",
    re.IGNORECASE,
)
TRIGGERED = ["1080-0", "1080-1", "1184-2", "174-1", "1952-2", "2148-0", "2148-1", "2148-2", "2149-1",
             "2150-0", "25305-0", "25305-1", "25305-2", "345-1", "345-2", "84-2", "98-0", "98-2"]
CONTROLS = ["1952-1", "135-1", "2149-2", "73-0", "1184-0", "1184-1"]

def body(text):
    start = text.find("*** START OF")
    if start != -1:
        text = text[text.find("\n", start) + 1:]
    end = text.find("*** END OF")
    if end != -1:
        text = text[:end]
    return text

windows = {}
for path in sorted(BOOKS.glob("*.txt")):
    words = body(path.read_text(errors="ignore")).split()
    scored = sorted(
        ((sum(1 for w in words[i:i + WINDOW] if KEYWORDS.search(w)), i)
         for i in range(0, max(1, len(words) - WINDOW), STEP)),
        reverse=True,
    )
    picked = []
    for score, i in scored:
        if all(abs(i - j) >= WINDOW for _, j in picked):
            picked.append((score, i))
        if len(picked) == PER_BOOK:
            break
    for rank, (_, i) in enumerate(picked):
        windows[f"{path.stem}-{rank}"] = " ".join(words[i:i + WINDOW])

json.dump([{"id": k, "text": windows[k]} for k in TRIGGERED], open(ROOT / "trig_passages.json", "w"))
json.dump([{"id": k, "text": windows[k]} for k in CONTROLS], open(ROOT / "control_passages.json", "w"))
json.dump(TRIGGERED, open(ROOT / "triggered.json", "w"))
print(len(windows), "windows;", len(TRIGGERED), "triggered;", len(CONTROLS), "controls")
