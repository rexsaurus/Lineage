#!/usr/bin/env python3
"""Check quotations in chapter files against their sources. Never invent or tidy a quote.

    python $BOOKASSEMBLER/scripts/verify_quotes.py chapters/*.typ               # published works
    python $BOOKASSEMBLER/scripts/verify_quotes.py --transcript chapters/*.typ  # the subject's words
    python $BOOKASSEMBLER/scripts/verify_quotes.py --all chapters/*.typ        # both

Run from the book project folder (or --project DIR). Exit status 1 on any
mismatch, missing source or unfound quote; 0 when everything checks out.

WORKS mode (default) checks passages quoted from published writers:
  * epigraphs given to the chapter template:
        #show: chapter.with(..., epigraphs: (([text], "Author, Work"), ...))
    (the single form `epigraph: [text], epigraph-source: "Author, Work"` too)
  * voice passages:  #voice[text][Author, Work]  or  #voice([text], "Author, Work")
  against public-domain texts listed in facts/sources/works.csv:
        work,author,file
        Moby-Dick,Herman Melville,melville/moby-dick.txt
        Poems,Emily Dickinson,dickinson/poems.txt
  (`file` is relative to facts/sources/). A source string matches a row by
  "Author, Work", by the bare work title, or -- for untitled poems -- by the
  author alone when that row's work is blank or equals the author. A work with
  no row (still in copyright, say) is an error: clear it by hand and remove
  the quote, or add the public-domain text.
  Pieces separated by an ellipsis are checked separately; curly quotes, line
  breaks, Typst escapes/emphasis and dash spellings are normalized.

TRANSCRIPT mode (--transcript) checks every "double-quoted" passage in the
chapter prose (outside epigraphs/voices, comments and code) of at least
--min-words words against what the narrator actually says in
transcript/clean/*.md (paragraphs labelled with narrator.label from book.yaml).
Matching is on words: case, punctuation, quote style, whitespace and the
[?word?] low-confidence markers are ignored; nothing else is. Ellipses
("...", "…") and bracketed editorial insertions ("[the ship]") split a quote
into pieces, each of which must appear verbatim. A quote found only in another
speaker's words (the interviewer's, say) is printed as "check attribution"
but does not fail the run: it is verbatim, and only a reader can tell
whether the prose credits it to the right person.
  Quotations from someone else (a letter, a newspaper, another relative) are
  exempted by putting  // quote-source: <where it is from>  on any line of
  the same paragraph. Those are counted, not checked.
"""
import argparse
import bisect
import csv
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _project as P  # noqa: E402

SOURCES = Path("facts/sources")
WORKS_CSV = SOURCES / "works.csv"
EXEMPT = re.compile(r"//\s*(quote-source|not-transcript)\b", re.I)
CITE = re.compile(r"\[(S\d+) \d{1,2}:\d{2}:\d{2}\]")
PARA = re.compile(r"^\*\*(?P<spk>[^*]+)\*\* \[(?P<s>S\d+) (?P<t>\d{1,2}:\d{2}:\d{2})\] (?P<rest>.*)$")
ELLIPSIS = re.compile(r"\s*(?:…|\.\s?\.\s?\.|\[\s*(?:…|\.\.\.)\s*\])\s*")


# --------------------------------------------------------------------------
# A small Typst scanner: enough to find balanced (...) and [...] and skip
# "strings" inside code.
# --------------------------------------------------------------------------
def close_of(s, i):
    """s[i] is ( or [; return the index of its matching closer (or len(s)-1)."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack = [s[i]]
    j = i + 1
    while j < len(s) and stack:
        c = s[j]
        top = stack[-1]
        if c == "\\":
            j += 2
            continue
        if top != "[" and c == '"':           # string literal in code mode
            j += 1
            while j < len(s) and s[j] != '"':
                j += 2 if s[j] == "\\" else 1
        elif top == "[" and c == "/" and s.startswith("//", j) and (j == 0 or s[j - 1] != ":"):
            j = s.find("\n", j)
            j = len(s) if j < 0 else j
            continue
        elif c in pairs:
            stack.append(c)
        elif c == pairs[top]:
            stack.pop()
            if not stack:
                return j
        j += 1
    return len(s) - 1


def split_args(s):
    """Split the inside of (...) on top-level commas."""
    out, cur, j = [], [], 0
    while j < len(s):
        c = s[j]
        if c in "([{":
            k = close_of(s, j)
            cur.append(s[j:k + 1])
            j = k + 1
            continue
        if c == '"':
            k = j + 1
            while k < len(s) and s[k] != '"':
                k += 2 if s[k] == "\\" else 1
            cur.append(s[j:k + 1])
            j = k + 1
            continue
        if c == ",":
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
        j += 1
    if "".join(cur).strip():
        out.append("".join(cur).strip())
    return out


def literal(arg):
    """[content] or "string" -> its text."""
    arg = arg.strip()
    if arg.startswith("[") and arg.endswith("]"):
        return arg[1:-1]
    if arg.startswith('"') and arg.endswith('"'):
        return arg[1:-1].replace('\\"', '"')
    return arg


def line_of(s, i):
    return s.count("\n", 0, i) + 1


# --------------------------------------------------------------------------
# WORKS mode
# --------------------------------------------------------------------------
def find_quoted_works(s):
    """[(line, body, source)] for epigraphs and voices in a chapter."""
    items = []
    for m in re.finditer(r"#voice\b", s):
        j = m.end()
        if j < len(s) and s[j] == "[":
            k = close_of(s, j)
            body = s[j + 1:k]
            if k + 1 < len(s) and s[k + 1] == "[":
                k2 = close_of(s, k + 1)
                items.append((line_of(s, m.start()), body, s[k + 2:k2]))
            else:
                items.append((line_of(s, m.start()), body, ""))
        elif j < len(s) and s[j] == "(":
            args = split_args(s[j + 1:close_of(s, j)])
            pos = [a for a in args if not re.match(r"^[\w-]+\s*:", a)]
            if pos:
                items.append((line_of(s, m.start()), literal(pos[0]),
                              literal(pos[1]) if len(pos) > 1 else ""))
    for m in re.finditer(r"\bepigraphs\s*:\s*\(", s):
        j = m.end() - 1
        for tup in split_args(s[j + 1:close_of(s, j)]):
            if tup.startswith("("):
                parts = split_args(tup[1:-1])
                if len(parts) >= 2:
                    items.append((line_of(s, m.start()), literal(parts[0]), literal(parts[1])))
    m = re.search(r"\bepigraph\s*:\s*\[", s)
    if m:
        j = m.end() - 1
        body = s[j + 1:close_of(s, j)]
        src = re.search(r'\bepigraph-source\s*:\s*"((?:[^"\\]|\\.)*)"', s)
        items.append((line_of(s, m.start()), body, src.group(1) if src else ""))
    return items


def typst_text(t):
    t = re.sub(r"#linebreak\(\)|#parbreak\(\)", " ", t)
    t = re.sub(r"#[A-Za-z][\w-]*\[(.*?)\]", r"\1", t, flags=re.S)   # #emph[x] -> x
    t = re.sub(r"\\\s*\n", " ", t)                                  # \ line break
    t = re.sub(r"\\(.)", r"\1", t)                                  # escapes
    t = t.replace("~", " ")
    return t


def norm_work(t):
    t = unicodedata.normalize("NFKC", t)
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"---|--|—|–", "—", t)
    t = re.sub(r"\s*—\s*", "—", t)
    t = t.replace("_", "").replace("*", "")
    t = t.replace(" 's", "'s").replace(" 'd", "'d")
    return re.sub(r"\s+", " ", t).strip()


def words(t):
    t = unicodedata.normalize("NFKC", t).lower().replace("’", "'").replace("‘", "'")
    t = re.sub(r"\[\?([^\]]*?)\?\]", r"\1", t)
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)*", t)


def load_works():
    if not WORKS_CSV.exists():
        return []
    with open(WORKS_CSV, newline="", encoding="utf-8") as fh:
        return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(fh)]


def lookup(works, source):
    src = norm_work(source).lower()
    def eq(a, b): return norm_work(a).lower() == b
    for r in works:
        if r["author"] and r["work"] and eq(f"{r['author']}, {r['work']}", src):
            return r
    for r in works:
        if r["work"] and eq(r["work"], src):
            return r
    for r in works:
        if r["author"] and eq(r["author"], src) and (not r["work"] or eq(r["work"], src)):
            return r
    if ", " in source:
        rest = norm_work(source.split(", ", 1)[1]).lower()
        for r in works:
            if r["work"] and eq(r["work"], rest):
                return r
    return None


def check_works(paths):
    works = load_works()
    cache, bad = {}, 0
    if not works:
        print(f"note: {WORKS_CSV} missing or empty; every quoted work will be reported")
    for p in paths:
        s = Path(p).read_text(encoding="utf-8")
        items = find_quoted_works(s)
        for line, body, source in items:
            where = f"{p}:{line}"
            if not source.strip():
                print(f"NO ATTRIBUTION {where}: {norm_work(typst_text(body))[:70]}")
                bad += 1
                continue
            row = lookup(works, typst_text(source))
            if not row:
                print(f"NO PUBLIC-DOMAIN SOURCE for {source.strip()!r} at {where} "
                      f"(add it to {WORKS_CSV}, or clear the quote by hand)")
                bad += 1
                continue
            f = SOURCES / row["file"]
            if not f.exists():
                print(f"SOURCE FILE MISSING {f} (for {source.strip()!r} at {where})")
                bad += 1
                continue
            if f not in cache:
                raw = f.read_text(encoding="utf-8", errors="replace")
                cache[f] = (norm_work(raw), " ".join(words(raw)))
            text, wtext = cache[f]
            for piece in ELLIPSIS.split(typst_text(body)):
                piece_n = norm_work(piece)
                if not piece_n or piece_n in text:
                    continue
                if " ".join(words(piece)) in wtext:
                    print(f"PUNCTUATION DIFFERS ({source.strip()}) at {where}: {piece_n[:80]}")
                else:
                    print(f"NOT VERBATIM ({source.strip()}) at {where}: {piece_n[:80]}")
                bad += 1
        print(f"{p}: {len(items)} published passage(s) checked")
    return bad


# --------------------------------------------------------------------------
# TRANSCRIPT mode
# --------------------------------------------------------------------------
class Transcript:
    """Word streams of the narrator's speech (and everyone's), with positions."""

    def __init__(self, narrator):
        self.narr, self.narr_pos = self._build(lambda spk: spk == narrator)
        self.all, self.all_pos = self._build(lambda spk: True)
        self.narrator = narrator

    @staticmethod
    def _build(keep):
        chunks, pos, n = [], [], 0
        files = sorted(Path("transcript/clean").glob("S*.md"), key=lambda p: P.session_key(p.stem))
        for f in files:
            prev_kept = False
            for line in f.read_text(encoding="utf-8").splitlines():
                m = PARA.match(line)
                if not m:
                    continue
                if not keep(m["spk"]):
                    if prev_kept:
                        chunks.append(" | ")       # a quote may not run across this
                        n += 3
                    prev_kept = False
                    continue
                w = " " + " ".join(words(m["rest"])) + " "
                pos.append((n, m["s"], m["t"], m["spk"]))
                chunks.append(w)
                n += len(w)
                prev_kept = True
            chunks.append(" | ")
            n += 3
        return "".join(chunks), pos

    def find(self, piece, narrator_only=True):
        stream, pos = (self.narr, self.narr_pos) if narrator_only else (self.all, self.all_pos)
        key = " " + " ".join(piece) + " "
        i = stream.find(key)
        if i < 0:
            return None
        k = bisect.bisect_right([p[0] for p in pos], i) - 1
        return pos[max(k, 0)][1:]


def mask_code(s):
    """Blank out comments and code (keeping newlines) so only prose remains."""
    out = list(s)

    def blank(a, b):
        for k in range(a, min(b, len(out))):
            if out[k] != "\n":
                out[k] = " "
    for m in re.finditer(r"/\*.*?\*/", s, re.S):
        blank(m.start(), m.end())
    for m in re.finditer(r"(?m)(^|[^:])(//[^\n]*)", s):
        blank(m.start(2), m.end(2))
    for m in re.finditer(r"#[A-Za-z_][\w.-]*", s):
        if out[m.start()] == " ":
            continue
        name = m.group(0)
        j = m.end()
        if name in ("#let", "#set", "#show", "#import", "#include"):
            # mask the statement: to end of line, extended over any open bracket
            k = j
            while k < len(s) and s[k] != "\n":
                if s[k] in "([{":
                    k = close_of(s, k)
                k += 1
            blank(m.start(), k)
            continue
        if name == "#voice":
            k = j
            while k < len(s) and s[k] in "([":
                k = close_of(s, k) + 1
            blank(m.start(), k)
            continue
        if j < len(s) and s[j] == "(":
            k = close_of(s, j) + 1
            blank(m.start(), k)                # #idx("..."), #image(...)
        else:
            blank(m.start(), j)                # #emph[...] keeps its content
    return "".join(out)


def quotes_in(text):
    t = text.replace("“", '"').replace("”", '"')
    return t.count('"') % 2 == 1, re.findall(r'"([^"]+)"', t)


def check_transcript(paths, min_words):
    narrator, interviewer = P.labels()
    if not list(Path("transcript/clean").glob("S*.md")):
        print("no transcript/clean/*.md -- run render_transcripts.py first")
        return 1
    tr = Transcript(narrator)
    if not tr.narr_pos:
        print(f"no paragraphs labelled **{narrator}** in transcript/clean/ -- check "
              "narrator.label in book.yaml and the speaker_map in corrections.json")
        return 1
    bad = 0
    for p in paths:
        raw = Path(p).read_text(encoding="utf-8")
        masked = mask_code(raw)
        raw_lines = raw.split("\n")
        n_checked = n_exempt = n_bad = 0
        # paragraphs are blank-line separated in the RAW text, so the
        # "// src:" / "// quote-source:" comment lines belong to their paragraph
        for blk in re.finditer(r"(?:[^\n]*\S[^\n]*(?:\n|$))+", raw):
            l0 = line_of(raw, blk.start())
            l1 = line_of(raw, blk.end() - 1)
            src_lines = raw_lines[l0 - 1:l1]
            odd, qs = quotes_in(masked[blk.start():blk.end()])
            qs = [q for q in qs if len(words(q)) >= min_words]
            if odd:
                print(f"UNBALANCED QUOTE MARKS {p}:{l0}")
            if not qs:
                continue
            if any(EXEMPT.search(x) for x in src_lines):
                n_exempt += len(qs)
                continue
            cited = set(CITE.findall("\n".join(src_lines)))
            for q in qs:
                n_checked += 1
                show = re.sub(r"\s+", " ", q).strip()
                pieces = [words(y) for x in ELLIPSIS.split(q)
                          for y in re.split(r"\[[^\]]*\]", x)]
                pieces = [w for w in pieces if w]
                problems, others, hits = [], [], []
                for piece in pieces:
                    hit = tr.find(piece)
                    if hit:
                        hits.append(hit)
                        continue
                    other = tr.find(piece, narrator_only=False)
                    if other:
                        others.append(f"spoken by {other[2]} at [{other[0]} {other[1]}], "
                                      f"not {narrator}: \"{' '.join(piece)[:60]}\"")
                    else:
                        problems.append(f"not in transcript: \"{' '.join(piece)[:60]}\"")
                if problems:
                    n_bad += 1
                    print(f"QUOTE NOT FOUND {p}:{l0}: \"{show[:90]}\"")
                    for x in problems + others:
                        print(f"    {x}")
                elif others:
                    # verbatim, but not the narrator's words: fine if the prose
                    # attributes it to that speaker; wrong if it says the subject
                    print(f"check attribution {p}:{l0}: \"{show[:90]}\"")
                    for x in others:
                        print(f"    {x}")
                elif cited and not any(h[0] in cited for h in hits):
                    print(f"note {p}:{l0}: quote found at [{hits[0][0]} {hits[0][1]}] but the "
                          f"paragraph cites {', '.join(sorted(cited))}")
        print(f"{p}: {n_checked} quotation(s) checked against the transcript, "
              f"{n_exempt} exempt (// quote-source:), {n_bad} not found")
        bad += n_bad
    return bad


def main():
    ap = argparse.ArgumentParser(
        description="Check quotations in chapters against public-domain sources and the transcript.")
    P.add_project_arg(ap)
    ap.add_argument("chapters", nargs="+", help="chapter files (.typ or .md)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--transcript", action="store_true", help="check the subject's quotes only")
    g.add_argument("--all", action="store_true", help="check published works and transcript")
    ap.add_argument("--min-words", type=int, default=3,
                    help="transcript mode: ignore quoted phrases shorter than this (3)")
    a = ap.parse_args()
    paths = [Path(c).expanduser().resolve() for c in a.chapters]
    root = P.enter_project(a.project)
    paths = [str(p.relative_to(root)) if p.is_relative_to(root) else str(p) for p in paths]
    missing = [c for c in paths if not Path(c).exists()]
    if missing:
        sys.exit(f"no such file: {', '.join(missing)}")
    bad = 0
    if not a.transcript:
        bad += check_works(paths)
    if a.transcript or a.all:
        bad += check_transcript(paths, a.min_words)
    print("OK" if not bad else f"{bad} problem(s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
