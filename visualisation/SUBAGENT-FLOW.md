# Subagent flow for large scopes

Read only when the scope exceeds about 2 files or 150 changed lines. Produces the same page from the same `template.html`.

For a large scope the page is too much for one context: per-line notes need full attention on each file, and a long run drifts. Split it, as the architecture-review skill does with its explorer, but fan out wider. You stay the orchestrator and the only author of the shared parts.

**Why this splits cleanly.** Each file's walkthrough block depends only on that file's hunks plus the shared evidence. The diagrams, the proof section and the walkthrough do not depend on one another. The parts that need the whole picture (summary, takeaway, scope, glossary, assembly, the completeness count) stay with you.

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
