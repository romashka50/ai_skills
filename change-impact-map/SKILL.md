---
name: change-impact-map
description: >
  Full change guide in one HTML page: before, after, the reason per changed line, plus a clickable usage tree of who uses each changed component. Use for PR review, impact analysis, "what changed, why, what it affects". Tree only: component-usage-tree.
---

# Change impact map

One run produces **the full visualisation guide plus a clickable usage tree**, in a single HTML page. The question it answers: **"I changed these files. What exactly changed and why, who uses them, how, and what could break?"**

- The guide half is the `visualisation` skill (`../visualisation/SKILL.md`): before → after, line-by-line walkthrough with reasons, proof, risks, glossary.
- The tree half is the `component-usage-tree` skill (`../component-usage-tree/SKILL.md`), whose scripts and viewer this skill reuses: changed files, every consumer (line, usage kind, props passed), dependencies, flagged risks.
- They are joined: clicking a node in the tree shows that file's **before, after and reason** (its walkthrough block) next to its **usage connections**.

`component-usage-tree` scripts do the deterministic part (changed files, import graph, usage sites, baseline risks). Your part is the judgement the scripts can't do: the why behind each change, behavioural risks, and an honest summary.

## Workflow

### 1. Check the environment and pin down the scope
First do `../visualisation/SKILL.md` §0 (detect OS, pick the Python command and browser-open command). Then:

Use `../visualisation/SKILL.md` §1 (Pin the scope): same prompt-to-git-source table, same "narrow by subject, list what you left out" rule. Default to "everything on this branch vs its merge-base, including uncommitted work". Map the result to the analyzer flags: `--base <ref>`, `--head <ref>` (default is the working tree), `--depth N` (consumer hops, default 3).

### 2. Run the analyzer
```bash
<python> <skills>/component-usage-tree/scripts/analyze_changes.py --repo <repo-root> --out impact-graph.json
```
Choose `<python>` and `<skills>` as `../visualisation/SKILL.md` §0 says (`python3` on macOS and Linux, `python` or `py -3` on Windows; `<skills>` is the parent folder of this skill's folder). Run the command with the repository root as the working directory. The scripts need only Python 3 and git, and write UTF-8 on every OS.
Details of the analyzer and its limits: `../component-usage-tree/SKILL.md` step 2. It prints one summary line. If it reports no changed source files, check `--base`. It supports JS/TS/JSX/TSX, Vue, Svelte and Python, resolves `tsconfig` path aliases, follows re-exports through barrel `index` files, and handles deleted and renamed files.

If the repo already has a stronger graph source (for example codegraph, dependency-cruiser, madge, an `.understand-anything/knowledge-graph.json`, or a TypeScript AST/MCP tool) you may use it to fill in gaps, but keep the output in the same JSON shape so the viewer still works. Mention in the summary which source you used.

### 3. Review what the scripts can't see
Open `impact-graph.json` and read the diff of the top changed files (highest `fanIn`, any `high` risk). Static regex analysis cannot see changed return shapes, default values, side effects, context/provider requirements, event names, CSS class contracts or string-keyed lookups. Read `../component-usage-tree/references/risk-signals.md` for what to look for and how to rate severity.

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

### 4. Write the guide (the visualisation part)
Follow `../visualisation/SKILL.md` §2-§4 end to end, on the same scope: find the why for every hunk, fill `../visualisation/template.html`, run the completeness count ("N of N changed lines explained"). Use the impact data instead of re-deriving it:
- **Before → after diagrams:** `build_report.py --mermaid` gives a ready call-graph flowchart in the shared legend (trim to about 12 nodes).
- **How we know it works:** `meta.likelyTests`.
- **Risks and edges:** `risks[]` from the graph, high first.
- **Walkthrough notes:** `nodes[].usages` give each consumer's line and props, useful for "who is affected" lines.

Two rules make the join work:
1. Every `<details class="file">` carries `data-node="<repo-relative path>"`, exactly the node `id` in the graph (for a renamed file, the new path). This is how a tree node finds its before/after/why block.
2. Keep the `<!-- IMPACT_MAP -->` marker where the template puts it, between Before → after and Walkthrough. The builder replaces it with the tree.

Large scope: use the subagent flow in `../visualisation/SKILL.md`, and tell each annotator the `data-node` rule.
Save the guide as `.visual-guides/<YYYY-MM-DD>-<slug>.guide.html` (an intermediate; the deliverable is step 5's output).

### 5. Build the combined page
```bash
<python> <skills>/component-usage-tree/scripts/build_report.py impact-graph.json --guide .visual-guides/<date>-<slug>.guide.html --out .visual-guides/<date>-<slug>.html [--mermaid impact.mmd]
```
Keep it on one line: a trailing `\` continues a command only in POSIX shells, not in cmd or PowerShell.
This embeds the usage tree into the guide at `<!-- IMPACT_MAP -->` and links each changed node to its walkthrough block. It warns when a block's `data-node` matches no node, or a changed file has no block: fix those, then rebuild. The tree sits in an inline frame (offline, light and dark mode, phone width); the guide still needs the Tailwind and Mermaid CDNs as `visualisation` documents.

### 5b. Deliver it
Follow `../visualisation/SKILL.md` §5: final file at `.visual-guides/<YYYY-MM-DD>-<slug>.html`; tell the user if `.visual-guides/` is not git-ignored. On Claude.ai with the Artifact tool, publish it as an artifact; otherwise give the path. With no browser, give the Mermaid flowchart in a fenced block. If the user wants the tree's look changed, edit `../component-usage-tree/assets/template.html`; keep the data contract (`__GRAPH_JSON__`) and the behaviours listed there.

### 6. Reply briefly
Follow the tone rules in `../visualisation/SKILL.md` (plain, concise, no hedging). Give three things: the 2 or 3 highest-severity issues in one sentence each, what to click first, and the limits of the analysis (it is static and heuristic; say which languages or patterns were not covered). Do not paste the whole graph or restate the viewer's content.

## What the tree does
The viewer's full behaviour (graph layout, node click panel, filters, checklist) is described in `../component-usage-tree/SKILL.md`. In this skill the panel also shows each changed file's **before → after, and why** block.

## Rules of thumb
Same as `../component-usage-tree/SKILL.md`: findings are "where to look", never proof; keep severity honest; lower `--depth` for large changes.

## Files
- `../visualisation/SKILL.md` and `template.html`: the guide (scope, delivery path, tone, legend, diagrams)
- `../component-usage-tree/`: analyzer, viewer, risk references
