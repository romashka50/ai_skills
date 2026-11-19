---
name: component-usage-tree
description: >
  Interactive clickable tree of who uses the components, modules or functions changed in a diff, commit, branch or PR, with flagged risks (removed exports still used, new required props, broken imports, cycles). Use for "who uses this", blast radius, dependency tree. With explanation: change-impact-map.
---

# Component usage tree

Turn a diff into a map the user can click through. The question it answers: **"I changed these files. Who uses them, how, and what could break?"**

This skill is the engine. `change-impact-map` reuses its scripts and viewer and adds the visualisation guide on top. Use this skill alone when the user wants only the tree.

The bundled scripts do the deterministic part (changed files, import graph, usage sites, baseline risk checks). Your part is the judgement the scripts can't do: reading the diff, spotting behavioural risks, and writing a short, honest summary.

## Workflow

### 1. Check the environment and pin down the scope
First do `../visualisation/SKILL.md` §0 (detect OS, pick the Python command and browser-open command). Then:

Use `../visualisation/SKILL.md` §1 (Pin the scope): same prompt-to-git-source table, same "narrow by subject, list what you left out" rule. Default to "everything on this branch vs its merge-base, including uncommitted work". Map the result to the analyzer flags: `--base <ref>`, `--head <ref>` (default is the working tree), `--depth N` (consumer hops, default 3).

### 2. Run the analyzer
```bash
<python> <skills>/component-usage-tree/scripts/analyze_changes.py --repo <repo-root> --out impact-graph.json
```
Choose `<python>` and `<skills>` as `../visualisation/SKILL.md` §0 says (`python3` on macOS and Linux, `python` or `py -3` on Windows; `<skills>` is the parent folder of this skill's folder). Run the command with the repository root as the working directory. The scripts need only Python 3 and git, and write UTF-8 on every OS.
It prints one summary line. If it reports no changed source files, check `--base`. It supports JS/TS/JSX/TSX, Vue, Svelte and Python, resolves `tsconfig` path aliases, follows re-exports through barrel `index` files, and handles deleted and renamed files.

If the repo already has a stronger graph source (for example codegraph, dependency-cruiser, madge, an `.understand-anything/knowledge-graph.json`, or a TypeScript AST/MCP tool) you may use it to fill in gaps, but keep the output in the same JSON shape so the viewer still works. Mention in the summary which source you used.

### 3. Review what the scripts can't see
Open `impact-graph.json` and read the diff of the top changed files (highest `fanIn`, any `high` risk). Static regex analysis cannot see changed return shapes, default values, side effects, context/provider requirements, event names, CSS class contracts or string-keyed lookups. Read `references/risk-signals.md` for what to look for and how to rate severity.

Add your findings to the JSON, anchored on real node ids from the graph:
```json
{
  "meta": { "summary": "Button now requires `variant` and `size`; 3 of 4 callers don't pass them." },
  "risks": [
    { "severity": "medium", "source": "review", "nodeId": "src/utils/format.ts",
      "title": "formatLabel now upper-cases output",
      "detail": "Snapshot tests and any case-sensitive comparison on the result will change.",
      "related": ["src/hooks/useCheckout.ts"] }
  ],
  "nodes": [ { "id": "src/components/Modal.tsx", "note": "Close button needs size=\"sm\"." } ]
}
```
(Change `meta.summary`, append to `risks`, set `note` on existing node objects. Don't invent node ids: the builder drops any finding that points at a node it can't find.) Do not repeat a risk the analyzer already raised; refine it with a `note` instead.

### 4. Build the viewer
```bash
<python> <skills>/component-usage-tree/scripts/build_report.py impact-graph.json [--mermaid impact.mmd]
```
Writes one self-contained HTML file (no network needed, light and dark mode, works on mobile) to `.visual-guides/<YYYY-MM-DD>-impact-map.html`; pass `--out` to change it. Add `--mermaid` when the user works in a terminal or wants something to paste into a PR description.

### 5. Deliver it
Follow `../visualisation/SKILL.md` §5: tell the user if `.visual-guides/` is not git-ignored. On Claude.ai with the Artifact tool, publish the HTML as an artifact; otherwise give the path. With no browser, give the Mermaid flowchart in a fenced block. To change the look, edit `assets/template.html`; keep the data contract (`__GRAPH_JSON__`) and the behaviours below.

### 6. Reply briefly
Follow the tone rules in `../visualisation/SKILL.md` (plain, concise, no hedging). Give three things: the 2 or 3 highest-severity issues in one sentence each, what to click first, and the limits of the analysis (static and heuristic; say which languages or patterns were not covered). Do not paste the whole graph or restate the viewer's content.

## What the viewer does
- **Legend, boxes:** colour shows the change kind (modified amber, added green, deleted red, renamed blue). A **dashed** border means either a deleted file (red) or a **dependency**: an unchanged file that a changed file imports (grey, filled). A **solid** grey border is a **consumer**: an unchanged file that imports a changed file.
- **Legend, arrows:** each arrow runs from a file to the code that uses it. **Solid** = a direct import or use. **Dashed** = a re-export, where the usage reaches the file through a barrel (`index`) file. **Thick blue** = the links of the file you selected, labelled with how many times it is used (or "import only" / "re-export"). Faded arrows and boxes are not connected to the selection. A coloured dot on a box marks an issue involving that file (red high, amber medium, blue low).
- Left to right: dependencies → changed files → consumers (levels). Arrows point from a file to the code that uses it, the direction a change travels. Colour shows modified, added, deleted, renamed. A dot marks nodes involved in an issue.
- **Click a node:** its direct links highlight (or the full upstream and downstream chain with the "Full chain" toggle), and the side panel lists:
  - what changed (touched exports, removed or added exports, newly required props)
  - **before → after, and why**: the file's annotated walkthrough block, only when built with `--guide` by `change-impact-map`
  - issues involving this file, each with clickable related files
  - **where it is used**: per consumer, the import line, how it is used (render, call, member, ref), props passed, and chips such as "missing size" where a required prop isn't passed. Usage through a barrel file is shown as "through barrel".
  - what it depends on, and the tests that reach it
- Clicking an issue in the overview rings every file involved. Clicking a consumer name in the panel jumps to it. Filters: tests, dependencies, name search. The overview offers a copyable markdown review checklist.

## Rules of thumb
- Present findings as "where to look", never as proof. The analysis is regex-based and has no type information.
- A clean result is not a safety claim. Say "no issues detected by static checks" rather than "safe".
- Keep severity honest: `high` means something very likely breaks at build or runtime (unresolved import, missing required prop, removed export still used). `medium` means behaviour may change for callers. `low` is housekeeping or a coverage gap.
- Large changes (more than ~60 nodes in view): lower `--depth`, or tell the user to filter by name, instead of dumping everything.

## Files

Run the scripts and fill `assets/template.html` through them. Reading either file into context costs about 8k tokens each and adds nothing.

- `scripts/analyze_changes.py`: diff → graph JSON (usage sites, props, barrel resolution, baseline risks)
- `scripts/build_report.py`: validate agent additions, render HTML, optional Mermaid; `--guide` is used by `change-impact-map`
- `assets/template.html`: the viewer (single file, vanilla JS and SVG)
- `references/risk-signals.md`: what to check by kind of change, severity rubric
- `references/prior-art.md`: existing skills and tools this builds on
