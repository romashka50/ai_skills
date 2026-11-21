---
name: visualisation
description: >
  Build one self-contained HTML visual guide that explains code changes (uncommitted, commit, branch, PR) or a topic line by line, with diagrams and the reason for each change. Use for "visual guide", "explain my changes", or /visualisation.
---

# visualisation

The reader is a person who wants to *understand*, not skim. The guide is done when every changed line has a plain-language explanation of **what** it does and **why** it changed, and the page opens in a browser and every diagram renders.

## 0. Check the environment first

These skills run on macOS, Linux and Windows. Before running anything, detect the OS and the tools you have (the harness environment block usually states the platform; otherwise run `git --version` and a Python version check). Then pick by this table instead of assuming macOS:

| Need | macOS / Linux | Windows | Any OS |
|---|---|---|---|
| Python 3 (for the usage-tree scripts) | `python3` | `python` or `py -3` (`python3` is often a Microsoft Store stub that does nothing) | Run `<cmd> --version` and use the first that prints 3.x. If none works, say so and skip the usage tree; the guide itself needs no Python. |
| Open the page in a browser | `open <file>` (macOS), `xdg-open <file>` (Linux) | `start "" "<file>"` (cmd) or `Start-Process "<file>"` (PowerShell) | `python -m webbrowser "<file>"`, or the Browser or preview tool when the session has one |
| Search a file for text | `grep` | `Select-String` (PowerShell) or `findstr` | Prefer the agent's own Grep and Read tools; they behave the same everywhere |
| Temp folder | `$TMPDIR`, else `/tmp` | `%TEMP%` (cmd) or `$env:TEMP` (PowerShell) | The session scratchpad when the environment gives one; else `python -c "import tempfile;print(tempfile.gettempdir())"` |

Rules that keep the commands portable:

- `git` commands are identical on every OS. Use them as written; forward slashes work in paths on Windows too.
- Do the file work (read, count, search, write) with the agent's file tools or a short Python snippet, not `sed`, `awk`, `wc`, `cat`, `head` or shell pipes. Those exist only in POSIX shells.
- Quote every path (spaces are common in Windows user folders).
- Write HTML and JSON as UTF-8 and never rely on the console code page.
- `<skills>` in this skill family means the folder that holds the sibling skill folders (`visualisation`, `change-impact-map`, `component-usage-tree`), found from this file's own location (`<skills>` is its parent folder). Do not hard-code `~/.claude/skills`: it is a different folder per OS and per install.

## 1. Pin the scope

Read the scope from the prompt:

| Prompt says | Source |
|---|---|
| "uncommitted", "latest changes", "what you just did" | `git diff HEAD` plus untracked files (`git status --porcelain`, read each `??` file in full) |
| a commit, "last commit", a SHA | `git show <sha>` |
| a branch, PR, "since X" | `git diff <base>...HEAD` |
| a topic with no diff ("how does auth work") | the code that implements it; the key lines play the role of changed lines |

Narrow by the prompt's subject ("regarding our bug" → only the files touching that bug; list the files you left out and why in the guide's Scope section). Ask the user only when two readings give different file sets.

## 2. Find the why

For each hunk, collect the reason from evidence, best first: this conversation, the bug report or ticket, tests added alongside, commit messages, code comments, the surrounding code. Read enough surrounding code to explain what the old code did wrong.

When no evidence gives a reason, write **"Reason not recorded"** in the note. An honest gap beats an invented rationale.

## 3. Write the guide

**Choose the flow first.** Small scope (up to about 2 files or 150 changed lines): write the whole page yourself, as below. Larger scope: use the [subagent flow](#subagent-flow) at the end of this file, which splits the walkthrough, diagrams and proof across parallel agents. Both flows produce the same page from the same template.

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

- Wrap every Mermaid diagram in a card (`rounded-lg border bg-white p-4`) so it belongs to the page. Use `flowchart LR` for before/after side by side; keep a diagram to about 8 nodes.
- Mermaid's `classDef` carries the legend colours: `leak` = red stroke `#dc2626`, `changed` = heavy accent stroke `#3557c4`, `faded` = grey. Linking edges the bug travels along with `-.leak.->` or `linkStyle` in red.
- Label boxes in small uppercase (`text-xs uppercase tracking-wider`) so they read as a schematic, not as UI.
- **Readable without zooming.** Mermaid is rendered at natural size (template setting `useMaxWidth: false`), so a diagram wider than its card scrolls instead of shrinking. Prevent both: at most 6 nodes in one `LR` row, node labels at most about 24 characters (put the detail in a table or caption), and a chain longer than 6 steps split into rows: several short `flowchart LR` diagrams stacked, or a `flowchart TB` with one `subgraph` per row, or the wrapping chip grid from `guided-implementation/template.html`. Inline SVG and Tailwind boxes follow the same bar: text at least 14px on screen. A reader should never need browser zoom.
- **File-status colours.** Wherever a page marks files by what happened to them (walkthrough file badges, maps, usage tables), use: new = green, edited = yellow, deleted = red, test file = brown. Pair each colour with a word (`new`, `edited`, `deleted`, `test`) and show the key as swatches in the legend. Red stays the fault colour in diagrams; a deleted file is marked by its word and red badge, never by a red edge.
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

- Every `{{PLACEHOLDER}}` and template comment is gone. Search with the Grep tool (not a shell-specific command) for the placeholder shape `\{\{[A-Z@]` and for `<!-- ` template comments: zero matches. Do not search for a bare `{{`: code shown in the walkthrough (JSX `style={{…}}`, Vue, Jinja, Go templates) legitimately contains it.
- Every diagram has a caption or label saying what to look at, and the changed step is visibly marked.
- Open the file in a browser if the environment allows (use the command for this OS from section 0) and confirm the Mermaid and Tailwind output renders (no raw `flowchart` text, no unstyled page) and that every diagram's text is readable at 100% zoom: no diagram scrolls sideways, none has tiny labels; split any that do and the page reads in both light and dark mode and at phone width.

## 5. Deliver

Save to `.visual-guides/<YYYY-MM-DD>-<slug>.html` at the repository root (outside a repo: the current directory). If `.visual-guides/` is not git-ignored, tell the user so they can decide. When your environment can render or publish HTML for the user, show it there; otherwise give the path. Reply with the path, the "In one minute" summary and the Takeaway line; do not repeat the guide in chat.

## Subagent flow

Use for scopes above about 2 files or 150 changed lines. Produces the same page from the same `template.html`.

### Step A: prepare the brief (you, before spawning)

Subagents do not see this conversation. Everything they need goes into one brief file, `<tmpdir>/visual-guide-<slug>/brief.md` (`<tmpdir>` = the session scratchpad if there is one, else the OS temp folder from section 0):

- the scope and the exact git command, so each agent can re-run it for its own files;
- the **why evidence** from step 2: conversation facts, ticket text, the root cause, decisions the user made. Mark each item with where it came from;
- the file list with `--numstat` counts, and the assignment of files to annotators;
- the vocabulary: the repo's `GLOSSARY.md` terms, and the one-term-per-concept rule;
- the diagram legend, the tone rules from this file and the path to `template.html`.

### Step B: fan out (one message, all agents together)

Spawn every agent below in a **single message** so they run concurrently. Use `general-purpose` agents (they must write files). Annotators and the proof agent can run on a cheaper model; keep the diagram agent on yours.

| Agent | Input | Writes to `<tmpdir>/visual-guide-<slug>/` | Returns |
|---|---|---|---|
| **Annotator** × N (one per file; group tiny files; split a file over ~300 changed lines by hunk range, up to 6 annotators in all) | brief, its files, template's `.file`/`.hunk`/`.ln` markup | `file-<n>.html`: the complete `<details class="file">` blocks, every changed line annotated | per file: path, role, Problem and Solution sentences, `added/removed/explained` counts, terms it used, lines marked "Reason not recorded" |
| **Diagrammer** × 1 | brief, the whole diff, the diagram patterns and tool table from this file | `diagrams.html`: the Before and After cards with diagrams | which pattern and tool it chose and why; the node/step it marked as changed |
| **Prover** × 1 | brief, the diff | `proof.html`: the "How we know it works" and "Risks and edges" content | tests found, commands run with results, what stays unverified |

Every agent's prompt states: the output file, "HTML-escape all code", the `+`/`−` signs rule, "do not invent a reason: write **Reason not recorded**", "do not edit any repository file", and "end with the return fields above". Hand the Prover the instruction to run only the existing tests that cover the scope, and to report failures as they are.

### Step C: assemble and verify (you)

1. Read each agent's return. If an annotator's `explained` count is below its changed-line count, send it a follow-up (`SendMessage` to the same agent) naming the uncovered lines; do not patch them yourself.
2. Write the parts only you can: In one minute, Takeaway, Scope, Glossary (merged from every agent's terms, deduplicated), and the header badges.
3. Open `template.html`, paste the fragments in order (file blocks sorted by the importance you gave them, the key file first), fill the header. Replace every placeholder.
4. Run the section 4 checks on the assembled page: the line totals add up across annotators, no placeholders remain, one term per concept (search the fragments for synonyms the agents introduced and unify them), diagrams agree with the walkthrough (the node marked "changed" is a file or function that really changed).
5. Reconcile contradictions between agents. If the Diagrammer and an Annotator explain the same change differently, re-read the code and fix the wrong one yourself.

Do not let an agent write the final page, and do not run a second agent pass "to review the first" by default: the count check and the term check are the review. Skip the flow when a re-run of one annotator would cost more than writing its file yourself.
