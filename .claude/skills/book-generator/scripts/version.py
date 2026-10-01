#!/usr/bin/env python3
"""Version the book's inputs (git) and outputs (numbered snapshots). Run from project root.

  version.py init                      # git repo + .gitignore + originals checksums
  version.py snapshot "label" [--major] [--note "..."]
        commits all inputs, tags vN.M, copies current outputs to output/versions/vN.M-label/,
        writes MANIFEST.json and appends CHANGES.md
  version.py list                      # all versions with date, pages, words
  version.py diff vA vB                # what changed between two versions (inputs + stats)
  version.py show vN.M -- <path>       # print a file as it was in that version

Inputs  = everything text: book.yaml, transcript/, facts/, content/, data/, chapters/, book/,
          voice/, photos/photo_index.csv, CLAUDE.md. Tracked in git; each snapshot is a tag.
Outputs = output/*.pdf and *.xlsx. Too big for git; each snapshot copies them into
          output/versions/<tag>/ with a manifest pinning the exact input commit.
Originals (audio/, photos/source/) are never versioned or modified; the manifest records
their SHA-256 so any later change is detectable.
"""
import datetime, hashlib, json, re, shutil, subprocess, sys
from pathlib import Path

IGNORE = """# BookAssembler project
audio/
photos/source/
photos/print/
transcript/work/
output/
.venv/
__pycache__/
*.wav
*.m4a
*.mp4
.DS_Store
"""


def git(*a, check=True):
    r = subprocess.run(["git", *a], capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"git {' '.join(a)} failed:\n{r.stderr}")
    return r.stdout.strip()


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()


def originals():
    out = {}
    for d in ("audio", "photos/source"):
        for p in sorted(Path(d).glob("*")) if Path(d).exists() else []:
            if p.is_file(): out[str(p)] = sha(p)
    # Once book.yaml sets transcription_locked: true, transcripts are protected like the
    # recordings (every citation depends on their timestamps), so a change stops a snapshot.
    try:
        import yaml
        locked = bool((yaml.safe_load(open("book.yaml")) or {}).get("transcription_locked"))
    except Exception:
        locked = False
    for d in () if not locked else ("transcript/raw", "transcript/verbatim", "transcript/clean"):
        for p in sorted(Path(d).glob("*")) if Path(d).exists() else []:
            if p.is_file(): out[str(p)] = sha(p)
    for f in ("transcript/master.md", "transcript/sessions.csv") if locked else ():
        if Path(f).is_file(): out[f] = sha(Path(f))
    return out


def tags():
    return [t for t in git("tag", "--list", "v*", "--sort=v:refname", check=False).splitlines() if t]


def next_tag(major):
    ts = [tuple(map(int, re.match(r"v(\d+)\.(\d+)", t).groups())) for t in tags() if re.match(r"v\d+\.\d+", t)]
    if not ts: return "v0.1" if not major else "v1.0"
    M, m = max(ts)
    return f"v{M + 1}.0" if major else f"v{M}.{m + 1}"


def stats():
    s = {}
    pdf = Path("output/book-draft.pdf")
    final = Path("output/book-final.pdf")
    for name, p in (("draft_pages", pdf), ("final_pages", final)):
        if p.exists():
            info = subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True).stdout
            m = re.search(r"Pages:\s+(\d+)", info); s[name] = int(m.group(1)) if m else None
    chapters = list(__import__("csv").DictReader(open("data/chapters.csv"))) if Path("data/chapters.csv").exists() else []
    s["chapters"] = len(chapters)
    s["words"] = sum(int(c.get("word_count") or 0) for c in chapters)
    s["units"] = len(list(Path("content/units").glob("U*.md"))) if Path("content/units").exists() else 0
    s["bridges_pending"] = sum(p.read_text().count("#bridge[") for p in Path("chapters").glob("*.typ")) if Path("chapters").exists() else 0
    return s


def cmd_init():
    if not Path(".git").exists(): git("init", "-q")
    gi = Path(".gitignore")
    cur = gi.read_text() if gi.exists() else ""
    if "# BookAssembler project" not in cur: gi.write_text(cur + ("\n" if cur and not cur.endswith("\n") else "") + IGNORE)
    Path("output/versions").mkdir(parents=True, exist_ok=True)
    json.dump(originals(), open("originals.sha256.json", "w"), indent=1)
    git("add", "-A"); git("commit", "-q", "-m", "Initialize book versioning", check=False)
    print("git ready; originals checksummed in originals.sha256.json")


def cmd_snapshot(args):
    label = next((a for a in args if not a.startswith("--")), "snapshot")
    major = "--major" in args
    note = args[args.index("--note") + 1] if "--note" in args else ""
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    tag = next_tag(major)
    # originals must be unchanged
    known = json.load(open("originals.sha256.json")) if Path("originals.sha256.json").exists() else {}
    now = originals()
    changed = [p for p in known if p in now and known[p] != now[p]]
    if changed: sys.exit(f"STOP: original files changed since init: {changed}")
    added = [p for p in now if p not in known]
    if added:
        known.update({p: now[p] for p in added}); json.dump(known, open("originals.sha256.json", "w"), indent=1)
    git("add", "-A")
    git("commit", "-q", "-m", f"{tag} {label}" + (f"\n\n{note}" if note else ""), check=False)
    commit = git("rev-parse", "HEAD")
    git("tag", "-a", tag, "-m", f"{label}" + (f": {note}" if note else ""))
    dest = Path("output/versions") / f"{tag}-{slug}"
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for p in sorted(Path("output").glob("*")):
        if p.is_file() and p.suffix in (".pdf", ".xlsx"):
            shutil.copy2(p, dest / p.name); copied.append(p.name)
    manifest = {"version": tag, "label": label, "note": note,
                "date": datetime.datetime.now().isoformat(timespec="seconds"),
                "input_commit": commit, "outputs": {n: sha(dest / n) for n in copied},
                "originals_added_since_last": added, "stats": stats()}
    json.dump(manifest, open(dest / "MANIFEST.json", "w"), indent=2)
    st = manifest["stats"]
    line = (f"## {tag} — {label} ({manifest['date'][:10]})\n"
            f"- chapters {st['chapters']}, words {st['words']:,}, units {st['units']}, "
            f"draft pages {st.get('draft_pages')}, bridges pending {st['bridges_pending']}\n"
            + (f"- {note}\n" if note else "") + f"- outputs: output/versions/{dest.name}/ · inputs: git tag {tag}\n\n")
    ch = Path("CHANGES.md")
    ch.write_text((ch.read_text() if ch.exists() else "# Book versions\n\n") + line)
    git("add", "CHANGES.md", "originals.sha256.json"); git("commit", "-q", "--amend", "--no-edit")
    git("tag", "-f", "-a", tag, "-m", f"{label}" + (f": {note}" if note else ""))
    print(f"{tag} saved: inputs @ {git('rev-parse', '--short', 'HEAD')}, outputs in {dest}")


def cmd_list():
    for d in sorted(Path("output/versions").glob("v*"), key=lambda p: [int(x) for x in re.findall(r"\d+", p.name.split("-")[0])]):
        m = json.load(open(d / "MANIFEST.json")) if (d / "MANIFEST.json").exists() else {}
        s = m.get("stats", {})
        print(f"{m.get('version', d.name):6} {m.get('date', '')[:10]}  {m.get('label', ''):30} "
              f"pages {s.get('draft_pages')}, words {s.get('words')}, bridges {s.get('bridges_pending')}")


def cmd_diff(a, b):
    print(git("diff", "--stat", a, b, "--", "content", "data", "chapters", "facts", "book", "book.yaml", "voice"))
    ma = json.load(open(next(Path("output/versions").glob(f"{a}-*")) / "MANIFEST.json"))["stats"]
    mb = json.load(open(next(Path("output/versions").glob(f"{b}-*")) / "MANIFEST.json"))["stats"]
    for k in mb:
        if ma.get(k) != mb.get(k): print(f"{k}: {ma.get(k)} -> {mb.get(k)}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == "init": cmd_init()
    elif a[0] == "snapshot": cmd_snapshot(a[1:])
    elif a[0] == "list": cmd_list()
    elif a[0] == "diff" and len(a) == 3: cmd_diff(a[1], a[2])
    elif a[0] == "show" and len(a) >= 4: print(git("show", f"{a[1]}:{a[3]}"))
    else: sys.exit(__doc__)
