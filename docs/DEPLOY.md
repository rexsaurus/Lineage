# The Lineage website: build, preview, deploy

The public site is static: a landing page, the README tour with its screenshots, the docs
rendered to HTML, install instructions, the sample book PDF, and a **read-only** snapshot of
the dashboard running on the invented demo family (the Calders). It is built into
`site/public/` and served by Vercel as plain files. Nothing runs on the server.

```
site/build_site.py   the generator (make site runs it)
site/public/         the built site, committed, and what Vercel serves
vercel.json          output directory, clean URLs, trailing slashes, cache and security headers
.vercelignore        only vercel.json and site/public are uploaded
```

## Build

```bash
make install        # once
make site           # runs `make sample`, then site/build_site.py
```

`make site` needs the Lineage venv plus `markdown` (installed into the venv automatically; it
renders the docs). If Playwright is installed (`make screenshots` installs it), a headless
browser clicks through the static demo afterwards and adds anything the page asked for that
the snapshot lacked. `make site SITEFLAGS=--no-browser` skips that pass.

How the demo is made: the committed fixture `examples/demo-lineage` is copied to a scratch
folder, the real dashboard is started on it with an empty temporary `HOME` (no keys, accounts
or paths of whoever builds it can leak), and every GET the page makes is saved under
`site/public/demo/api/` with the files it shows under `site/public/demo/files/`. A shim
answers the page's `fetch()` calls from those files. Writes, pipeline jobs and the terminal
are switched off and say so; full-text search falls back to matching names.

The build ends with a check over everything in `site/public/` (PDF text included) and stops on
local paths, real email addresses, API keys, links to a local server, or the names of the
real family in the worked example. The worked example chapter (`examples/erasthus-burnham`,
`docs/EXAMPLE-CHAPTER.md`, `docs/images/chapter-p*.png`) is left out by default; publish it
only deliberately, with `make site SITEFLAGS=--with-example-chapter`.

Rebuild and commit `site/public/` whenever the README, the docs, the dashboard or the demo
lineage change.

## Preview locally

```bash
python3 -m http.server 8000 --directory site/public    # then open http://localhost:8000/
```

The demo is at `/demo/`. To preview with Vercel's own routing (clean URLs, trailing slashes,
headers) without deploying, from a linked checkout: `vercel build && vercel dev`.

## Deploy

Not done yet: publishing needs Rex's go-ahead. From the repo root, on the branch to publish:

```bash
vercel link --scope <team>          # once: pick the team and the project name
vercel                              # a preview deployment, to check
vercel --prod                       # production
```

The project settings come from `vercel.json` (no install or build command, output directory
`site/public`), so the Vercel project needs no framework preset and no root directory change.
If the project is connected to the GitHub repo instead, every push to the production branch
deploys the committed `site/public/`; nothing is built on Vercel.

Decisions for the first deploy:
- **Team**: the CLI is logged in with access to two teams, `verafyai` (Verafy, Pro) and
  `verafy` (Verafy, Hobby).
- **Project name**: for example `lineage` (gives `lineage-<team>.vercel.app` or similar).
- **Domain**: none is configured; add one in the project's Domains settings when chosen.
- **Production branch**: `main` or `development`.
