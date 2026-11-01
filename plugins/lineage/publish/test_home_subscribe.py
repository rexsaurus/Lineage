#!/usr/bin/env python3
"""The book home page loses its Subscribe control on republish. The lineage app keeps its button."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "site"))
import posts  # noqa: E402
import build_site  # noqa: E402

HOME = """<!doctype html><html><body>
<div class="actions">
  <a class="btn ghost" href="/updates/">Updates</a>
  <a class="btn ghost" href="#subscribe">Subscribe</a>
  <a class="btn ghost" href="/lineage/">Explore in Lineage</a>
</div>
<section class="subscribe" id="subscribe">
  <h2>Latest updates</h2>
  <p>What the research turned up. <a href="/updates/">All updates</a></p>
  <ul id="latest-updates"><li><a href="/updates/">Read the updates</a></li></ul>
  <h2>Follow the book</h2>
  <p>Get a plain-language summary each week.</p>
  <div data-lineage-subscribe></div>
  <script src="/updates/subscribe.js" defer></script>
</section>
</body></html>
"""

LINEAGE = """<!doctype html><html><body>
<div class="proj">project <code id="proj"></code></div>
<div class="hactions">
  <a class="btn go hsub-link" id="hdr-sub" href="#home?to=subscribe">Subscribe</a>
  <button class="hsign" id="hdr-sign" type="button">Sign in</button>
</div>
</body></html>
"""


def main():
    stripped = posts.strip_home_subscribe(HOME)
    assert 'href="#subscribe"' not in stripped, stripped
    assert "data-lineage-subscribe" not in stripped
    assert "subscribe.js" not in stripped
    assert "Follow the book" not in stripped
    assert "Latest updates" in stripped
    assert "Read the updates" in stripped
    assert posts.strip_home_subscribe(stripped) == stripped

    kept = posts.strip_home_subscribe(LINEAGE)
    assert kept == LINEAGE
    assert 'id="hdr-sub"' in kept and "btn go" in kept

    published = build_site.mark_published(LINEAGE.replace("<body>", "<body>", 1))
    assert 'class="proj"' not in published
    assert 'id="hdr-sub"' in published and "btn go" in published
    assert 'data-published="1"' in published
    assert "~/lineages" not in published

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "index.html").write_text(HOME, encoding="utf-8")
        (root / "lineage").mkdir()
        (root / "lineage" / "index.html").write_text(LINEAGE, encoding="utf-8")
        assert posts.apply_home_subscribe(root, {"subscribe_home": False}) is True
        home = (root / "index.html").read_text(encoding="utf-8")
        assert 'href="#subscribe"' not in home and "data-lineage-subscribe" not in home
        assert "Latest updates" in home
        assert (root / "lineage" / "index.html").read_text(encoding="utf-8") == LINEAGE
        assert posts.apply_home_subscribe(root, {"subscribe_home": True}) is False
        (root / "index.html").write_text(HOME, encoding="utf-8")
        assert posts.apply_home_subscribe(root, {"subscribe_home": True}) is False
        assert 'href="#subscribe"' in (root / "index.html").read_text(encoding="utf-8")
        (root / "index.html").write_text(HOME.replace("</body>", "<p>~/lineages/example</p></body>"), encoding="utf-8")
        try:
            posts.apply_home_subscribe(root, {"subscribe_home": False})
        except posts.PostError:
            pass
        else:
            raise SystemExit("a home path in the book home page should stop the build")
    print("home subscribe: ok")


if __name__ == "__main__":
    main()
