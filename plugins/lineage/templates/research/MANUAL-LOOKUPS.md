# Manual lookups (hand-off spec)

The records the automated research could **not** reach: they need a logged-in account, a
normal browser past a bot check, a site whose robots.txt bars automated crawlers, or a written
request. Whoever does them (the author, a relative, or a browser assistant working in the
author's own browser session at the author's direction) works **as the author**: the author's
own accounts, a normal browser, a human pace, one record at a time, within each site's terms
of use. Never: CAPTCHA solving, tools built to defeat bot checks, anyone else's credentials,
or bulk downloading of a database.

## How to report back
For every lookup, add one row to `research/manual-lookups-results.csv`:

`id,person,record_type,site,search_used,result,url,date_viewed,transcription,saved_file`

- `result` is found · not found · ambiguous.
- Save each record as a PDF or screenshot in `research/manual-lookups/<id>-<short-name>.(pdf|png)`
  (keep that folder out of git if the site restricts reproduction).
- **Transcribe exactly**, including spellings and crossings-out. Never "correct" a name or date.
- When several candidates appear, list **all** of them with the reasons each does or doesn't fit.
- Never guess an identity. A match needs at least two agreeing facts (name + birth year + place).
- Log the lookup in the chapter's dossier (`RESEARCH-LOG.md`) and its source in `SOURCES.csv`.

## Accounts that unlock most of this
<!-- List the free accounts or reading rooms that cover most rows below, and which sites need a
     person (a bot check, or robots.txt barring automated crawlers). -->

---

## A. <Person> (<birth> – <death>; the record that anchors them)

| id | What to find | Where | Search with | Why it matters |
|---|---|---|---|---|
| A1 | **<record>**, <date and place> | <site or archive, and the collection> | <name variants, years, places> | <what it would prove or settle> |

## B. Family photographs (from the family)

| id | What | Why |
|---|---|---|
| P1 | <a photograph the subject mentions on tape, with the citation> | <where it would go> |

## Not reached by the scripts
<!-- fetch_records.py appends a row here for every page it was not allowed or not able to fetch. -->

| id | URL | site | what to look for | why it was not reached |
|---|---|---|---|---|
