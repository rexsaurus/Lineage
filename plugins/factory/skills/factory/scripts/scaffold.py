#!/usr/bin/env python3
"""Write a new pipeline from a short spec file, reproducibly.

  scaffold.py SPEC.yaml --out DIR [--force]

SPEC.yaml holds the five answers (see ../examples/*.yaml and SKILL.md):

  name: minutes                       # slug: skill prefix and output file name
  title: "Minutes"                    # display name
  domain: "meeting minutes written from call transcripts"
  source:  {noun: transcript, dir: sources, citation: "[{source}:{line}]"}     # 1
  unit:    {noun: decision, plural: decisions, definition: "..."}               # 2
  tiers:   [{id: stated, meaning: "..."}, {id: implied, meaning: "..."}]        # 3
  output:  {noun: minutes, format: markdown, builder: none, title: "Minutes"}   # 4
  gates:   [{id: G1, name: "...", after: units, question: "..."}, ...]          # 5
  rules:   ["domain rule", ...]                                                 # optional
  fixture: {sources: {name: "line\\nline"}, units: [...], map: [[section, unit]]}  # optional

The same spec always produces the same files. Everything domain-independent (immutable
sources, citations, units with coverage, policy skill, GENERATED outputs, bridges, gates,
versioning, orchestrator, fixture, HOWTO) comes from ../templates/pipeline/ unchanged.
"""
import argparse, re, shutil, sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("pyyaml is required: pip install pyyaml")

HERE = Path(__file__).resolve().parent
TPL = HERE.parent / "templates" / "pipeline"
STAGES = ["ingest", "units", "assemble", "build", "final"]
FORMATS = {"markdown": "md", "typst": "typ", "html": "html"}


def fail(msg):
    sys.exit(f"spec error: {msg}")


def validate(spec):
    for k in ("name", "title", "domain", "source", "unit", "tiers", "output", "gates"):
        if k not in spec: fail(f"missing `{k}`")
    if not re.fullmatch(r"[a-z][a-z0-9-]{1,30}", spec["name"]):
        fail("`name` must be a short lowercase slug, e.g. minutes")
    cit = spec["source"].setdefault("citation", "[{source}:{line}]")
    if "{source}" not in cit or "{line}" not in cit:
        fail("source.citation must contain {source} and {line}, e.g. \"[{source}:{line}]\"")
    spec["source"].setdefault("dir", "sources")
    spec["source"].setdefault("noun", "source")
    u = spec["unit"]
    for k in ("noun", "definition"):
        if k not in u: fail(f"unit.{k} is required")
    u.setdefault("plural", u["noun"] + "s")
    if len(spec["tiers"]) < 2: fail("give at least two evidence tiers")
    for t in spec["tiers"]:
        if "id" not in t or "meaning" not in t: fail("each tier needs id and meaning")
    o = spec["output"]
    o.setdefault("format", "markdown"); o.setdefault("builder", "none")
    o.setdefault("noun", "output"); o.setdefault("title", spec["title"])
    if o["format"] not in FORMATS: fail(f"output.format must be one of {list(FORMATS)}")
    ids = set()
    for g in spec["gates"]:
        for k in ("id", "name", "after"):
            if k not in g: fail(f"each gate needs {k}")
        if g["after"] not in STAGES: fail(f"gate {g['id']}: after must be one of {STAGES}")
        if g["id"] in ids: fail(f"duplicate gate id {g['id']}")
        ids.add(g["id"])
    if not any(g["after"] in ("build", "final") for g in spec["gates"]):
        fail("add a final sign-off gate (after: build): a human signs off before anything is final")
    spec.setdefault("rules", [])
    return spec


def cite(spec, src, line):
    return spec["source"]["citation"].replace("{source}", src).replace("{line}", line)


def tokens(spec):
    t1 = spec["tiers"][0]["id"]
    src_example = "call-1"
    return {
        "name": spec["name"], "title": spec["title"], "domain": spec["domain"],
        "source_noun": spec["source"]["noun"], "source_dir": spec["source"]["dir"],
        "citation": spec["source"]["citation"], "citation_example": cite(spec, src_example, "3"),
        "span_example": f"{src_example}:1-4",
        "unit_noun": spec["unit"]["noun"], "unit_plural": spec["unit"]["plural"],
        "unit_definition": spec["unit"]["definition"],
        "first_tier": t1, "tier_ids": ", ".join(t["id"] for t in spec["tiers"]),
        "tiers_table": "\n".join(["| Tier | Meaning |", "|---|---|"]
                                 + [f"| `{t['id']}` | {t['meaning']} |" for t in spec["tiers"]]),
        "output_noun": spec["output"]["noun"], "output_format": spec["output"]["format"],
        "builder": spec["output"]["builder"], "ext": FORMATS[spec["output"]["format"]],
        "gates_table": "\n".join(["| Gate | Decision | After stage | The question |", "|---|---|---|---|"]
                                 + [f"| {g['id']} | {g['name']} | {g['after']} | {g.get('question', '')} |"
                                    for g in spec["gates"]]),
        "domain_rules": "\n".join(f"- {r}" for r in spec["rules"]) or "- (none yet: add the domain's own rules here)",
    }


def render(text, tk):
    def rep(m):
        k = m.group(1)
        if k not in tk: fail(f"template token {{{{{k}}}}} has no value")
        return str(tk[k])
    return re.sub(r"\{\{([a-z_]+)\}\}", rep, text)


def default_fixture(spec):
    """A tiny, valid fixture: two sources, three units, one unapproved bridge."""
    sn, un = spec["source"]["noun"], spec["unit"]["noun"]
    tiers = [t["id"] for t in spec["tiers"]]
    sources = {
        "s1": "\n".join(f"Example {sn} one, line {i}." for i in range(1, 5)),
        "s2": "\n".join(f"Example {sn} two, line {i}." for i in range(1, 4)),
    }
    units = [
        {"id": "U001", "title": f"First {un}", "spans": ["s1:1-2"], "tier": tiers[0],
         "text": f"The first {un} restates lines one and two {cite(spec, 's1', '1-2')}."},
        {"id": "U002", "title": f"Second {un}", "spans": ["s1:3-4"], "tier": tiers[-1],
         "text": f"The second {un} restates lines three and four {cite(spec, 's1', '3-4')}.\n\n"
                 f"[[bridge B1: A connecting sentence the sources do not support.]]",
         "questions": ["Approve bridge B1, or cut it?"]},
        {"id": "U003", "title": f"Third {un}", "spans": ["s2:1-3"], "tier": tiers[0],
         "text": f"The third {un} restates the second {sn} {cite(spec, 's2', '1-3')}."},
    ]
    return {"sources": sources, "units": units,
            "map": [["Part one", "U001"], ["Part one", "U002"], ["Part two", "U003"]]}


def write_fixture(spec, root):
    fx = spec.get("fixture") or default_fixture(spec)
    proj = root / "fixture"
    srcdir = proj / spec["source"]["dir"]
    for d in (srcdir, proj / "units", proj / "ledger"): d.mkdir(parents=True, exist_ok=True)
    for name, text in fx["sources"].items():
        (srcdir / f"{name}.txt").write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    for u in fx["units"]:
        lines = []
        for sp in u["spans"]:
            src, _, rng = sp.partition(":")
            a, _, b = rng.partition("-")
            body = (srcdir / f"{src}.txt").read_text(encoding="utf-8").splitlines()
            for n in range(int(a), int(b or a) + 1):
                lines.append(f"{cite(spec, src, str(n))} {body[n - 1]}")
        fm = {"id": u["id"], "title": u["title"], "spans": u["spans"], "tier": u["tier"],
              "bridges_approved": u.get("bridges_approved", []), "questions": u.get("questions", [])}
        slug = re.sub(r"[^a-z0-9]+", "-", u["title"].lower()).strip("-")[:40]
        (proj / "units" / f"{u['id']}-{slug}.md").write_text(
            "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n## Source\n"
            + "\n".join(lines) + "\n\n## Text\n" + u["text"].strip() + "\n", encoding="utf-8")
    (proj / "map.csv").write_text("section,unit\n" + "".join(f"{s},{u}\n" for s, u in fx["map"]))
    (proj / "excluded.csv").write_text("span,reason\n")
    # Gates before assembly are pre-approved in the fixture so `make fixture` reaches a draft;
    # the final sign-off stays open, which is the point.
    pre = {g["id"]: {"approved": True, "by": "fixture", "date": "2026-01-01"}
           for g in spec["gates"] if STAGES.index(g["after"]) < STAGES.index("assemble")}
    (proj / "gates.yaml").write_text(yaml.safe_dump(pre, sort_keys=True) if pre else "{}\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec"); ap.add_argument("--out", required=True)
    ap.add_argument("--force", action="store_true", help="overwrite an existing output folder")
    a = ap.parse_args()
    spec = validate(yaml.safe_load(Path(a.spec).read_text()))
    root = Path(a.out)
    if root.exists() and any(root.iterdir()):
        if not a.force: sys.exit(f"{root} exists and is not empty (use --force to overwrite)")
        shutil.rmtree(root)
    tk = tokens(spec)
    for src in sorted(TPL.rglob("*")):
        if src.is_dir(): continue
        rel = src.relative_to(TPL).as_posix()
        if rel.startswith("skills/"):  # skills/policy/SKILL.md -> .claude/skills/<name>-policy/SKILL.md
            part = rel.split("/")[1]
            rel = f".claude/skills/{spec['name']}-{part}/" + "/".join(rel.split("/")[2:])
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix in (".md", ".mk") or src.name == "Makefile":
            dest.write_text(render(src.read_text(encoding="utf-8"), tk), encoding="utf-8")
        else:
            shutil.copy2(src, dest)
    clean = {k: v for k, v in spec.items() if k != "fixture"}
    (root / "pipeline.yaml").write_text("# The five answers. scripts/pl.py reads this at run time.\n"
                                        + yaml.safe_dump(clean, sort_keys=False, allow_unicode=True))
    write_fixture(spec, root)
    (root / "scripts" / "pl.py").chmod(0o755)
    n = sum(1 for p in root.rglob("*") if p.is_file())
    print(f"scaffolded {spec['name']} at {root} ({n} files). Next: cd {root} && make fixture")


if __name__ == "__main__":
    main()
