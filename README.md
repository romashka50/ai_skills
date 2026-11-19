# AI Skills: Understand Every Change

Four [Claude Code](https://claude.com/claude-code) skills that help you understand code, before and after you change it:

- **After a change:** *"What exactly changed, why, and what could break?"* Three skills turn a diff, commit, branch or PR into one self-contained HTML page with before/after views, plain-language reasons for each change, and a clickable map of everywhere the changed code is used.
- **Before a change:** *"Which files do I touch, in what order, and why?"* One skill interviews you about a new feature, then writes a file-by-file build guide that you apply by hand.

Every skill writes a single HTML file you open in a browser. No server, no build step.

## Contents

- [Quick start](#quick-start)
- [Which skill should I use?](#which-skill-should-i-use)
- [Reference](#reference)
  - [visualisation](#visualisation)
  - [component-usage-tree](#component-usage-tree)
  - [change-impact-map](#change-impact-map)
  - [guided-implementation](#guided-implementation)
- [How the scope is chosen](#how-the-scope-is-chosen)
- [How the skills fit together](#how-the-skills-fit-together)
- [Repository layout](#repository-layout)
- [Requirements](#requirements)
- [Inspired by](#inspired-by)

## Quick start

1. Put the skill folders where your agent loads skills. For Claude Code, copy or symlink them into `~/.claude/skills/` (all user projects) or `<project>/.claude/skills/` (one project):

   ```bash
   cp -R visualisation component-usage-tree change-impact-map guided-implementation ~/.claude/skills/
   ```

   Keep all four folders side by side. The skills reference each other by relative path (`../visualisation/SKILL.md`), so `change-impact-map`, `component-usage-tree` and `guided-implementation` need `visualisation` next to them. `guided-implementation` also needs skills from another collection, [mattpocock/skills](https://github.com/mattpocock/skills). Install them too (next step).

2. **Only for `guided-implementation`:** install the [mattpocock/skills](https://github.com/mattpocock/skills) collection, which provides `grilling` and `domain-modeling` (required) and `code-review` (optional, used for the final review). Follow the install section of that repository; at the time of writing it offers:

   ```bash
   claude plugin install mattpocock-skills@claude-plugins-official
   ```

   or, for any other agent or for editable copies:

   ```bash
   npx skills@latest add mattpocock/skills -a <agent>
   ```

   Without them `guided-implementation` cannot run its interview. The other three skills work without them.

3. Open a repo and run a skill. The text after the slash command says *what* to look at:

   ```text
   /visualisation uncommitted changes
   ```

   This builds a visual guide of everything you have not committed yet. Other scopes: `last commit`, `changes since main`, or a topic such as `how does authentication work?` (see [How the scope is chosen](#how-the-scope-is-chosen)).

   Without a slash command, plain language works too: *"Explain everything I changed and who it affects."*

4. The agent writes one HTML file to `.visual-guides/` in your repo (the file name starts with the date) and opens it in your browser. If `.visual-guides/` is not git-ignored, it tells you.

## Which skill should I use?

| You want... | Use |
|---|---|
| To understand what changed and why, line by line, with diagrams | [visualisation](#visualisation) |
| Only to see who uses the changed code and what it might break | [component-usage-tree](#component-usage-tree) |
| Both in one page, for a PR review or before merging | [change-impact-map](#change-impact-map) |
| To plan a new feature and build it yourself, file by file, with explained snippets | [guided-implementation](#guided-implementation) |
| To explain how a feature works when there is no diff | [visualisation](#visualisation) (topic mode: [see how](#how-the-scope-is-chosen)) |

## Reference

All four skills are triggered by what you say. Each one's `description` tells the agent when to pick it, so you rarely need the slash command.

### visualisation

**[visualisation](./visualisation/SKILL.md)**: Builds a visual guide: one self-contained HTML page that explains code changes (or a topic) line by line, with diagrams, so a person understands what was done and why.

**Purpose.** Make a change *understandable*, not just reviewable. The guide is complete only when every changed line has a plain-language note on what it does and why it changed.

**Use it when**
- You want a "visual guide" of uncommitted work, a commit, a branch, a PR or a fix.
- You are reviewing someone else's (or an agent's) change and need the reasoning, not only the diff.
- You need to explain a change to a teammate or non-author, or document how a feature works.

**What you get**, in order:
1. **In one minute**: a short summary plus a one-sentence takeaway.
2. **Scope**: files covered and excluded, and the exact git command used.
3. **Before → after**: side-by-side diagrams of behaviour, with the changed step marked and a badge for change kind (fix, feature, refactor, risky).
4. **Walkthrough**: an annotated diff per file where every added, removed or changed line carries a *what* and *why* note.
5. **How we know it works**: tests and manual checks, and what is still unverified.
6. **Risks and edges**: what could break and what was deliberately left alone.
7. **Glossary**: every domain term or acronym used.

**Good to know**
- When no evidence explains a change, the guide says **"Reason not recorded"** rather than inventing a rationale.
- Large scopes (more than about 2 files or 150 changed lines) switch to a parallel subagent flow that splits the walkthrough, diagrams and proof across agents.
- Diagrams render at readable size and long chains wrap into rows, so you should not need to zoom.
- Works on macOS, Linux and Windows; it detects the OS and picks portable commands.

**Try it**: type the slash command, then say what to look at. The wording picks the scope.

| You type | What it does |
|---|---|
| `/visualisation uncommitted changes` | Guides everything not yet committed: `git diff HEAD` plus new untracked files. |
| `/visualisation last commit` | Guides one commit (`git show <sha>`). Give a SHA to pick another commit. |
| `/visualisation changes since main` | Guides the whole branch or PR: `git diff main...HEAD`. |
| `/visualisation the login bug fix` | Narrows to files touching that bug. Files left out are listed in the Scope section. |
| `/visualisation how does authentication work?` | **Topic mode.** No diff: it reads the code that implements the topic and explains its key lines. |

Plain language works too, without the slash command: *"Explain everything about the latest changes. Make a visual guide."*

---

### component-usage-tree

**[component-usage-tree](./component-usage-tree/SKILL.md)**: Builds an interactive, clickable usage tree for the components, modules or functions changed in a diff, with no written explanation.

**Purpose.** Show the *blast radius* of a change. It answers: "I changed these files. Who uses them, how, and what could break?"

**Use it when**
- You ask "who uses this component?" or "what does this change affect?".
- You are about to refactor, rename, delete or change a signature and want a dependency tree first.
- You want only the graph, with no narrative.

**What you get**
- Each changed file, with every consumer: exact line, how it is used, and props passed.
- What each file depends on.
- Flagged risks: removed exports still in use, newly required props that callers don't pass, deleted or renamed files still imported, circular dependencies, untested paths.

**How it works.** Bundled scripts do the deterministic part: changed files, import graph, usage sites and baseline risk checks. The agent then adds judgement the scripts can't see (changed return shapes, side effects, provider requirements, string-keyed lookups) using [`references/risk-signals.md`](./component-usage-tree/references/risk-signals.md).

**Good to know**
- Supports JS/TS/JSX/TSX, Vue, Svelte and Python.
- Resolves `tsconfig` path aliases and follows re-exports through barrel `index` files.
- Needs Python 3 and git only.
- Want the explanation too? Use [change-impact-map](#change-impact-map).

**Try it**: type the slash command, then say what to look at. The wording picks the scope.

| You type | What it does |
|---|---|
| `/component-usage-tree` | Default scope: everything on this branch against its merge-base, including uncommitted work. |
| `/component-usage-tree uncommitted changes` | Only the working tree changes. |
| `/component-usage-tree last commit` | Only the files changed by that commit. |
| `/component-usage-tree changes since main` | Whole branch against `main`. |
| `/component-usage-tree who uses Button?` | Narrows the tree to the subject you name. |

Under the hood the scope becomes analyzer flags `--base <ref>`, `--head <ref>` and `--depth N` (consumer hops, default 3). You can ask for it directly: *"/component-usage-tree changes since main, depth 5"*.

---

### change-impact-map

**[change-impact-map](./change-impact-map/SKILL.md)**: The full guide in one page: before, after and the reason for every changed line, plus a clickable usage tree of who uses each changed component.

**Purpose.** One run, one page, the complete picture: *what changed, why, who uses it, and what could break.* Clicking a file in the tree shows its before, after, why and usage connections together.

**Use it when**
- You are doing a PR or code review and want visual context.
- You need impact analysis before merging or refactoring.
- You would otherwise run both other skills and cross-reference the results.

**What you get**
- The complete [visualisation](#visualisation) guide.
- The complete [component-usage-tree](#component-usage-tree) viewer.
- Both combined: clicking a file in the tree shows its before, after, why and its consumers.

**Good to know**
- It composes the other two. It reuses their template, scripts and rules instead of duplicating them.
- It is the best default for reviewing a branch.

**Try it**: type the slash command, then say what to look at. The wording picks the scope.

| You type | What it does |
|---|---|
| `/change-impact-map` | Whole branch vs its merge-base, including uncommitted work: guide plus usage tree. |
| `/change-impact-map uncommitted changes` | Review what you are about to commit. |
| `/change-impact-map changes since main` | Review a branch or PR before merging. |
| `/change-impact-map last commit` | Check what one commit really affected. |

Plain language works too: *"Explain what changed, why, and what it affects. I'm about to merge this branch."*

### guided-implementation

**[guided-implementation](./guided-implementation/SKILL.md)**: Plans a new feature with you, then writes a step-by-step build guide you apply by hand: which file to edit first, what to add, a code snippet and explanation per file.

**Purpose.** Keep you in control. The agent plans, explains and reviews; you type the code. You finish knowing what was built and why, instead of receiving an unexplained diff.

**Use it when**
- You want to implement a feature but are unsure which files or side effects are involved.
- You want to understand and write the change yourself rather than delegate it.

**What it does**
1. Maps the entry points and the closest existing feature, and finds the project's verify tasks (typecheck, ESLint, Prettier, tests) from the nearest `package.json` scripts, falling back to config files. If several scripts fit one task it asks you to pick, and proceeds with a recommended check-only script when you don't answer.
2. Grills you on the idea. With new domain terms it runs `grilling` plus `domain-modeling` (like `/grill-with-docs`) and records decisions in `GLOSSARY.md`; for purely technical work it runs `grilling` alone (like `/grill-me`).
3. Finds every file to touch, every consumer of edited code, and contracts, tests and docs affected.
4. Orders the steps so the project works after each one: prefactor first, then one thin slice through every layer.
5. Builds one HTML page: the decisions, a colour-coded map of the steps (new file green, edited yellow, deleted red, test brown), and one card per step with the file, a paste-ready snippet, an explanation, a check command and a progress checkbox.
6. After you finish editing, reviews your result against the plan with `/code-review` and `/visualisation`.

**Try it**

| You type | What it does |
|---|---|
| `/guided-implementation add CSV export to the reports page` | Full flow: grill, impact sweep, build guide. |
| `/guided-implementation add rate limiting to the API, I'm not sure what it touches` | Same flow. The side-effect sweep lists every consumer, contract, test and doc the change affects. |
| `/guided-implementation step 3 failed` | Compares your file with the step's snippet and explains the gap. |
| `/guided-implementation done` | Reviews your changes against the plan. |

**Needs** the [mattpocock/skills](https://github.com/mattpocock/skills) collection (`grilling`, `domain-modeling`; `code-review` optional). Install it first, see [Quick start](#quick-start).

Small features (fewer than 3 files, no new domain terms) use a lighter flow: `grilling` only, no sub-agent. The agent never edits your source files during this skill; it writes only the guide, plus `GLOSSARY.md` and ADRs when decisions are recorded.

Output goes to `.visual-guides/<date>-<slug>-plan.html`.

---

## How the scope is chosen

Applies to `visualisation`, `component-usage-tree` and `change-impact-map` (`guided-implementation` starts from your feature description instead). There are no flags or modes to switch on. The skill reads your wording and maps it to a source:

| Your wording | Source used | Mode |
|---|---|---|
| "uncommitted", "latest changes", "what you just did" | `git diff HEAD` plus untracked files | changes |
| "last commit", or a commit SHA | `git show <sha>` | changes |
| a branch, a PR, "since main" | `git diff <base>...HEAD` | changes |
| a topic with no diff: "how does auth work?" | the code that implements it | **topic** |

Topic mode is simply a prompt with a subject and no mention of changes, commits or branches. Only `visualisation` and `change-impact-map` explain *why*; when no evidence gives a reason, the guide says **"Reason not recorded"**.

If your wording fits two different sets of files, the skill asks which you mean.

## How the skills fit together

```
change-impact-map
├── visualisation          → the "what and why" guide
└── component-usage-tree   → the "who uses it" graph (scripts + viewer)

guided-implementation      → plans a feature before you write it
├── grilling               → interview (external skill)
├── domain-modeling        → GLOSSARY.md and ADRs (external skill)
└── visualisation          → shared environment and scope rules, page template
```

`visualisation` and `component-usage-tree` also work alone. `change-impact-map` runs both and merges the result. After you finish a planned feature, `guided-implementation` hands the review to `/code-review` and `/visualisation`.

## Repository layout

```
skills/
├── visualisation/          SKILL.md, template.html
├── component-usage-tree/   SKILL.md, scripts/, references/, assets/template.html
├── change-impact-map/      SKILL.md
└── guided-implementation/  SKILL.md, template.html
```

## Requirements

- An agent that supports skills (built for Claude Code).
- `git`, for diffs, commits and branches.
- Python 3, for the usage-tree scripts (the visualisation guide alone does not need it).
- For `guided-implementation`: the [mattpocock/skills](https://github.com/mattpocock/skills) collection installed (see [Quick start](#quick-start)). It provides `grilling` and `domain-modeling` (required) and `code-review` (optional).
- A web browser to open the generated HTML. The pages load Tailwind and Mermaid from a CDN, so they need a network connection to render fully.

## Inspired by

These skills build on other people's work.

| Skill | Inspired by | What was taken |
|---|---|---|
| `guided-implementation` | `grilling` and `domain-modeling` from [mattpocock/skills](https://github.com/mattpocock/skills) | The skill calls them directly. The interview (a design tree worked in rounds until nothing is left open) and the glossary and ADR recording are theirs. The grill-me / grill-with-docs choice mirrors those two skills. |
| This README | [mattpocock/skills](https://github.com/mattpocock/skills) | Used as an example of how to structure a skills README: install, why, then a reference with one entry per skill. Nothing was copied. |

