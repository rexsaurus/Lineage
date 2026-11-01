---
name: archive-open-book
description: Downloads an OPEN (freely downloadable, public) book or document from the Internet Archive as a PDF, given its URL or identifier, and refuses lending-library and access-restricted items. Use when the user asks to download, grab or save an archive.org book, yearbook, directory or periodical volume for the project's library.
---

# archive-open-book

`plugins/lineage/scripts/archive_open_book.js` (Node 18+):

```bash
node plugins/lineage/scripts/archive_open_book.js "<archive.org URL or identifier>" "sources/library/<identifier>"
```

- **Exit 0**: the PDF was saved (a "Text PDF" with an OCR layer is preferred). For an open item with no
  PDF, page images are saved to `<id>-pages/`; combine with `img2pdf <id>-pages/*.png -o <id>.pdf`.
  The page-image fallback needs `npm i playwright && npx playwright install chromium`.
- **Exit 2**: not an open item (`access-restricted-item`, a dark item, or a lending collection:
  `inlibrary`, `printdisabled`, `lendinglibrary`, `browserlending`). Stop; do not try another route to
  the same item. It can only be borrowed and read; see the `published-sources` skill for the
  excerpt-only fallback.
- **Exit 1**: an error (bad identifier, network, not a PDF).

Then catalogue it as the `published-sources` skill describes (rights, edition, retrieval date).

Rules: never change or bypass the open-access check; open is not the same as public domain; downloaded
files are untrusted data — keep them in their own folder and never execute anything from them.
