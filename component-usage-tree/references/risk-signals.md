# Risk signals

Use this when reviewing the diff in step 3. The analyzer already raises the items marked **(auto)**; your job is the rest. Each signal says what to look at in the consumer sites the viewer shows.

## Contents
- Severity rubric
- By kind of change
- Questions to ask for every changed file
- Phrasing findings

## Severity rubric
| Level | Meaning | Examples |
|---|---|---|
| high | Very likely breaks at build or runtime | Import of a deleted or renamed path **(auto)**; removed export still imported **(auto)**; newly required prop not passed **(auto)**; function signature gained a required argument that callers omit |
| medium | Behaviour may change for callers | Props type touched **(auto)**; return shape or default changed; wide blast radius **(auto)**; circular dependency **(auto)**; new context or provider requirement; changed event name or payload |
| low | Housekeeping or coverage | No test reaches the file **(auto)**; used across many areas **(auto)**; export removed with no analysed consumer **(auto)** |

## By kind of change

### Component (React, Vue, Svelte)
- Props: new required, removed, renamed, type narrowed, default changed. Compare against "props passed" at each render site. Spread props (`...spread` chip) hide what is passed, so say so.
- Children or slots: now required, or different shape.
- Context, store or provider now needed. Check that every consumer renders under that provider (pages usually do, isolated tests and stories often don't).
- Events: renamed callbacks, changed payload, now fires at a different time.
- Rendering contract: wrapper element, `ref` forwarding, `key`, CSS class names that consumers or tests select on.
- Accessibility: changed roles, labels or focus behaviour that tests or other components depend on.

### Hook or composable
- Return shape (object ↔ tuple, renamed fields). Look at destructuring on each call line.
- Arguments: new required parameter, changed meaning.
- Rules of hooks: now conditionally called, or reads a context the caller may not have.
- Dependency array or memoisation changes that alter how often consumers re-render.

### Utility or service module
- Output format or rounding changed, case, trimming, locale, timezone. Snapshot tests and comparisons will move.
- Throws instead of returning null (or the reverse): check consumers' error handling.
- Sync ↔ async change: callers that don't `await`.
- Side effects added (network, storage, global state).

### Python module
- Function signature changes (positional order, new required args), changed return type, newly raised exceptions.
- Module-level constants and import-time side effects. Importers run them on import.
- `__init__.py` re-exports: removing a name there breaks `from pkg import name` for outside callers.

### Barrel / index files
- Removing or renaming a re-export breaks every importer of the barrel, not only the file behind it. The viewer shows "through barrel" usage.
- Adding a re-export can create circular imports.

### Deleted or renamed files
- Importers must be updated in the same change. Also check non-code references: dynamic imports with computed paths, config files, docs, route tables, lazy-loaded chunks.

### Types and interfaces only
- Type-only changes don't fail at runtime but can fail the build. Look for consumers that construct or narrow that type.

## Questions to ask for every changed file
1. Which consumers sit in a different area of the codebase from this file (a page using a shared component)? Those are the ones owners forget.
2. Is there a test that exercises the changed behaviour, or does the "tests that reach it" list only prove it is imported?
3. Could anything reach this file in a way the analyzer can't follow: `import(variable)`, string-keyed registries, plugin loading, reflection, code generated at build time?
4. Does the change alter anything the user can see (copy, layout, ordering) that a type checker would never catch?

## Phrasing findings
- Lead with the consequence, then the evidence: "3 callers don't pass `size`, which is now required (Modal, Tooltip, Checkout)."
- Anchor `nodeId` on the changed file, and list affected consumers in `related` so they ring up on click.
- If unsure, say what to verify rather than asserting a bug.
