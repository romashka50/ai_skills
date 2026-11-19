# Environment and scope

Shared by `visualisation`, `change-impact-map`, `component-usage-tree` and `guided-implementation`. Section numbers (§0, §1) are stable.

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
