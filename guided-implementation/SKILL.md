---
name: guided-implementation
description: >
  Plan a feature with the user, then write an ordered file-by-file build guide (HTML, snippets, explanations) they apply by hand. Grills the idea, updates GLOSSARY.md, finds affected files and side effects. Use when implementing a feature and unsure which files it involves, or to understand the change instead of delegating it.
---

# guided-implementation

The reader is a developer who will **edit the files themselves**. The agent plans, explains and reviews; the user types. The page is done when the user can follow it top to bottom, end up with a working feature, and explain every change afterwards.

Source files stay untouched by the agent during this skill. The only files it writes are `GLOSSARY.md` / ADRs (via `domain-modeling`) and the guide page.

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

- **Consumers**: every importer and caller of each edited export, with file and line. A changed signature or return shape makes each one a change-set entry or an explicit "unaffected, because…".
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
| **Snippet** | real code written against the file as it is today: read the file first. Edits show 2–3 unchanged anchor lines, then the added lines with `+` and removed lines with `−`. New files show the whole file. Every snippet is paste-ready |
| **Explanation** | line-group by line-group: what it does, why it is there, which decision (`D#`) it serves |
| **Check** | the exact command from the verify table (typecheck after type-affecting steps, lint and format on the edited file, the matching test) or a click path, and the expected result |
| **If skipped** | what breaks, one sentence |

Completion criterion: every change-set row appears in exactly one step, and every snippet compiles in your head against the current file contents.

## 5. Build the page

Start from [`template.html`](template.html). It shares the look of `../visualisation/template.html` (Tailwind and Mermaid from CDN, light and dark mode) and adds step cards with checkboxes. Sections, in order:

1. **In one minute**: what the feature does, how many files, how many steps, and the **Start here** link to step 1.
2. **Decisions**: `D1…Dn` from the grilling, each one sentence, plus the glossary terms added or changed (link to `GLOSSARY.md`).
3. **Map of the work**: the steps in order as a wrapping grid of chips (`ol.chips` in the template: step number, a role of at most 4 words, the file name; coloured by file status: new green, edited yellow, deleted red, test brown; the legend shows each colour as a swatch). The grid wraps, so 3 or 30 steps stay readable. Add a Mermaid flowchart only for branching dependencies, within the readability rules in `../visualisation/SKILL.md` (about 8 nodes, 6 per row). Under it, the file-order table (step, file, create/edit, why).
4. **Steps**: one `<details class="step">` per step, in order, using the part table from §4. Steps carry a checkbox so the user tracks progress (browser-local; the page works without it).
5. **Side effects**: consumers, contracts, tests, docs found in §3, each with file and line, and the "checked, unaffected" list.
6. **Verify commands**: the verify table from §1 (task, command, source, script or own command).
7. **Done when**: the end-to-end check for the whole feature, plus the commands from the verify table.
8. **Glossary**: terms from this page, matching `GLOSSARY.md` exactly.

**File-status colours** (everywhere a file is marked: chips, badges, tables, the legend): new = green, edited = yellow, deleted = red, test = brown. Colour is paired with a word (create, edit, delete, test) so it never carries meaning alone.

Writing rules: reuse the visualisation skill's *Tone and wording* and *Writing rules* (`../visualisation/SKILL.md` §3). HTML-escape all code. Use the glossary's terms exactly. Give diagrams a caption saying what to look at.

## 6. Check completeness

- Search the file for `{{`: zero matches.
- Every `D#` is cited by at least one step; every step cites at least one `D#`.
- Count change-set rows and steps: equal coverage, as §4 requires.
- Every step has a Check with a command or click path, and every command appears in the verify table.
- Open the page (command from §0) and confirm Mermaid and Tailwind render, in light and dark mode and at phone width.

## 7. Deliver and hand over

Save to `.visual-guides/<YYYY-MM-DD>-<slug>-plan.html` at the repo root. If `.visual-guides/` is not git-ignored, tell the user. Reply with the path, the one-minute summary, the list of decisions, and the first step's file; leave the rest on the page.

Then wait. The user edits the files. When they return:

- *"Step N failed"*: read the file as it is now, compare with the step's snippet, and explain the gap.
- *"Done"*: review the result against the plan with `/code-review` for standards and `/visualisation` for an explained diff of what they actually wrote. Report plan items missing from the diff and diff lines the plan never mentioned.
