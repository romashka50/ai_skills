---
name: visualisation
description: >
  Build one self-contained HTML visual guide that explains code changes (uncommitted, commit, branch, PR) or a topic line by line, with diagrams and the reason for each change. Use for "visual guide", "explain my changes", or /visualisation.
---

# visualisation

The reader is a person who wants to *understand*, not skim. The guide is done when every changed line has a plain-language explanation of **what** it does and **why** it changed, and the page opens in a browser and every diagram renders.

## 0–1. Environment and scope

Read [`ENVIRONMENT-AND-SCOPE.md`](ENVIRONMENT-AND-SCOPE.md): it picks the OS-specific commands (§0) and maps your prompt to a git source (§1). Sibling skills read the same file.

## 2. Find the why

For each hunk, collect the reason from evidence, best first: this conversation, the bug report or ticket, tests added alongside, commit messages, code comments, the surrounding code. Read enough surrounding code to explain what the old code did wrong.

When no evidence gives a reason, write **"Reason not recorded"** in the note. An honest gap beats an invented rationale.

## 3. Write the guide

**Choose the flow first.** Small scope (up to about 2 files or 150 changed lines): write the whole page yourself, as below. Larger scope: read [`SUBAGENT-FLOW.md`](SUBAGENT-FLOW.md) and follow it, which splits the walkthrough, diagrams and proof across parallel agents. Both flows produce the same page from the same template.

Start from [`template.html`](template.html) in this folder: it carries the Tailwind and Mermaid setup (both follow light and dark mode), the legend, the diagram classes and the annotated-diff markup. Fill these sections, in order:

1. **In one minute**: 3–5 sentences a non-author grasps: the problem, the fix, the effect. Under it, a **Takeaway** card: one sentence, the single thing to remember, with a link to the walkthrough file that matters most.
2. **Scope**: files covered, files excluded, the exact git command used.
3. **Before → after**: the centrepiece. What the user or system experienced before, what happens now, two columns side by side, one diagram each (see *Diagrams*). Mark the changed step. Add a badge row under the title: change kind (`fix` = emerald, `feature` = indigo, `refactor` = slate, `risky` = amber) and, for fixes, severity.
4. **Walkthrough**, one `<details open>` per file: a one-line role of the file, then each hunk as an annotated diff. Every added, removed and changed line carries a note: what it does, why it is there. Group mechanical lines (imports, formatting, renames) under one note naming each line it covers. Open the file block with a **Problem** line and a **Solution** line (one sentence each) when the file holds a distinct part of the change.
5. **How we know it works**: the tests that prove it, what each asserts, how to run them; what was verified by hand; what is still unverified.
6. **Risks and edges**: what could break, what was deliberately left unchanged. A decision someone made on purpose (an ADR, a trade-off the user chose) goes in an amber callout, one line.
7. **Glossary**: every domain term or acronym the guide uses.

### Diagrams

The diagrams carry the weight; prose around them stays short. If a diagram needs a paragraph to be understood, redraw the diagram. Draw one whenever behaviour crosses more than one function, file or process. Pick the pattern that fits and vary them across the page:

- **Flow / call graph**: boxes and arrows for "X calls Y calls Z". Draw the faulty edge in the *leak* colour (red), the new or changed step with a heavy accent border. Sequence form (lifelines, numbered arrows) suits "before: 6 round-trips; after: 1".
- **Cross-section**: horizontal bands for the layers a call passes through. Before: many thin bands. After: fewer, thicker bands, each labelled with its responsibility.
- **Call-graph collapse**: before, a tree of nested boxes; after, one box with the calls that became internal faded inside it.
- **State / timeline**: boxes on a time axis for races, retries, ordering bugs and data that changes over time. Show the bad moment with a red marker.
- **Mass diagram**: two rectangles per unit, one for how much you must know to use it, one for how much it does. Use it for "the interface grew as big as the implementation".
- **Data before/after**: a small table or key-value card for config and schema changes, with changed cells highlighted.

Pick the tool per diagram, and mix them on one page; a page where every diagram looks alike reads as generic:

| Tool | Use for |
|---|---|
| **Mermaid** (`<pre class="mermaid">`) | Graph-shaped diagrams: flowcharts, sequence diagrams, state machines, ER and class diagrams, timelines. Fast, reliable layout. Colour the faulty edge and the changed node with `classDef`. |
| **Tailwind-built boxes** (`<div>`s with utility classes) | Editorial visuals Mermaid cannot weight: cross-sections, mass diagrams, call-graph collapse, before/after data cards, a "deep" box with faded internals. |
| **Inline SVG** | Hand-placed arrows over a Tailwind box layout, markers, timelines with exact positions, anything needing precise geometry. Combine it with the other two: SVG arrows absolutely positioned over a `relative` container of boxes. |

Rules:

- Wrap every Mermaid diagram in a card (`rounded-lg border bg-white p-4`) so it belongs to the page. Use `flowchart LR` for before/after side by side; keep a diagram to about 12 nodes, split it otherwise.
- Mermaid's `classDef` carries the legend colours: `leak` = red stroke `#dc2626`, `changed` = heavy accent stroke `#3557c4`, `faded` = grey. Linking edges the bug travels along with `-.leak.->` or `linkStyle` in red.
- Label boxes in small uppercase (`text-xs uppercase tracking-wider`) so they read as a schematic, not as UI.
- Keep each diagram about 320px tall so before and after sit side by side. Colour sparingly: one accent (indigo), red for faults, amber for warnings, emerald for the fixed state.
- The template header carries a legend (solid box = unit, dashed line = boundary, red = fault or leak, heavy border = changed). Keep it in step with what your diagrams use.
- Know the CDN dependency: the page needs a network to render Mermaid and Tailwind. Say so in the final reply, and keep the walkthrough (plain HTML and CSS in the template) readable even if the CDNs fail to load.

### Impact data

When the scope touches components or modules with many consumers, use the sibling `change-impact-map` skill (`../change-impact-map/SKILL.md`) instead: it runs this whole flow and adds a clickable usage tree, where each changed file's node opens its walkthrough block (before, after, why) beside its usage connections. For that join every `<details class="file">` needs `data-node="<repo-relative path>"`, which the template already carries.

### Tone and wording

- Plain, concise, no hedging, no throat-clearing ("it is worth noting that…"). If a sentence could be a bullet, make it a bullet; if a bullet adds nothing, cut it.
- Use one term per concept and keep it across the whole page. If the repo has a `GLOSSARY.md` or domain-model doc, use its terms exactly and do not substitute near-synonyms.
- Name the gain concretely, in the code's terms: "bug can only happen in one place", "3 call sites share one function", "form no longer double-submits". Do not write "cleaner code" or "easier to maintain".
- Bullets of wins or effects: six words or fewer each.
- Visual style is editorial, not dashboard: generous whitespace, serif headings (`font-serif`) over a stone/slate palette, one accent colour, red for faults, amber for warnings, nothing else.
- If it is related to the evidence - never add sentences which might confuse the user.
- Wording should be clear, user shouldn't double-check and ask the AI agent about any sentence, to clear it out.

### Writing rules

- Explain for a developer new to this codebase: name concepts before using them, give file paths with line numbers.
- HTML-escape all code (`<`, `>`, `&`).
- Mark added and removed lines with `+`/`−` signs as well as colour.
- Keep it one HTML file. Allowed external scripts: the Tailwind CDN and the Mermaid ESM import, both already in the template. Everything else (CSS, SVG, diff markup) is inline. No app code and no interactivity beyond Mermaid's own rendering and `<details>`; no other CDNs or web fonts.

## 4. Check completeness

Count the changed lines in the scoped diff (`git diff HEAD --numstat` gives added/removed per file; add the lines of untracked files). Count the lines your notes cover. Both numbers go in the header as **"N of N changed lines explained"**. Go back to step 3 until they match.

Then check the page itself:

- Every `{{PLACEHOLDER}}` and template comment is gone (search the file for `{{`: zero matches; use the Grep tool, not a shell-specific command).
- Every diagram has a caption or label saying what to look at, and the changed step is visibly marked.
- Open the file in a browser if the environment allows (use the command for this OS from section 0) and confirm the Mermaid and Tailwind output renders (no raw `flowchart` text, no unstyled page) and the page reads in both light and dark mode and at phone width.

## 5. Deliver

Save to `.visual-guides/<YYYY-MM-DD>-<slug>.html` at the repository root (outside a repo: the current directory). If `.visual-guides/` is not git-ignored, tell the user so they can decide. When your environment can render or publish HTML for the user, show it there; otherwise give the path. Reply with the path, the "In one minute" summary and the Takeaway line; do not repeat the guide in chat.
