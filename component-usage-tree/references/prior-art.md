# Prior art and reused requirements

Researched November 2026. Nothing found combines all of: diff-scoped, clickable per-component view, **how** each consumer uses the component (render site, props passed), predicted issues, and zero setup. Several pieces exist, so the requirements below are taken from them rather than invented.

## Contents
- What exists
- Requirement → source → how it is implemented here
- Deliberate differences
- Possible later work

## What exists

| Project | What it offers | Limit for this use case |
|---|---|---|
| `Lum1104/Understand-Anything` → `/understand-diff` (also listed in TerminalSkills) | Maps changed files onto a prebuilt knowledge graph, follows edges to affected components, writes `diff-overlay.json` for a dashboard | Needs `/understand` to build the graph first; warns when the graph is stale; no usage-site detail |
| `swannysec/code-analysis-toolkit` → `impact-flow` | Dependency graph, blast radius per symbol, A–F health score, risk tiers by % of files affected, impact tree | Symbol-centric; no diff-scoped clickable UI; Mermaid output |
| `rysweet/amplihack` → `code-visualizer` | Colour-coded new / modified / deleted diagram, delegates syntax to a mermaid generator | Static diagrams; no usage sites |
| `lzehrung/codegraph` | Dependency graphs, find-references, PR review bundles (changed symbols, graph deltas, likely tests), cycle detection, browser graph viewer | Separate CLI to install; viewer is generic graph JSON |
| `react-component-graphify` | Import usage with line numbers, props used, export type, dead-component check | CLI text output, not diff-scoped |
| ReactGraph | Interactive React/Next.js hierarchy, cycles, prop drilling, unused components | Whole-app view, not change-scoped |
| `madge`, `skott`, `dependency-cruiser` | File-level import graphs, cycle checks, SVG/HTML output | File granularity, no diff overlay or risk reasoning |
| TypeScript AST MCP server (`component_tree`, `find_reference`) | Component tree and references via ts-morph | Needs an MCP setup; no UI |
| `borghei/claude-skills` → `monorepo-navigator` | Affected-package detection, workspace graph | Package level, not component level |

Sources: github.com/lzehrung/codegraph; skillselion.com (code-analysis-toolkit, code-visualizer, monorepo-navigator); openskillindex.com (understand-diff); github.com/WRATH2002/react-component-graphify; dev.to ReactGraph post; glama.ai TypeScript AST MCP; npm component-dependency-collapser; dev.to skott.

## Requirement → source → implementation

| Requirement | Taken from | Implemented as |
|---|---|---|
| Get the changed-file list first, then expand outward (don't read the whole graph) | understand-diff | `analyze_changes.py` starts from `git diff --name-status` and walks the import graph from there |
| Warn when the graph may be out of date or files are missing | understand-diff | The graph is rebuilt from the repo on every run, so there is no stale cache; unresolved imports are not silently dropped for deleted files |
| Write an overlay the visual layer can consume | understand-diff (`diff-overlay.json`) | One JSON file is the contract between analyzer, agent review and viewer |
| Blast radius with direct and indirect consumers, graded risk | impact-flow | `directConsumers`, `transitiveConsumers`, "Wide blast radius" signal, severity rubric |
| Colour changed nodes by new / modified / deleted | code-visualizer | Node colours plus renamed; mirrored in Mermaid export |
| Mermaid as a plain-text fallback | code-visualizer, impact-flow | `build_report.py --mermaid` |
| Changed symbols, not just changed files | codegraph | Hunk-to-export matching gives `changedSymbols`, plus added and removed exports |
| Likely tests to run | codegraph | `meta.likelyTests` and per-node "Tests that reach it" |
| Cycle detection | codegraph, ReactGraph, madge | Tarjan SCC; flags changed files inside a cycle |
| Import usage **with line numbers** | react-component-graphify | `importLine` and per-usage `line` with a code snippet |
| Props used by each consumer | react-component-graphify, TypeScript AST MCP | Multi-line JSX prop parsing, `...spread` detection |
| Unused / dead code awareness | react-component-graphify, ReactGraph | Not implemented (out of scope for a diff view); noted below |
| Interactive, click-to-inspect graph | ReactGraph, codegraph viewer | Single-file HTML viewer with side panel, focus modes and filters |

## Deliberate differences
- **Predicts breakage, not just connections.** Compares the props type before and after, then checks each render site: "required prop `size` is not passed by Modal, Tooltip, Checkout". Also removed exports still imported, and deleted or renamed paths still imported.
- **Barrel-aware.** `A → index.ts → Button` is shown, and usage through the barrel is attributed to the real component.
- **No setup.** Python 3 and git only; the viewer is one offline HTML file. Stronger indexers are optional enrichers, not prerequisites.
- **Honest about limits.** Regex-based; labelled as static analysis in the viewer.

## Possible later work
- Optional ts-morph backend for exact references and type-aware prop contracts.
- Dead-code and prop-drilling signals (ReactGraph) as extra risks.
- Graph delta view: edges added or removed by the change (codegraph).
- Language support beyond JS/TS/Vue/Svelte/Python (Go, Java, C#).
