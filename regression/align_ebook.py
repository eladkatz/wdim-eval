import json, re, zipfile, html, pathlib, collections

ROOT = pathlib.Path(__file__).parent
EPUB = pathlib.Path.home() / "Downloads" / "Maas, Sarah J. - [Throne of Glass 01] • Throne of Glass.epub"
TOG_CASES = ["4GfFVI", "TIPJdZ", "ahIMQ1", "eZ6fzf", "nVw06Z", "tlHQ1O"]
PROBE = 60

def norm(word):
    return re.sub(r"[^a-z]", "", word.lower())

def load_book():
    book = zipfile.ZipFile(EPUB)
    names = [n for n in book.namelist() if n.endswith((".xhtml", ".html", ".htm"))]
    opf = next(n for n in book.namelist() if n.endswith(".opf"))
    opf_text = book.read(opf).decode("utf-8", "ignore")
    manifest = dict(re.findall(r'<item[^>]*id="([^"]+)"[^>]*href="([^"]+)"', opf_text))
    manifest.update({k: v for v, k in re.findall(r'<item[^>]*href="([^"]+)"[^>]*id="([^"]+)"', opf_text)})
    spine = re.findall(r'<itemref[^>]*idref="([^"]+)"', opf_text)
    base = opf.rsplit("/", 1)[0] + "/" if "/" in opf else ""
    ordered = [base + manifest[i] for i in spine if i in manifest]
    ordered = [n for n in ordered if n in names] or sorted(names)
    words, chapter_starts = [], []
    for name in ordered:
        raw = book.read(name).decode("utf-8", "ignore")
        heading = re.search(r"<h[1-3][^>]*>(.*?)</h[1-3]>", raw, re.S)
        text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"</p>", "\n", raw)))
        chunk = text.split()
        if not chunk:
            continue
        title = html.unescape(re.sub(r"<[^>]+>", "", heading.group(1))).strip() if heading else name
        chapter_starts.append((len(words), title))
        words.extend(chunk)
    return words, chapter_starts

def best_offset(book_norm, probe, start_hint=0):
    target = collections.Counter(probe)
    best, best_pos = 0, 0
    for pos in range(start_hint, len(book_norm) - len(probe), 3):
        window = collections.Counter(book_norm[pos:pos + len(probe)])
        score = sum((window & target).values())
        if score > best:
            best, best_pos = score, pos
    return best_pos, best / len(probe)

words, chapters = load_book()
book_norm = [norm(w) for w in words]
passages = {p["case"]: p for p in json.load(open(ROOT / "arms_passages.json")) if p["arm"] == "A_prod_full"}

aligned = {}
for case in TOG_CASES:
    transcript = [norm(w) for w in passages[case]["window"].split()]
    transcript = [w for w in transcript if w]
    start, start_quality = best_offset(book_norm, transcript[:PROBE])
    end_probe = transcript[-PROBE:]
    end, end_quality = best_offset(book_norm, end_probe, max(0, start))
    end += PROBE
    inside = [(i, t) for i, t in chapters if start < i < end]
    containing = [t for i, t in chapters if i <= start][-1:] 
    aligned[case] = {
        "match_quality": [round(start_quality, 2), round(end_quality, 2)],
        "ebook_words": end - start,
        "transcript_words": len(transcript),
        "starts_in": containing[0] if containing else None,
        "chapter_breaks_inside": [{"title": t, "words_into_window": i - start} for i, t in inside],
        "ebook_text": " ".join(words[start:end]),
    }
    print(case, aligned[case]["match_quality"], aligned[case]["ebook_words"], "vs", len(transcript),
          "| starts in:", aligned[case]["starts_in"], "| breaks:", aligned[case]["chapter_breaks_inside"])

json.dump(aligned, open(ROOT / "tog_ebook_alignment.json", "w"), indent=1)
print("chapters found:", len(chapters))
