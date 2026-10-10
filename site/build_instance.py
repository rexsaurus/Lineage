#!/usr/bin/env python3
"""Publish a read-only snapshot of the Lineage dashboard for ANY project (a family's own lineage),
as a static site that any host can serve (Vercel, Netlify, a folder on a web server).

    python site/build_instance.py --project ~/books/grandma --out ~/sites/grandma \\
        --title "Grandma's Lineage" [--pdf output/book.pdf] [--allow-real-names] [--no-browser]

It is the same machinery as `make site` uses for the invented demo family (see build_site.py), pointed
at a real project:
  - the project is copied to a scratch folder first (never modified), skipping the bulky caches the
    dashboard does not show (--skip; defaults below) and anything the builder cannot read;
  - the real dashboard (app/server.py) runs on the copy with an empty temporary HOME, so no keys,
    accounts or local paths of whoever builds it can leak;
  - every GET the page makes is stored as a static file; writes, pipeline jobs and the terminal are
    switched off and say so;
  - the book PDF (--pdf) is published at book/<name>.pdf and linked from the dashboard's book view.

Publishing a real family is a deliberate act: the build refuses unless --allow-real-names is given,
and it always stops on local paths, emails, API keys and localhost links (the LEAKS check).
The output folder gets a vercel.json (clean URLs, security headers) so it can be deployed as is:
    cd <out> && vercel --prod
"""
import argparse, json, os, re, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_site as bs  # noqa: E402

SKIP = [".git", ".venv", "venv", "node_modules", "__pycache__", ".claude", "output",
        "facts/records/_raw", "facts/records/sources", "audio/raw", "photos/archive"]

VERCEL_JSON = {
    "$schema": "https://openapi.vercel.sh/vercel.json",
    "framework": None, "installCommand": "", "buildCommand": "", "outputDirectory": ".",
    "cleanUrls": True, "trailingSlash": True,
    "headers": [{"source": "/(.*)", "headers": [
        {"key": "X-Content-Type-Options", "value": "nosniff"},
        {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"},
        {"key": "X-Frame-Options", "value": "SAMEORIGIN"}]}],
}


def copy_project(src: Path, dst: Path, skip):
    """Copy src to dst, skipping the listed project-relative paths, symlinks that leave the project,
    and files the builder is not allowed to read (reported, not fatal)."""
    skipped, denied = [], []
    src = src.resolve()
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        rel = Path(dirpath).relative_to(src)
        keep = []
        for d in dirnames:
            r = (rel / d).as_posix()
            full = Path(dirpath) / d
            if any(r == s or r.startswith(s + "/") for s in skip) or full.is_symlink():
                skipped.append(r); continue
            keep.append(d)
        dirnames[:] = keep
        (dst / rel).mkdir(parents=True, exist_ok=True)
        for f in filenames:
            r = (rel / f).as_posix()
            full = Path(dirpath) / f
            if any(r == s or r.startswith(s + "/") for s in skip):
                continue
            try:
                if full.is_symlink():
                    target = full.resolve()
                    if src not in target.parents:
                        skipped.append(r); continue
                shutil.copy2(full, dst / rel / f)
            except (PermissionError, OSError):
                denied.append(r)
    return skipped, denied


class Instance(bs.Demo):
    def start(self):
        # like Demo.start, but the server's stderr goes to a log beside the output (crash diagnosis)
        import subprocess, urllib.request, time
        port = bs.free_port()
        env = dict(os.environ, HOME=str(self.home), LINEAGE_PORT=str(port))
        # Typst finds downloaded packages (e.g. @preview/droplet) under the real user's cache; with the empty
        # HOME it would try to download them and story rendering fails. The cache holds no keys or accounts.
        real_cache = Path(os.path.expanduser("~")) / "Library" / "Caches" / "typst" / "packages"
        if not real_cache.is_dir():
            real_cache = Path(os.environ.get("XDG_CACHE_HOME", Path(os.path.expanduser("~")) / ".cache")) / "typst" / "packages"
        if real_cache.is_dir():
            env.setdefault("TYPST_PACKAGE_CACHE_PATH", str(real_cache))
        env.pop("ANTHROPIC_API_KEY", None)
        self.errlog = open(self.tmp / "server.log", "w")
        self.srv = subprocess.Popen([sys.executable, str(bs.APP / "server.py"), "--port", str(port), "--project", str(self.proj),
                                     "--command", "true"], env=env, cwd=bs.APP,
                                    stdout=self.errlog, stderr=self.errlog)
        self.base = f"http://127.0.0.1:{port}"
        for _ in range(150):
            try:
                page_ = urllib.request.urlopen(self.base + "/", timeout=1).read().decode()
                self.token = re.search(r'const TOKEN = "([^"]+)"', page_).group(1)
                return
            except Exception:
                time.sleep(0.15)
        raise SystemExit("the dashboard did not start; see " + str(self.tmp / "server.log"))

    def req(self, path, method="GET", body=None):
        try:
            return super().req(path, method, body)
        except Exception as e:  # one bad endpoint must not sink the snapshot
            bs.log(f"  request failed, left out: {path} ({type(e).__name__})")
            return 599, "text/plain", b""

    def __init__(self, tmp, project, out, name, pdf):
        super().__init__(tmp)
        self.src = project
        self.proj = Path(tempfile.gettempdir()) / f"lineage-instance-{os.getpid()}" / name
        self.out = out
        self.pdf = pdf
        self.public_path = f"~/lineages/{name}"

    def prepare(self):
        shutil.rmtree(self.proj.parent, ignore_errors=True)
        self.proj.parent.mkdir(parents=True)
        skipped, denied = copy_project(self.src, self.proj, SKIP + self.extra_skip)
        # images the book prints from skipped folders (listed by the project in data/lineage_assets.txt): put them back at
        # their own paths so chapters that reference them still render (e.g. museum photographs under facts/records/_raw/)
        la = self.src / "data" / "lineage_assets.txt"
        for rel in (la.read_text().split() if la.exists() else []):
            f = self.src / rel
            if f.is_file() and not (self.proj / rel).exists():
                (self.proj / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, self.proj / rel)
        bs.log(f"  scratch copy: skipped {len(skipped)} paths, {len(denied)} unreadable files")
        sys.path.insert(0, str(bs.APP))
        import server  # noqa: E402
        p = server.Project(self.proj)
        sj = self.proj / "data" / "sources.json"
        if sj.exists():
            data = json.loads(sj.read_text())
            for row in data.values():
                try:
                    row["thumb"] = server._thumbnail(p, row, self.proj / row["path"])
                except Exception:
                    pass
            sj.write_text(json.dumps(data, indent=1))
        if self.pdf:
            (self.proj / "output").mkdir(exist_ok=True)
            shutil.copy(self.pdf, self.proj / "output" / "book-draft.pdf")
        for s in {str(self.proj.resolve()), str(self.proj), str(self.src), str(self.src.resolve())}:
            self.scrub += [("file://" + s, ""), (s, self.public_path)]
        for s in {str(self.home.resolve()), str(self.home)}:
            self.scrub.append((s, "~"))
        self.scrub.append((str(self.tmp.resolve()), "/tmp"))
        self.scrub.append((str(bs.ROOT), "<lineage>"))
        self.scrub.append((str(Path.home()), "~"))
        self.scrub.sort(key=lambda x: -len(x[0]))


HOME_PATH = re.compile(r"(?:file://)?/(?:Users|home)/[^/\s'\"]+/")
TMP_PATH = re.compile(r"/(?:private/)?(?:tmp|var/folders)/[^\s'\"]*")
TEXT = {".md", ".txt", ".json", ".csv", ".html", ".typ", ".yaml", ".yml", ".js", ".svg", ".ged", ".xml"}


def scrub_paths(out: Path):
    """Published copies only: home-folder and temp paths in text files become "~/" and "/tmp"."""
    n = 0
    for f in out.rglob("*"):
        if f.is_file() and f.suffix.lower() in TEXT:
            t = f.read_text(encoding="utf-8", errors="ignore")
            u = TMP_PATH.sub("/tmp", HOME_PATH.sub("~/", t))
            if u != t:
                f.write_text(u, encoding="utf-8"); n += 1
    return n


# what each hideable area serves; removed from the snapshot (not just hidden in the page)
HIDE_API = {
    "sources": ["/api/engine/sources", "/api/engine/requests", "/api/engine/trash"],
    "settings": ["/api/settings", "/api/identity", "/api/connectors", "/api/voices", "/api/engine/approvals"],
}
HIDE_FILES = {"sources": ["facts", "transcript", "audio", "content", "dossiers", "work"], "settings": []}
HIDE_JS = """
(function(){ const HIDE = __HIDE__;
  for (let i = TABS.length - 1; i >= 0; i--) if (HIDE.includes(TABS[i][0])) TABS.splice(i, 1);
  const bad = h => HIDE.includes(decodeURIComponent((h || '').replace(/^#\\/?/, '')).split(/[\\/?]/)[0]);
  if (bad(location.hash)) history.replaceState(null, '', '#home');
  const route0 = route;
  route = function(){ if (bad(location.hash)) { location.replace('#home'); return; } return route0.apply(this, arguments); };
  if (HIDE.includes('settings')) {
    const st = document.createElement('style'); st.textContent = '#gear{display:none !important}';
    document.head.appendChild(st);
    window.showSettings = function(){ location.replace('#home'); };
  }
})();
"""



R2_JS = """
(function(){ const A = __A__, T = __T__, F = __F__, f0 = window.demoFileUrl;
  // every image comes from Cloudflare R2: full size by path, thumbnails where the page shows it small
  window.thumbOf = u => T[u] || u;
  window.demoFileUrl = rel => { const k = String(rel || '').split('?')[0].replace(/^\\//, ''); return A[k] || f0(rel); };
  const SMALL = '.fp-photo img, .story img, img.portrait, .ap-img img, .fp-src img, .hero img, .infobox img, .cast img, img.ph, .tl img, .hstory img, .hgal img, .hrel img, .pchip img';
  const swap = i => { const s = i.getAttribute('src'); if (T[s] && i.matches(SMALL)) { i.dataset.full = s; i.loading = 'lazy'; i.src = T[s]; } };
  new MutationObserver(ms => { for (const m of ms) for (const n of m.addedNodes) { if (n.nodeType !== 1) continue;
      if (n.tagName === 'IMG') swap(n); else n.querySelectorAll && n.querySelectorAll('img').forEach(swap); } })
    .observe(document.documentElement, { childList: true, subtree: true });
  // faces: centre every cropped picture on the face found in it (data/image_focus.json)
  const focus = i => { const p = F[i.getAttribute('src')] || F[i.dataset.full]; if (p) i.style.objectPosition = p; };
  new MutationObserver(ms => { for (const m of ms) { if (m.type === 'attributes') { if (m.target.tagName === 'IMG') focus(m.target); continue; }
      for (const n of m.addedNodes) { if (n.nodeType !== 1) continue; if (n.tagName === 'IMG') focus(n); else n.querySelectorAll && n.querySelectorAll('img').forEach(focus); } } })
    .observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['src'] });
})();
"""


def use_r2_assets(out: Path, manifest: Path):
    """Point every image at its Cloudflare R2 copy (manifest from the project's scripts/r2_sync.py: path, url,
    thumb_url) and drop those files from the static output. Returns (images mapped, files removed)."""
    import csv as _csv
    A, T, F = {}, {}, {}
    fj = manifest.parent / "image_focus.json"
    focus = json.loads(fj.read_text()) if fj.exists() else {}
    for r in _csv.DictReader(open(manifest, encoding="utf-8")):
        if r.get("url"):
            A[r["path"]] = r["url"]
            if r.get("thumb_url"):
                T[r["url"]] = r["thumb_url"]
            fp = focus.get(r["path"]) or focus.get(r["path"].replace("work/lineage-assets/", "", 1))
            if fp:
                F[r["url"]] = fp
                if r.get("thumb_url"):
                    F[r["thumb_url"]] = fp
    shim = out / "demo" / "shim.js"
    shim.write_text(shim.read_text(encoding="utf-8") + R2_JS.replace("__A__", json.dumps(A)).replace("__T__", json.dumps(T)).replace("__F__", json.dumps(F)), encoding="utf-8")
    gone = 0
    for rel in A:
        f = out / "files" / rel
        if f.is_file():
            f.unlink(); gone += 1
    return len(A), gone

def hide_areas(out: Path, areas):
    """Leave whole areas out of a published snapshot: their API answers and files are deleted, the tabs
    removed, and their addresses sent home. Hidden in the page AND absent from the files served."""
    man_p = out / "api" / "manifest.json"
    man = json.loads(man_p.read_text())
    gone = 0
    for key in list(man):
        path = json.loads(key)[0]
        if any(path == a or path.startswith(a + "/") for area in areas for a in HIDE_API.get(area, [])):
            f = out / "api" / man[key]["f"] if isinstance(man[key], dict) and "f" in man[key] else None
            if f and f.exists():
                f.unlink()
            del man[key]; gone += 1
    man_p.write_text(json.dumps(man, ensure_ascii=False, sort_keys=True, indent=0))
    # remove the hidden areas' files, but never an image another page still shows (photo index, story plates,
    # Familypedia portraits): those stay, everything else in the folder (notes, transcripts, PDFs, research) goes
    still_used = set()
    for f in (out / "api").glob("*"):
        if f.is_file():
            still_used.update(re.findall(r'"((?:work|facts|content|dossiers|transcript|audio)/[^"]+\.(?:jpe?g|png|gif|webp))"',
                                         f.read_text(encoding="utf-8", errors="ignore"), re.I))
    for area in areas:
        for d in HIDE_FILES.get(area, []):
            root = out / "files" / d
            if not root.exists():
                continue
            for f in sorted(root.rglob("*"), reverse=True):
                rel = f.relative_to(out / "files").as_posix()
                if f.is_file() and rel not in still_used:
                    f.unlink()
                elif f.is_dir() and not any(f.iterdir()):
                    f.rmdir()
    aj = out / "demo" / "after.js"
    aj.write_text(aj.read_text(encoding="utf-8") + HIDE_JS.replace("__HIDE__", json.dumps(areas)), encoding="utf-8")
    return gone


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--title", required=True)
    ap.add_argument("--name", default=None, help="short public name for the project (default: from the title)")
    ap.add_argument("--pdf", type=Path, help="the book PDF to publish with the snapshot")
    ap.add_argument("--description", default="")
    ap.add_argument("--home-url", default="../", help="link back from the snapshot's banner (default: the parent page)")
    ap.add_argument("--home-label", default="Home")
    ap.add_argument("--hide", default="", help="comma-separated areas to leave out of a public snapshot: "
                    "sources (raw sources, transcripts, research files) and/or settings")
    ap.add_argument("--skip", action="append", default=[], help="another project-relative path to leave out")
    ap.add_argument("--assets", type=Path, help="R2 manifest CSV (path,url,thumb_url): serve those images from R2, not the site")
    ap.add_argument("--allow-real-names", action="store_true",
                    help="required: this publishes a real family's material")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    if not a.allow_real_names:
        raise SystemExit("refusing: publishing a project's real names needs --allow-real-names "
                         "(for an invented family use `make site`)")
    name = a.name or re.sub(r"[^a-z0-9]+", "-", a.title.lower()).strip("-")
    out = a.out.expanduser().resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    bs.SITE = out                               # build_site's helpers and checks write/scan here

    tmp = Path(tempfile.mkdtemp(prefix="lineage-instance-"))
    inst = Instance(tmp, a.project.expanduser().resolve(), out, name, a.pdf)
    inst.extra_skip = a.skip
    report = None
    try:
        inst.prepare(); inst.start(); inst.crawl(); inst.write_app(); inst.copy_files(); inst.write_manifest()
        bs.log(f"  {len(inst.manifest)} API responses, {len(inst.files)} files")
        if not a.no_browser:
            report = inst.browser_pass()
    finally:
        inst.stop()
        log = tmp / "server.log"
        if log.exists() and log.stat().st_size:
            shutil.copy(log, out.parent / (out.name + "-server.log"))
        shutil.rmtree(tmp, ignore_errors=True)

    # the page: its own title and description instead of the demo family's
    idx = out / "index.html"
    t = idx.read_text(encoding="utf-8")
    t = re.sub(r"<title>.*?</title>", f"<title>{a.title} · Lineage (read-only)</title>", t, count=1, flags=re.S)
    t = re.sub(r'<meta name="description" content="[^"]*">',
               f'<meta name="description" content="{a.description or a.title + ": a read-only snapshot of the Lineage dashboard."}">', t, count=1)
    idx.write_text(t, encoding="utf-8")
    # the banner and messages: a real family's snapshot, not the invented demo
    aj = out / "demo" / "after.js"
    if aj.exists():
        j = aj.read_text(encoding="utf-8")
        esc = lambda x: x.replace("\\", "\\\\").replace("'", "\\'")
        j = re.sub(r"bar\.innerHTML = '.*?';", (
            "bar.innerHTML = '<span><b>Read-only</b> snapshot of " + esc(a.title) + ". Nothing you change is saved.</span>'"
            " + '<span><a href=\"" + esc(a.home_url) + "\">" + esc(a.home_label) + "</a> · Built with "
            "<a href=\"" + bs.GITHUB + "\">Lineage</a></span>';"), j, count=1, flags=re.S)
        j = j.replace('The terminal runs Claude Code on your own machine. Run it yourself with "make demo".',
                      "This is a read-only snapshot: the terminal is not available here.")
        j = j.replace("Pipeline steps run on your own machine (\"make demo\").", "This is a read-only snapshot: nothing runs here.")
        aj.write_text(j, encoding="utf-8")
    areas = [x.strip() for x in a.hide.split(",") if x.strip()]
    if areas:
        unknown = [x for x in areas if x not in HIDE_API]
        if unknown:
            raise SystemExit(f"--hide: unknown area(s) {unknown}; choose from {list(HIDE_API)}")
        bs.log(f"  hidden: {', '.join(areas)} ({hide_areas(out, areas)} API answers and their files removed)")
    if a.assets:
        n, g = use_r2_assets(out, a.assets)
        bs.log(f"  images from Cloudflare R2: {n} mapped, {g} local copies dropped from the snapshot")
    if a.pdf:
        (out / "book").mkdir(exist_ok=True)
        shutil.copy(a.pdf, out / "book" / f"{name}.pdf")
    (out / "vercel.json").write_text(json.dumps(VERCEL_JSON, indent=2) + "\n")

    bs.log(f"  scrubbed local paths in {scrub_paths(out)} published files")
    found = bs.check_text()
    if report and report.get("misses"):
        bs.log("  still missing from the snapshot:", *report["misses"][:20], sep="\n    ")
    if found["leaks"]:
        bs.log(f"CHECK leaks: {len(found['leaks'])}", *found["leaks"][:40], sep="\n  ")
        raise SystemExit("check failed: local paths, emails, keys or localhost links in the output")
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    bs.log(f"{out}: {sum(1 for f in out.rglob('*') if f.is_file())} files, {size / 1048576:.1f} MB "
           f"(real names allowed; leak check passed)")


if __name__ == "__main__":
    main()
