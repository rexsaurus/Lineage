# The factory

Lineage is one instance of a general pattern. The factory is the generator for the
pattern: give it five answers and it writes a new pipeline, with skills, a runtime, a fixture
and a HOWTO, for a different kind of source material.

```
/plugin marketplace add rexsaurus/Lineage
/plugin install factory@lineage
```
Then ask Claude for "a pipeline like Lineage for <your domain>". Or run the generator
directly:
```bash
python plugins/factory/skills/factory/scripts/scaffold.py \
  plugins/factory/skills/factory/examples/incident-review.yaml --out /tmp/postmortem
cd /tmp/postmortem && make fixture
```

## The pattern

```
sources ──► units ──► map ──► generated output
 (fixed)   (cited)   (order)  (never hand-edited)
     ▲          ▲                    ▲
   gate       gate              final sign-off
```

Raw material comes in and is frozen. It is cut into small units that each cite the lines they
came from. The output is generated from the units in an order a person approves. Humans decide
at named points. Everything the model adds that the sources don't support is quarantined until
someone accepts it.

## The five variables

Only these change from domain to domain:

1. **The source, and what a citation looks like.** Interview audio cited by timestamp; a chat
   export cited by line; a paper cited by page. The citation format is how every later claim
   points home.
2. **The unit.** The smallest piece that stands alone and can be moved without rewriting
   anything: a story, a decision, a timeline event, a finding. Get this right and reordering
   the output is a one-line change.
3. **The evidence tiers.** How well a claim is supported: witnessed / told / lore;
   logged / stated / reconstructed; documented / asserted / disputed. Every unit declares one.
4. **The output, and what builds it.** A printed book via Typst, an HTML page, Markdown, or
   anything a shell command can produce.
5. **The gates.** The points where a human decides: are these the right sources, is this the
   right structure, may this go out. Each has one question.

## The invariants, and why each exists

These are generated for every domain and never vary, because they are what make the output
trustworthy.

- **Sources are immutable and checksummed.** If the source can change, every citation into it
  can silently start pointing at something else. Corrections are new files, never edits.
- **Every claim cites back, into its own unit's lines.** A citation that can point anywhere
  proves nothing. Tying it to the unit's span means a reader, or a check, can verify each
  sentence against the few lines it came from.
- **Units sit between source and output, with a coverage check.** Writing straight from source
  to output makes reordering a rewrite and makes omissions invisible. Units make the structure
  movable, and coverage proves nothing was quietly dropped (or says why it was).
- **One policy skill, which the others defer to.** Rules scattered across skills drift apart.
  One master means one place to change a rule and no contradictions to resolve mid-task.
- **Outputs are generated, never hand-edited.** A hand fix to the output is lost on the next
  build and breaks the chain from claim to source. The GENERATED header says so; the runtime
  detects edits.
- **Anything the model adds is a bridge, and the final build fails while one is unapproved.**
  This is the single most important line of code. Models fill gaps fluently. Quarantining
  every addition, visibly, and refusing to finalize until a human accepts each one is what
  stops plausible invention from reaching a reader.
- **Named gates, with batched questions.** Asking one question at a time trains people to
  click yes. Stopping at a few named points with one batch of questions gets real decisions,
  and they are recorded with who and when.
- **Versioning that pins each output to its exact inputs.** "Which text produced the copy we
  sent?" must have an answer: a tag, an input commit, and every source's checksum in a
  manifest.
- **An orchestrator with a status command.** Long jobs span sessions. `status` says what's done,
  which gate is open, and what to run next, so nobody re-derives the state.
- **A fixture and a HOWTO.** A pipeline nobody can run on a tiny example can't be trusted on a
  large one. CI builds the fixture on every push.

## How to point the factory at a new domain

1. Answer the five questions. Write them down as a spec. `examples/toy-minutes.yaml` is
   complete, with a fixture; `examples/incident-review.yaml` shows a non-book domain;
   `examples/lineage.yaml` is Lineage itself as five answers.
2. Run `scaffold.py <spec> --out <dir>` and then `make fixture` in that folder. It must pass.
3. Write the domain's own rules into `<name>-policy` §7. These are the mistakes this domain
   punishes.
4. Replace the generic fixture with a small real one: two sources, three units, one bridge.
5. Extend only where the domain needs it, for example audio transcription or page layout,
   adding scripts beside `pl.py`. Keep the invariants, and keep `make fixture` green.

## What the generic runtime does not do

It cites lines of plain-text sources. Timestamps, page numbers in PDFs, and audio need a
domain extension, as Lineage adds. It doesn't judge whether a unit's text is faithful
to its lines. It proves that every claim points at the right lines, and leaves the reading to
the human at the gate.
