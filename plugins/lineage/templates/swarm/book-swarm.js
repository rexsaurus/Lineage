export const meta = {
  name: 'lineage-book-swarm',
  description: 'Full first pass of a Lineage book: per chapter, research, draft, three edits, two judges with revisions, 100% sources; then front matter, images plan, index, assembly and a continuity review',
  whenToUse: 'Only when the author has asked for a full first pass of the whole book (book-generator, "Gates and the full first pass"). Never between gates otherwise.',
  phases: [
    { title: 'Research', detail: 'two researchers per chapter: records and people; place and period' },
    { title: 'Draft', detail: 'one writer per chapter, to the page minimum, from the dossier and fact sheets' },
    { title: 'Edit', detail: 'fidelity, taste, layout' },
    { title: 'Score', detail: 'two independent judges; revise until the pass score, at most max_rounds' },
    { title: 'Sources', detail: '100% of sources in SOURCES.csv and THE RECORDS' },
    { title: 'Book', detail: 'front matter, images plan, index, assembly, whole-book continuity review' },
  ],
}

// Lineage book swarm (docs/BOOK-SWARM.md). A template: copy it, or pass everything through args.
// Run it from Claude Code's Workflow tool with args like:
// {
//   "project": "/abs/path/to/the/book",          // the project folder (better: a git worktree of it)
//   "scratch": "/abs/path/to/scratch",            // outside the project
//   "min_pages": 10, "pass_score": 8, "max_rounds": 2,
//   "author": "the author",                        // how prompts name the person whose taste rules
//   "chapters": [
//     { "n": 1, "slug": "tobias-calder", "title": "Tobias Calder", "part": "Those Who Came Before",
//       "kind": "ancestor", "file": "chapters/01-tobias-calder.typ", "units": "U001 U002",
//       "note": "the record is the spine: the 1870 census and the roster" },
//     { "n": 2, "slug": "the-ore-dock", "title": "The Ore Dock", "part": "Her Life", "kind": "life",
//       "file": "chapters/02-the-ore-dock.typ", "units": "U003 U004", "frozen": false }
//   ]
// }
// Nothing here names a family: everything specific comes from args and the project's own files.

const A = args || {}
const ROOT = A.project
const SCRATCH = A.scratch || `${A.project}/../swarm-scratch`
const MIN = A.min_pages || 10
const PASS = A.pass_score || 8
const ROUNDS = A.max_rounds === undefined ? 2 : A.max_rounds
const AUTHOR = A.author || 'the author'
if (!ROOT || !Array.isArray(A.chapters) || !A.chapters.length) throw new Error('args.project and args.chapters are required')

const RULES = `
You are working on a Lineage book project at ${ROOT}. WORK ONLY INSIDE IT (use absolute paths); scratch files go in ${SCRATCH}/<slug>/.
Read first: ${ROOT}/CLAUDE.md and ${ROOT}/local-overrides/ (the project's own rules win), ${ROOT}/book.yaml, and the skills in ${ROOT}/.claude/skills/: memoir-style-guide (the master rulebook), family-history-chapters (ancestor chapters), records-archives (research and THE RECORDS), photo-processor (images), chapter-dossier. Then the chapter's dossier ${ROOT}/dossiers/<slug>/: DOSSIER.md holds ${AUTHOR}'s requests for THIS chapter, and every one must be honoured.
Non-negotiables: nothing about the subject or the family that is not on tape (// src: [S# hh:mm:ss] on every paragraph) or in a cited record; quotes exact, diction never upgraded; interpretation and connective tissue not on tape go in #bridge[...]; context about the world is sourced (// context: fact — URL) and never claims anyone's thoughts, feelings or presence; no "general knowledge" sources; ambiguities → // REVIEW: and DOSSIER.md "Decisions pending", never a guess. Sensitive record entries stay out of the prose unless DOSSIER.md records ${AUTHOR}'s decision. Transcription is locked: never touch audio/ or transcript/raw|clean, never re-run speech recognition.
Research: targeted lookups only; automated fetching respects robots.txt, at least 2 s between requests per site, the User-Agent in book.yaml research.user_agent and never an email address; no logins, CAPTCHAs or bot-check workarounds, no bulk harvesting. Use $LINEAGE/scripts/fetch_records.py where it fits. Anything not reachable goes on ${ROOT}/research/MANUAL-LOOKUPS.md for a person. Log every search in the dossier's RESEARCH-LOG.md and every source in SOURCES.csv ($LINEAGE/scripts/dossier.py source|log).
Frozen chapters (DOSSIER.md says FROZEN) are never edited. Shared files you must NOT edit: book/template.typ, photos/photo_index.csv, data/chapters.csv, other chapters' files. Do not git add, commit or push. Never put images in git.
Images: plan new illustrations in photos/images-plan.yaml entries proposed in ${SCRATCH}/<slug>/images.md (id IMG-<NN>-<k>, scene citation, caption, anchor, prompt per photos/IMAGE-STYLE.md); leave // PLATE-TODO: <id> at the anchor. The main session generates them. Illustrations are never presented as photographs.
Build one chapter: cd ${ROOT} && python .claude/skills/book-generator/scripts/build_book.py chapter <file>  (it prints the page count; --pages writes page images you can look at). Quotes: python $LINEAGE/scripts/verify_quotes.py --all <file> must pass.
`

const brief = c => `Chapter ${c.n} of ${A.chapters.length}, "${c.title}" (slug ${c.slug}, part "${c.part || ''}", kind: ${c.kind || 'life'}). File: ${ROOT}/${c.file}. Units: ${c.units || 'see data/chapters.csv'}. Notes: ${c.note || 'none'}.
Minimum length: ${MIN} pages, measured by building. Reach it with real material (the subject's full stories in their words, records, built-out sourced context), never padding, repetition or invention. If the material cannot reach it, say so: the chapter should be combined with a neighbour.`

const CH_SCHEMA = {
  type: 'object',
  properties: {
    slug: { type: 'string' }, pages: { type: 'number' }, builds: { type: 'boolean' }, quotes_ok: { type: 'boolean' },
    sources_logged: { type: 'number' }, review: { type: 'array', items: { type: 'string' } },
    image_ids: { type: 'array', items: { type: 'string' } }, notes: { type: 'string' },
  },
  required: ['slug', 'pages', 'builds', 'quotes_ok', 'review', 'notes'],
}
const SCORE_SCHEMA = {
  type: 'object',
  properties: {
    fidelity: { type: 'number' }, chronology: { type: 'number' }, voice: { type: 'number' }, context: { type: 'number' },
    structure: { type: 'number' }, layout: { type: 'number' }, requests: { type: 'number' }, pages: { type: 'number' },
    hard_fail: { type: 'boolean' }, overall: { type: 'number' }, issues: { type: 'array', items: { type: 'string' } },
  },
  required: ['fidelity', 'chronology', 'voice', 'context', 'structure', 'layout', 'requests', 'pages', 'hard_fail', 'overall', 'issues'],
}

async function research(c) {
  const lenses = [
    ['records', c.kind === 'ancestor'
      ? 'RECORDS AND PEOPLE: primary records of this person and family (censuses, vital records, service files, directories, naturalization, border crossings, newspapers, obituaries, ship and regiment records) and what each confirms, adds to or contradicts in the family story. Anyone who served: the service-record process in family-history-chapters (the record as the spine; hometown and country then; how the war drew them in and their reputation; enlistment, training, shipping; the unit\'s battles, weapons and generals; being sent home; what veterans came home to; first-hand accounts from soldiers in or near the unit).'
      : 'RECORDS AND EVENTS: documentary traces of the events, places and institutions the subject describes (newspapers, catalogues, yearbooks, company and union histories, agency records), confirming dates and names.'],
    ['period', 'PLACE AND PERIOD: the local history of the chapter\'s places in its exact years: numbers, prices, wages, weather, events that explain what the subject was doing; short exact period quotations and first-hand accounts from public-domain writers (texts saved under facts/sources/ and listed in facts/sources/works.csv); 3-5 candidate epigraphs from writers of the place, verified.'],
  ]
  return parallel(lenses.map(([key, what]) => () => agent(`${RULES}\n${brief(c)}
YOUR JOB: research only. Lens: ${what}
First read the chapter's units in ${ROOT}/content/units/, grep ${ROOT}/transcript/master.md, and read the dossier and any existing facts/records/ and facts/people/ files, so you build on what exists. Write a fact sheet at ${ROOT}/facts/records/${c.slug}/${key}_firstpass.md: sections by topic, one fact per bullet with URL (+ page), retrieval date and confidence. Log searches and sources in the dossier; add decisive findings to EVIDENCE.md. Return a summary of the strongest material and the gaps.`,
    { label: `research:${key}:${c.slug}`, phase: 'Research' })))
}

const draft = (c, rs) => agent(`${RULES}\n${brief(c)}
Research summaries (fact sheets in ${ROOT}/facts/records/${c.slug}/):\n${(rs || []).filter(Boolean).join('\n---\n')}
YOUR JOB: write ${ROOT}/${c.file} by the memoir-style-guide chapter shape (§6) and, for an ancestor, family-history-chapters: header (setting · dates · short poetic summary line), the epigraph, opening on the place and its people, strictly chronological dated sections, a closing paragraph, then THE RECORDS listing 100% of the sources. Build, count pages, iterate to >= ${MIN} pages with real material; quotes verified; clean build. Notes in ${SCRATCH}/${c.slug}/notes.md (REVIEWs, bridges, open questions, index terms).`,
  { label: `draft:${c.slug}`, phase: 'Draft', schema: CH_SCHEMA })

const EDITS = [
  ['fidelity', 'FIDELITY EDIT: check every paragraph against its // src: spans in transcript/master.md and every record or context sentence against its source; fix or cut anything unsupported, any upgraded diction in the subject\'s quotes, any altered #verbatim, any claim about feelings, motives or presence, any over-precise date, any claim made "in passing" that no source supports.'],
  ['taste', `TASTE EDIT, as ${AUTHOR} reads: strict chronology with dated section openings; context local to the place and years; the narrator's tone in the style guide and local-overrides; concrete numbers over adjectives; first-hand voices used briefly; every request in DOSSIER.md honoured (check them one by one); smooth seams; no repetition; a strong closing paragraph.`],
  ['layout', 'LAYOUT EDIT: build, render every page (--pages) and look at each; fix plates far from their text, a page that is only a plate, stranded last lines, bad caption breaks, the opener, the family tree or descent block, THE RECORDS. Confirm the page minimum and that quotes verify.'],
]

async function edit(c, cur) {
  for (const [k, job] of EDITS) {
    const r = await agent(`${RULES}\n${brief(c)}\nState: ${JSON.stringify(cur)}\nYOUR JOB: ${job}\nEdit ${ROOT}/${c.file} in place, rebuild, append what you changed to ${SCRATCH}/${c.slug}/notes.md.`,
      { label: `edit:${k}:${c.slug}`, phase: 'Edit', schema: CH_SCHEMA })
    if (r) cur = r
  }
  return cur
}

async function score(c, cur) {
  const who = ['a strict fact-checker who reads the transcript and the records', `${AUTHOR}, a demanding reader who wants an engrossing, accurate book and checks every request in DOSSIER.md`]
  let s = null
  for (let round = 0; round <= ROUNDS; round++) {
    const js = (await parallel(who.map((w, j) => () => agent(`${RULES}\n${brief(c)}
You are an independent judge (${w}). Do NOT edit any file. Read ${ROOT}/${c.file} and its dossier, build it, look at the pages, spot-check 8 // src: citations and 6 record or context claims. Score 1-10: fidelity, chronology, voice, context, structure, layout, requests (each DOSSIER request honoured). pages = measured. hard_fail if pages < ${MIN}, the build or quote check fails, any invented fact, a bare-quote ending, or a request ignored. overall 1-10; issues: concrete, with locations.`,
      { label: `judge${j + 1}:r${round}:${c.slug}`, phase: 'Score', schema: SCORE_SCHEMA, effort: 'high' })))).filter(Boolean)
    const avg = js.length ? js.reduce((t, x) => t + x.overall, 0) / js.length : 0
    const fail = js.some(x => x.hard_fail)
    s = { avg, fail, issues: js.flatMap(x => x.issues), rounds: round }
    log(`${c.slug}: round ${round} score ${avg.toFixed(1)}${fail ? ' (hard fail)' : ''}`)
    if ((avg >= PASS && !fail) || round === ROUNDS) break
    const r = await agent(`${RULES}\n${brief(c)}\nTwo judges scored ${avg.toFixed(1)}/10${fail ? ' with a HARD FAIL' : ''}. Issues:\n${s.issues.map(i => '- ' + i).join('\n')}\nYOUR JOB: fix every issue in ${ROOT}/${c.file} (research more where context is thin), rebuild, confirm the page minimum and the quote check, append to notes.`,
      { label: `revise:r${round}:${c.slug}`, phase: 'Score', schema: CH_SCHEMA })
    if (r) cur = r
  }
  return { ...cur, score: s }
}

const sources = (c, cur) => agent(`${RULES}\n${brief(c)}
YOUR JOB: SOURCES, 100%. Gather every source found, consulted or scraped for this chapter (every URL in its // context: and record comments, every fact sheet's source list, every file under facts/records/_raw/${c.slug}/, the texts quoted) into ${ROOT}/dossiers/${c.slug}/SOURCES.csv: deduplicated, the work's real title (the fact goes in used_for), cited_in_chapter=yes only when the chapter relies on it, status found/consulted/blocked/generated, a group heading. Regenerate THE RECORDS with $LINEAGE/scripts/dossier.py records ${c.slug} and put it after the closing paragraph; then dossier.py check ${c.slug} ${c.file} must pass. Fill EVIDENCE.md and LEARNINGS.md. Rebuild.`,
  { label: `sources:${c.slug}`, phase: 'Sources', schema: CH_SCHEMA })

phase('Research')
const work = A.chapters.filter(c => !c.frozen)
log(`${work.length} chapters to build (${A.chapters.length - work.length} frozen); research → draft → 3 edits → judges (≤${ROUNDS} revisions) → sources`)
const results = await pipeline(work,
  c => research(c),
  (rs, c) => draft(c, rs),
  (d, c) => d ? edit(c, d) : null,
  (e, c) => e ? score(c, e) : null,
  (r, c) => r ? sources(c, r).then(s => ({ ...r, ...(s || {}), score: r.score })) : null,
)
const done = A.chapters.map(c => c.frozen ? { slug: c.slug, title: c.title, frozen: true }
  : { title: c.title, ...(results[work.indexOf(c)] || { slug: c.slug, failed: true }) })

phase('Book')
const BOOK = `${RULES}\nChapter results: ${JSON.stringify(done)}`
const [front, images, index] = await parallel([
  () => agent(`${BOOK}\nYOUR JOB: FRONT AND BACK MATTER. With the foreword-generator and book-generator skills: the introduction draft (as #bridge until ${AUTHOR} approves), the reader glossary, and anything else build_book.py does not generate. Never hand-edit generated files. Report what you wrote.`, { label: 'front-matter', phase: 'Book' }),
  () => agent(`${BOOK}\nYOUR JOB: IMAGES PLAN. Gather every ${SCRATCH}/*/images.md, check each prompt against photos/IMAGE-STYLE.md and photo-processor §4 (a scene the material describes; details matching; no named person's invented face presented as a photograph; nothing graphic), and write the consolidated entries into a proposal ${SCRATCH}/images-plan.yaml in the format of photos/images-plan.yaml. Do not generate images. Report the list.`, { label: 'images-plan', phase: 'Book' }),
  () => agent(`${BOOK}\nYOUR JOB: INDEX. Add #idx(...) marks for people, places, ships, units and events across every non-frozen chapter file (chapter-index-builder conventions). Report the terms.`, { label: 'index', phase: 'Book' }),
])
const assembled = await agent(`${BOOK}\nFront: ${front}\nImages: ${images}\nIndex: ${index}\nYOUR JOB: ASSEMBLE. Run make -C "$LINEAGE" draft PROJECT=${ROOT} (or build_book.py all), fix build errors at their source, look at the title page, contents, a part page, two openers, a spread with a plate, and the index. Report the PDF path and page count.`, { label: 'assemble', phase: 'Book' })
const review = await agent(`${BOOK}\nAssembly: ${assembled}\nYOUR JOB: WHOLE-BOOK CONTINUITY REVIEW (read-only except the report). Read every chapter in order. Find stories told twice, contradictions in names, dates and relationships between chapters, the same context fact repeated, weak seams, tonal outliers, chapters well below the others. Write ${SCRATCH}/REVIEW.md: a table of chapters (pages, judge score, top issues), the cross-book issues with locations, and the consolidated REVIEW list ${AUTHOR} must answer. Return its summary.`, { label: 'continuity', phase: 'Book' })

return { chapters: done.map(d => ({ slug: d.slug, title: d.title, pages: d.pages, score: d.score && d.score.avg, hard_fail: d.score && d.score.fail, frozen: !!d.frozen, failed: !!d.failed })), assembled, review }
