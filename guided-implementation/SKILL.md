---
name: guided-implementation
description: >
  Plan a feature with the user, then write an ordered file-by-file build guide (HTML, snippets, explanations) they apply by hand. Grills the idea, updates GLOSSARY.md, finds affected files and side effects. Use when implementing a feature and unsure which files it involves, or to understand the change instead of delegating it.
---

# guided-implementation

The reader is a developer who will **edit the files themselves**. The agent plans, explains and reviews; the user types. The page is done when the user can follow it top to bottom, end up with a working feature, and explain every change afterwards.

Source files stay untouched by the agent during this skill. The only files it writes are `GLOSSARY.md` / ADRs (via `domain-modeling`) and the guide page. The audit in §7 may apply the snippets inside a throwaway `git worktree` copy; the real checkout is never edited.

**Every snippet must be true.** A snippet that imports a symbol the file does not export, uses an undefined error code, or leaves out an import sends the reader into a debugging session of the agent's mistake. §4 sets the rules that prevent this, and §7 makes an independent sub-agent audit the guide before the user sees it.

## 0. Check the environment

Do `../visualisation/SKILL.md` §0 (detect OS, pick the browser-open command, use portable file tools).

## 1. Capture the idea and map the ground

Restate the feature in two sentences from the user's prompt. Then collect facts yourself (use a sub-agent for wide searches; the user supplies decisions, never facts):

- the entry points the feature will hang off (route, component, command, job)
- the closest existing feature: the pattern to copy
- `GLOSSARY.md`, `GLOSSARY-MAP.md`, `docs/adr/`: vocabulary and standing decisions
- the verify tasks: see [Find the verify tasks](#find-the-verify-tasks)

Completion criterion: you can name the entry point, the pattern to copy, and the verify commands, each with a file path.

### Find the verify tasks

The Check line of every step and the final "Done when" run the project's own tasks: **typecheck**, **lint** (ESLint), **format** (Prettier), **test**, and **build** when the feature touches it. Find them in this order:

1. **Nearest `package.json`.** From each file the feature will edit, walk up the directories to the first `package.json`; in a monorepo also read the root one. Read its `scripts`. Take the package manager from the lockfile (`pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `package-lock.json` → npm, `bun.lockb` → bun) and run scripts as `<pm> run <name>`.
2. **Classify each script** by name and body:

   | Task | Names and bodies that match |
   |---|---|
   | typecheck | `type-check`, `typecheck`, `check-types`, `tsc`; body contains `tsc --noEmit`, `vue-tsc`, `svelte-check` |
   | lint | `lint`, `eslint`; body contains `eslint` |
   | format | `format:check`, `prettier:check`, `format`, `prettier`; body contains `prettier` |
   | test | `test`, `test:unit`, `cypress`; body contains `node --test`, `vitest`, `jest`, `cypress` |
   | build | `build` |

3. **Fall back to config files** when a task has no script: `tsconfig.json` → `npx tsc --noEmit`; `eslint.config.*` or `.eslintrc*` → `npx eslint <edited files>`; `.prettierrc*` or `prettier.config.*` → `npx prettier --check <edited files>`. Name these "own commands" in the table. Non-JS projects: use the equivalent from `pyproject.toml`, `Makefile`, `go.mod` and similar.
4. **Prefer check-only variants.** The user edits by hand, so a script that rewrites files (`lint:fix`, `format`, `--write`) is a *fix* command: list it as an optional follow-up, and pick the matching check variant for the Check lines.

**When one task has several candidates** (for example `type-check` and `tsc:build`, or `lint` and `lint:ci`), ask the user once, one question covering every ambiguous task, with the recommended script first and marked. If the user does not answer (away, skipped, "you pick"), continue with the recommended one. The agent cannot run a clock, so the default applies to a missing or declined answer, never to a timer; tell the user so in one line when you ask. Choose the recommendation by: check-only over fixing, scoped to the edited package over repo-wide, fastest over slowest.

Completion criterion: a verify table with one row per task (typecheck, lint, format, test, build when relevant): the exact command, the `package.json` or config it came from, and whether it was a script, an own command, or the user's pick.

## 2. Grill

**Small scope** (the feature touches fewer than 3 files and adds no domain terms): run `grilling` only, search the code inline instead of dispatching a sub-agent, and keep the page to the sections that apply. This saves tokens.

Pick the interview by what the feature touches:

| The feature... | Run |
|---|---|
| adds or renames domain concepts, touches an area with a glossary or ADRs, or the user wants decisions recorded | call the Skill tool for `grilling` **and** `domain-modeling` (the `/grill-with-docs` combination) |
| is purely technical (refactor, config, plumbing) with no new vocabulary | call the Skill tool for `grilling` only (the `/grill-me` combination) |

When unsure, use both: a glossary entry costs little and a missing one costs a misunderstanding later. Say which you chose in one line.

`domain-modeling` writes `GLOSSARY.md` inline as each term resolves, and offers an ADR only for hard-to-reverse, surprising, trade-off decisions. Let it.

Completion criterion: the grilling frontier is empty and the user has confirmed shared understanding. Keep a numbered list of decisions (`D1`, `D2`, …) for the page.

## 3. Find every file and side effect

Build the **change set** before writing any snippet. For each file the feature creates or edits, record: path, create or edit, the reason, the decision (`D#`) it serves.

Then sweep for what the user did not ask about, using Grep and Read:

- **Consumers**: every importer and caller of each edited export, with file and line. A changed signature or return shape makes each one a change-set entry or an explicit "unaffected, because…". Name every affected file individually; "and the other callers" is a gap.
- **Contracts**: types, schemas, API shapes, event names, DB migrations, config and env vars, feature flags, i18n keys, CSS class contracts.
- **Tests**: existing tests that cover edited code, and the new tests the feature needs.
- **Docs and glossary**: README, API docs, ADRs, `GLOSSARY.md` terms the feature adds.

Completion criterion: every edited export has its consumers listed, and every change-set row has a reason and a `D#`. Files you examined and ruled out go in a "checked, unaffected" list with one-line reasons.

## 4. Order the steps

Sequence the change set so each step leaves the project working (typecheck passes, existing tests pass):

1. **Prefactor first**: "make the change easy, then make the easy change." Moves, renames and extractions that need no new behaviour.
2. **Then one thin vertical slice** (a tracer bullet) through every layer: type or schema → logic → entry point → UI → test. Widen after the slice works.
3. **Contract last**: delete old code and update docs once nothing uses them.

For a mechanical change with many call sites, use expand → migrate → contract: add the new form beside the old, move callers in batches, then delete the old.

One step is one file, or a tight pair that cannot compile apart. Each step carries:

| Part | Content |
|---|---|
| **Where** | repo-relative path, `create` or `edit`, and the location in the file (after which function, near which line) |
| **Why now** | what earlier steps made possible, in one sentence |
| **Snippet** | real code written against the file as it is today: read the file first. Edits show 2–3 unchanged anchor lines, then the added and removed lines; a new file shows the whole file. Every snippet follows the **snippet correctness rules** below and the **snippet markup rules** in §5 |
| **Explanation** | line-group by line-group: what it does, why it is there, which decision (`D#`) it serves |
| **Check** | the exact command from the verify table (typecheck after type-affecting steps, lint and format on the edited file, the matching test) or a click path, and the expected result |
| **If skipped** | what breaks, one sentence |

### Snippet correctness rules

1. **Symbol ledger.** Before writing any snippet, build a ledger: for every file in the change set and every file a snippet imports from, the exports with kind and signature (parameters, return type, props type, default or named). Take existing files from reading them in this run; take new ones from the step that creates them. Look up every imported or used identifier in the ledger, with the exact name, casing, path and export style.
2. **Imports are part of the snippet.** A snippet that uses a new symbol includes the import line as an added line (or the edited import statement) with its anchor lines, with a path verified against the target file. A snippet for a new file starts with its imports.
3. **Define before use.** Types, error classes and codes, enum members, constants, i18n keys, routes and config keys are created in a step before the first step that uses them. When a use comes first, move the definition earlier.
4. **Paste-ready.** Each snippet is complete, valid code: whole statements, whole functions, whole JSX elements, balanced braces. Elisions such as `...` or "rest unchanged" stay out of code; widen the anchor instead. Anchor lines and `data-n` numbers match the file as it is after the earlier steps.
5. **Behaviour coverage.** For every decision, keep a decision → step matrix, and walk each state it mentions: create versus update, move or reorder, delete and cascade, cancel, failure paths, empty and first-use cases. Every state the feature can reach is saved, sent or shown by some step.
6. **Checks match the step.** A step's Check runs only commands and files that exist after that step and the steps before it. A check on a later file moves to the step that creates it.

Completion criterion: every change-set row appears in exactly one step, every identifier in every snippet resolves in the ledger, and every snippet is complete code.

## 5. Build the draft page

Write the page to a **draft** file outside the repo: `<tmp>/guided-<slug>-draft.html` (the session scratchpad when the environment names one, else the OS temp folder). The final file goes to `.visual-guides/` only after §7 reports clean.

**Copy [`template.html`](template.html) and fill it. Never write the page from scratch**: the template carries the readable-size diagram settings, the chip map, the file-status colours and the step checkboxes, and a page without them renders tiny diagrams. It shares the look of `../visualisation/template.html` (Tailwind and Mermaid from CDN, light and dark mode) and adds step cards with checkboxes. Sections, in order:

1. **In one minute**: what the feature does, how many files, how many steps, and the **Start here** link to step 1.
2. **Decisions**: `D1…Dn` from the grilling, each one sentence, plus the glossary terms added or changed (link to `GLOSSARY.md`).
3. **Map of the work**: four parts, every run, in this order:
   1. **Counts**: badges for new, edited, deleted and test files, then the colour legend as swatches (new green, edited yellow, deleted red, test brown).
   2. **How the pieces fit**: one Mermaid diagram of how the changed pieces interact at runtime (caller → API → service → store, or component → provider → hook), at most 8 nodes, labels at most about 24 characters, new and edited nodes coloured by status, plus a caption saying what to look at. Mermaid is never the step map.
   3. **Files by area**: one `<details class="group">` per area (backend, UI, tests, config, docs, or one per repository). Each group holds its **chips** (`ol.chips`: step number, a role of at most 4 words, the file name, coloured by status) and its **file table** (step, path, kind, why, with a badge in the status colour; deleted files get a red `delete` row). Use groups when there are more than about 12 steps or two or more areas; otherwise one group titled "All steps". Groups start **open**, so the whole plan is visible with no clicks and the reader can collapse any area. With more than about 30 steps, a chip may cover a consecutive range of steps.
   4. **Every changed file appears** in exactly one group's table, including deleted ones.
4. **Steps**: the step cards, wrapped in the same groups in the same order (a group's summary repeats its area name and step range). Each is one `<details class="step">` using the part table from §4, with a checkbox so the user tracks progress (browser-local; the page works without it). The page stays fully readable with every group and step open.
5. **Side effects**: consumers, contracts, tests, docs found in §3, each with file and line, and the "checked, unaffected" list.
6. **Verify commands**: the verify table from §1 (task, command, source, script or own command).
7. **Done when**: the end-to-end check for the whole feature, plus the commands from the verify table.
8. **Glossary**: terms from this page, matching `GLOSSARY.md` exactly.

**File-status colours** (everywhere a file is marked: chips, badges, tables, the legend): new = green, edited = yellow, deleted = red, test = brown. Colour is paired with a word (create, edit, delete, test) so it never carries meaning alone.

**Snippet markup rules** (copying must give clean code):
- One `<figure class="snippet">` per snippet: a caption with the language and file name, copy buttons, and a single `<pre><code>` holding one `<span class="l add|del|ctx">` per line.
- **Gutter on the left:** the row number and the `+` / `−` sign are CSS generated content (`data-n` attribute, `::before` and `::after`), never part of the text. Neither can be selected, so selecting any rows by hand copies only code. Every `.ctx` and `.add` span carries `data-n` with its line number in the file after the edit (a new file counts from 1), so the reader sees where to paste; `.del` spans have none. A new-file snippet uses `class="snippet newfile"` with every line `.add`: green background and row numbers, no sign per line.
- Spans sit next to each other with no whitespace or newline between them; a blank line is a span containing only `<br>` (so manual selection keeps it).
- Each snippet has a **Copy** button (copies the added lines). An edit snippet that has anchor lines also gets **Copy with context** (anchor plus added lines). Removed lines are never copied.
- The page's script wires the buttons and a `copy` handler that cleans any manual selection (numbers, signs and removed lines dropped); keep both.

Writing rules: reuse the visualisation skill's *Tone and wording* and *Writing rules* (`../visualisation/SKILL.md` §3). HTML-escape all code. Use the glossary's terms exactly. Give diagrams a caption saying what to look at.

## 6. Check the draft yourself

Mechanical checks first, so the auditor spends its effort on meaning:

- Search the file for `{{`: zero matches.
- Every `D#` is cited by at least one step; every step cites at least one `D#`.
- Count change-set rows and steps: equal coverage, as §4 requires.
- Every snippet follows the markup rules: no `+` or `−` characters or row numbers inside line text, every `.ctx` and `.add` span has `data-n`, a copy button present, spans adjacent.
- Every step has a Check with a command or click path, and every command appears in the verify table.
- The Map section has all four parts: counts and legend, one overview Mermaid diagram (at most 8 nodes, labels at most about 24 characters, `useMaxWidth: false` in the setup), and grouped chips plus tables.
- Count the table rows: the number equals the change set, every file appears once, deleted files carry the red `delete` badge, and the badge counts at the top match the rows.
- Every chip links to an existing `#step-N`, and group names and step ranges match between the map and the Steps section.
- Every snippet follows the correctness rules in §4: ledger lookups done, imports present, definitions before use.

## 7. Audit with a sub-agent, fix, repeat

The author of a guide is the worst reviewer of it. Before the user sees anything, an **independent auditor** reviews the draft. Spawn it with the Agent tool (`general-purpose`, fresh context). It starts from the repo and the draft, not from your conclusions.

**Brief for the auditor** (the whole brief; add no verdicts or reassurances of your own): the draft path, the repo root, the decisions list, the change set, the verify table, and this checklist:

| # | Check |
|---|---|
| A | **Imports and identifiers.** Every identifier in every snippet resolves: an export read from the repo now, or defined in an earlier step. Import lines are present, paths resolve, named versus default export matches, signatures, parameter lists, return types and props types match the exporting file. |
| B | **Define before use.** Error codes and classes, types, enums, constants, i18n keys, routes and config keys exist in an earlier step than their first use. Nothing is undefined. |
| C | **Paste-ready.** Each snippet is complete, valid code with no elisions, no half-written JSX, balanced braces; anchor lines and line numbers match the file as it is after the earlier steps. |
| D | **Behaviour coverage.** Every decision is implemented. Walk the states: create versus update, move or reorder, delete, cancel, failure, empty, first use. Report any state where data is never saved, sent or shown. |
| E | **Consumers.** Every file that uses a changed export or contract is in the change set, or in "checked, unaffected" with a reason. Every affected file is named. |
| F | **Order and checks.** No step needs something a later step creates. Each Check runs only on files that exist at that step. |
| G | **Consistency.** Names, glossary terms, counts, chips, tables, group ranges and snippet markup agree across the page. |

**Strongest method:** when the project has a typecheck script, the auditor applies the snippets step by step in a throwaway `git worktree` under the temp folder (reusing the repo's `node_modules` by symlink), runs the verify commands after each step, and removes the worktree afterwards. It never touches the real checkout. When that cannot run (no typecheck, missing dependencies), the auditor does a static review reading every target file, and reports "static review only".

**Report format:** a verdict, `CLEAN` or `NOT CLEAN`, then a table of findings: id, severity (blocker, major, minor), step, file, evidence (what the repo or another step really says), and the proposed fix. `CLEAN` means zero findings.

**Scale:** one auditor for 12 steps or fewer. For larger plans, spawn in one message one auditor per area group plus one cross-cutting auditor for D, E, F and G.

**The loop:**
1. Run the audit.
2. Fix every finding in the draft, re-reading the real files for each fix; correct the ledger and the decision matrix as well.
3. Re-run the audit on the changed steps plus the cross-cutting checks.
4. Stop at `CLEAN`. After 3 rounds without `CLEAN`, tell the user the remaining findings and let them decide; never present the guide as verified.

Only after `CLEAN`: copy the draft to the final path (§8) with one addition, the **audit line** in the page header: `Audited: <n> rounds, clean, <applied in worktree and typechecked | static review only>`. Open the page in the browser (command from §0) only then, and confirm Mermaid and Tailwind render, in light and dark mode and at phone width.

## 8. Deliver and hand over

Save the audited draft to `.visual-guides/<YYYY-MM-DD>-<slug>-plan.html` at the repo root. If `.visual-guides/` is not git-ignored, tell the user. Reply with the path, the audit result (rounds, method, findings fixed in one line), the one-minute summary, the list of decisions, and the first step's file; leave the rest on the page.

Then wait. The user edits the files. When they return:

- *"Step N failed"*: read the file as it is now, compare with the step's snippet, and explain the gap.
- *"Done"*: review the result against the plan with `/code-review` for standards and `/visualisation` for an explained diff of what they actually wrote. Report plan items missing from the diff and diff lines the plan never mentioned.
