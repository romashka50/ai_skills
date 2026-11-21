#!/usr/bin/env python3
"""
analyze_changes.py - map a git diff onto a usage graph.

Finds the changed files, then walks *upwards* to every file that imports them
(consumers) and *downwards* one level to what they import (dependencies).
For each consumer->changed edge it records the usage sites: the line, how the
symbol is used (render / call / member / ref) and, for JSX, which props are
passed. It also computes heuristic risk signals.

Heuristic by design: regex-based, no type information. Languages: JS/TS/JSX/TSX,
Vue, Svelte, Python. Prefer to treat output as "where to look", not as proof.

Usage:
  python analyze_changes.py --repo . [--base REF] [--head REF|WORKTREE]
                            [--depth 3] [--no-deps] [--max-sites 12]
                            --out impact-graph.json
"""
import argparse, json, os, posixpath, re, subprocess, sys, time
from collections import defaultdict, deque

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

JS_EXT = ('.ts', '.tsx', '.mts', '.cts', '.js', '.jsx', '.mjs', '.cjs', '.vue', '.svelte')
PY_EXT = ('.py',)
SRC_EXT = JS_EXT + PY_EXT
RESOLVE_EXT = ['', '.ts', '.tsx', '.mts', '.cts', '.js', '.jsx', '.mjs', '.cjs', '.vue', '.svelte', '.py']
TEST_RE = re.compile(r'(\.(test|spec)\.[jt]sx?$|(^|/)__tests__/|(^|/)tests?/|(^|/)test_[^/]*\.py$|_test\.py$|\.stories\.[jt]sx?$)')


class Repo:
    def __init__(self, root, base, head):
        self.root, self.base, self.head = root, base, head
        self._cache = {}

    def git(self, *args, check=True):
        try:
            r = subprocess.run(['git', '-C', self.root, '-c', 'core.quotepath=false', *args],
                               capture_output=True, text=True, encoding='utf-8', errors='replace')
        except FileNotFoundError:
            raise SystemExit('git was not found on PATH. Install Git and reopen the terminal.')
        if check and r.returncode != 0:
            raise SystemExit(f"git {' '.join(args)} failed: {r.stderr.strip()}")
        return r.stdout

    def read(self, path):
        if path in self._cache:
            return self._cache[path]
        try:
            if self.head == 'WORKTREE':
                with open(os.path.join(self.root, path), encoding='utf-8', errors='replace') as f:
                    t = f.read()
            else:
                t = self.git('show', f'{self.head}:{path}', check=False)
        except OSError:
            t = ''
        self._cache[path] = t
        return t

    def read_base(self, path):
        return self.git('show', f'{self.base}:{path}', check=False)


def detect_base(repo):
    cur = repo.git('rev-parse', '--abbrev-ref', 'HEAD', check=False).strip()
    for cand in ('origin/main', 'origin/master', 'main', 'master', 'develop'):
        if cur and cur != cand and repo.git('rev-parse', '--verify', '--quiet', cand, check=False).strip():
            mb = repo.git('merge-base', 'HEAD', cand, check=False).strip()
            if mb and mb != repo.git('rev-parse', 'HEAD', check=False).strip():
                return mb
    return 'HEAD'


def changed_files(repo):
    args = ['diff', '--name-status', '-M', repo.base]
    if repo.head != 'WORKTREE':
        args.append(repo.head)
    out = repo.git(*args)
    changes = {}  # path -> dict(status, renamedFrom)
    for line in out.splitlines():
        parts = line.split('\t')
        s = parts[0][0]
        if s == 'R':
            changes[parts[2]] = {'status': 'renamed', 'renamedFrom': parts[1]}
            changes[parts[1]] = {'status': 'deleted', 'renamedTo': parts[2]}
        elif s in 'AMD':
            changes[parts[1]] = {'status': {'A': 'added', 'M': 'modified', 'D': 'deleted'}[s]}
    if repo.head == 'WORKTREE':
        for p in repo.git('ls-files', '-o', '--exclude-standard').splitlines():
            changes.setdefault(p, {'status': 'added'})
    return {p: v for p, v in changes.items() if p.endswith(SRC_EXT)}


def inventory(repo):
    if repo.head == 'WORKTREE':
        files = repo.git('ls-files').splitlines() + repo.git('ls-files', '-o', '--exclude-standard').splitlines()
    else:
        files = repo.git('ls-tree', '-r', '--name-only', repo.head).splitlines()
    return {f for f in files if f.endswith(SRC_EXT)}


# ---------- alias / resolution ----------
def strip_jsonc(raw):
    """Remove // and /* */ comments and trailing commas, leaving string contents untouched."""
    out, i, n, in_str = [], 0, len(raw), False
    while i < n:
        c = raw[i]
        if in_str:
            out.append(c)
            if c == '\\' and i + 1 < n:
                out.append(raw[i + 1]); i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True; out.append(c)
        elif raw.startswith('//', i):
            while i < n and raw[i] != '\n':
                i += 1
            continue
        elif raw.startswith('/*', i):
            j = raw.find('*/', i + 2)
            i = n if j < 0 else j + 2
            continue
        else:
            out.append(c)
        i += 1
    return re.sub(r',(\s*[}\]])', r'\1', ''.join(out))


def read_tsconfig(path, seen=()):
    """Return (baseUrl_abs|None, paths|None, paths_dir) for one tsconfig, following relative `extends`."""
    path = os.path.abspath(path)
    if path in seen or not os.path.isfile(path):
        return None, None, None
    with open(path, encoding='utf-8') as f:
        cfg = json.loads(strip_jsonc(f.read()))
    here = os.path.dirname(path)
    base, paths, pdir = None, None, here
    ext = cfg.get('extends')
    for e in ([ext] if isinstance(ext, str) else (ext or [])):
        if not e.startswith('.'):
            continue  # package extends (node_modules) are not analysed
        ep = os.path.normpath(os.path.join(here, e))
        for cand in (ep, ep + '.json'):
            if os.path.isfile(cand):
                b2, p2, d2 = read_tsconfig(cand, seen + (path,))
                if b2 is not None:
                    base = b2
                if p2 is not None:
                    paths, pdir = p2, d2
                break
    co = cfg.get('compilerOptions', {}) or {}
    if co.get('baseUrl') is not None:
        base = os.path.normpath(os.path.join(here, co['baseUrl']))
    if co.get('paths'):
        paths, pdir = co['paths'], here
    return base, paths, pdir


def load_aliases(root, config_files=None):
    """Scoped aliases from every tsconfig.json / jsconfig.json (repo root and sub-packages).

    Returns (aliases, base_urls). aliases: [(scope_dir, prefix, [repo-relative target prefixes])];
    base_urls: [(scope_dir, repo-relative dir)]. A config only applies to files under its own folder."""
    if config_files is None:
        config_files = [n for n in ('tsconfig.json', 'jsconfig.json') if os.path.exists(os.path.join(root, n))]
    aliases, base_urls, warned = [], [], []

    def rel(p):
        r = os.path.relpath(p, root).replace(os.sep, '/')
        return '' if r == '.' else r

    for cf in config_files:
        full = os.path.join(root, cf)
        scope = posixpath.dirname(cf)
        try:
            base, paths, pdir = read_tsconfig(full)
        except Exception as ex:
            warned.append(f'{cf}: {ex}')
            continue
        if base is not None:
            base_urls.append((scope, rel(base)))
        for k, v in (paths or {}).items():
            anchor = base if base is not None else pdir
            aliases.append((scope, k.rstrip('*'), [rel(os.path.join(anchor, t.rstrip('*'))) + ('/' if t.endswith('*') or t.endswith('/') else '') for t in v]))
    for w in warned:
        print('warning: could not read tsconfig, aliases from it are ignored -', w, file=sys.stderr)
    return aliases, base_urls


JS_TO_TS = {'.js': ('.ts', '.tsx'), '.jsx': ('.tsx',), '.mjs': ('.mts',), '.cjs': ('.cts',)}


def try_file(cand, files):
    cand = posixpath.normpath(cand).replace('\\', '/')
    # NodeNext/ESM style: "./util.js" in source points at util.ts
    stem, ext0 = posixpath.splitext(cand)
    for alt in JS_TO_TS.get(ext0, ()):
        if stem + alt in files:
            return stem + alt
    for ext in RESOLVE_EXT:
        if cand + ext in files:
            return cand + ext
    for ext in RESOLVE_EXT[1:]:
        if f'{cand}/index{ext}' in files:
            return f'{cand}/index{ext}'
    if f'{cand}/__init__.py' in files:
        return f'{cand}/__init__.py'
    return None


def in_scope(scope, src):
    return scope == '' or src.startswith(scope + '/')


def resolve_js(spec, src, files, aliases, base_urls):
    if spec.startswith('.'):
        return try_file(posixpath.join(posixpath.dirname(src), spec), files)
    for scope, prefix, targets in aliases:
        if not prefix or not in_scope(scope, src):
            continue
        wildcard = prefix.endswith('/') or any(t.endswith('/') for t in targets)
        if (wildcard and spec.startswith(prefix)) or spec == prefix:
            for t in targets:
                r = try_file(t + spec[len(prefix):] if t.endswith('/') else t, files)
                if r:
                    return r
    for scope, bdir in sorted(base_urls, key=lambda x: -len(x[0])):
        if in_scope(scope, src):
            r = try_file(posixpath.join(bdir, spec), files)
            if r:
                return r
    return None


def resolve_py(mod, level, src, files):
    parts = [p for p in mod.split('.') if p]
    if level:
        d = posixpath.dirname(src)
        for _ in range(level - 1):
            d = posixpath.dirname(d)
        return try_file(posixpath.join(d, *parts), files) if parts else (try_file(d, files))
    roots = ['', 'src', posixpath.dirname(src).split('/')[0] if '/' in src else '']
    for r in roots:
        res = try_file(posixpath.join(r, *parts), files)
        if res:
            return res
    return None


# ---------- parsing ----------
def parse_names(clause):
    out = []
    for item in clause.split(','):
        item = re.sub(r'^\s*type\s+', '', item.strip())
        if not item:
            continue
        m = re.match(r'([\w$]+)(?:\s+as\s+([\w$]+))?$', item)
        if m:
            out.append((m.group(1), m.group(2) or m.group(1)))
    return out


def lineno(text, pos):
    return text.count('\n', 0, pos) + 1


def parse_js_imports(text, src, files, aliases, base_url):
    res = []

    def add(spec, names, m, kind):
        res.append({'spec': spec, 'target': resolve_js(spec, src, files, aliases, base_url),
                    'names': names, 'line': lineno(text, m.start()),
                    'endLine': lineno(text, m.end()), 'kind': kind})

    for m in re.finditer(r'import\s+(?:type\s+)?(?:([\w$]+)\s*,?\s*)?(?:\{([^}]*)\})?\s*(?:\*\s+as\s+([\w$]+))?\s*from\s*[\'"]([^\'"]+)[\'"]', text):
        names = []
        if m.group(1):
            names.append(('default', m.group(1)))
        if m.group(2):
            names += parse_names(m.group(2))
        if m.group(3):
            names.append(('*', m.group(3)))
        add(m.group(4), names, m, 'import')
    for m in re.finditer(r'(?m)^\s*import\s*[\'"]([^\'"]+)[\'"]', text):
        add(m.group(1), [], m, 'import')
    for m in re.finditer(r'export\s+(?:type\s+)?(\*(?:\s+as\s+([\w$]+))?|\{([^}]*)\})\s*from\s*[\'"]([^\'"]+)[\'"]', text):
        names = parse_names(m.group(3)) if m.group(3) else [('*', m.group(2) or '*')]
        add(m.group(4), [(a, '') for a, _ in names], m, 'reexport')
        res[-1]['exposed'] = names
    for m in re.finditer(r'(?:(?:const|let|var)\s+(?:([\w$]+)|\{([^}]*)\})\s*=\s*)?require\(\s*[\'"]([^\'"]+)[\'"]\s*\)', text):
        # `const lib = require(x)` binds the whole module (CommonJS has no default/named split)
        names = [('*', m.group(1))] if m.group(1) else (parse_names(m.group(2).replace(':', ' as ')) if m.group(2) else [])
        add(m.group(3), names, m, 'require')
    for m in re.finditer(r'(?:([\w$]+)\s*=\s*(?:\w+\.)?lazy\(\s*\(\)\s*=>\s*)?import\(\s*[\'"]([^\'"]+)[\'"]\s*\)', text):
        add(m.group(2), [('default', m.group(1))] if m.group(1) else [], m, 'lazy')
    return res


def parse_py_imports(text, src, files):
    res, lines, i = [], text.split('\n'), 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r'\s*from\s+(\.*)([\w.]*)\s+import\s+(.+)$', ln)
        if m:
            clause, start = m.group(3), i
            if '(' in clause and ')' not in clause:
                while i + 1 < len(lines) and ')' not in lines[i]:
                    i += 1
                    clause += ' ' + lines[i]
            clause = clause.replace('(', '').replace(')', '').split('#')[0]
            names = [('*', '')] if clause.strip() == '*' else parse_names(clause)  # `from x import *` uses the whole module
            target = resolve_py(m.group(2), len(m.group(1)), src, files)
            # "from pkg import submodule"
            for a, b in names:
                sub = resolve_py((m.group(2) + '.' + a).strip('.'), len(m.group(1)), src, files)
                if sub and (not target or target.endswith('__init__.py')):
                    res.append({'spec': a, 'target': sub, 'names': [('*', b)], 'line': start + 1,
                                'endLine': i + 1, 'kind': 'import'})
            if target:
                res.append({'spec': m.group(2), 'target': target, 'names': names,
                            'line': start + 1, 'endLine': i + 1, 'kind': 'import'})
        else:
            m = re.match(r'\s*import\s+([\w.]+(?:\s+as\s+\w+)?(?:\s*,\s*[\w.]+(?:\s+as\s+\w+)?)*)', ln)
            if m:
                for part in m.group(1).split(','):
                    pm = re.match(r'\s*([\w.]+)(?:\s+as\s+(\w+))?', part)
                    target = resolve_py(pm.group(1), 0, src, files)
                    if target:
                        res.append({'spec': pm.group(1), 'target': target,
                                    'names': [('*', pm.group(2) or pm.group(1).split('.')[0])],
                                    'line': i + 1, 'endLine': i + 1, 'kind': 'import'})
        i += 1
    return res


def parse_imports(text, path, files, aliases, base_url):
    return parse_py_imports(text, path, files) if path.endswith('.py') else parse_js_imports(text, path, files, aliases, base_url)


EXPORT_PATTERNS = [
    r'export\s+default\s+(?:abstract\s+)?(?:async\s+)?(?:function\*?|class)\s+([\w$]+)',
    r'export\s+(?:declare\s+)?(?:abstract\s+)?(?:async\s+)?(?:function\*?|class|(?:const\s+)?enum|const|let|var|type|interface|namespace)\s+([\w$]+)',
]


def list_exports(text, path):
    ex = set()
    if path.endswith('.py'):
        for m in re.finditer(r'(?m)^(?:async\s+def|def|class)\s+([A-Za-z]\w*)', text):
            ex.add(m.group(1))
        for m in re.finditer(r'(?m)^([A-Z][A-Z0-9_]*)\s*=', text):
            ex.add(m.group(1))
        return ex
    for p in EXPORT_PATTERNS:
        for m in re.finditer(p, text):
            ex.add(m.group(1))
            if 'default' in m.group(0).split(m.group(1))[0]:
                ex.add('default')
    for m in re.finditer(r'export\s*\{([^}]*)\}(?!\s*from)', text):
        for a, b in parse_names(m.group(1)):
            ex.add(b)
    for m in re.finditer(r'export\s+(?:const|let|var)\s*\{([^}]*)\}', text):  # export const { a, b } = obj
        for a, b in parse_names(re.sub(r':\s*', ' as ', m.group(1))):
            ex.add(b)
    # CommonJS
    for m in re.finditer(r'(?m)^\s*(?:module\.)?exports\.([\w$]+)\s*=', text):
        ex.add(m.group(1))
    for m in re.finditer(r'module\.exports\s*=\s*\{([^}]*)\}', text):
        for item in m.group(1).split(','):
            km = re.match(r'\s*([\w$]+)\s*(?::|$|\()', item)
            if km:
                ex.add(km.group(1))
    if re.search(r'module\.exports\s*=(?!\s*\{)', text):
        ex.add('default')
    if re.search(r'export\s+default\b', text):
        ex.add('default')
    if path.endswith(('.vue', '.svelte')):
        ex.add('default')
    return ex


def symbol_lines(text, names):
    out = {}
    for n in names:
        if n == 'default':
            continue
        m = re.search(r'(?:function\*?|class|const|let|var|def|interface|type|enum)\s+' + re.escape(n) + r'\b', text)
        if m:
            out[n] = lineno(text, m.start())
    return out


def diff_hunks(repo, path):
    args = ['diff', '-U0', repo.base]
    if repo.head != 'WORKTREE':
        args.append(repo.head)
    out = repo.git(*args, '--', path, check=False)
    hunks, added_removed = [], []
    # split on '\n' only: str.splitlines() also splits on form feed and U+2028 that can sit inside a code line
    for line in out.split('\n'):
        m = re.match(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', line)
        if m:
            s, c = int(m.group(1)), int(m.group(2) or 1)
            hunks.append((s, s + max(c, 1) - 1))
        elif line and line[0] in '+-' and not line.startswith(('+++', '---')):
            added_removed.append(line)
    return hunks, added_removed


def jsx_props(text, pos):
    depth, buf, quote, spread = 0, [], None, False
    for ch_i in range(pos, min(len(text), pos + 1500)):
        ch = text[ch_i]
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in '"\'`':
            quote = ch
            continue
        if ch == '{':
            if depth == 0 and re.match(r'\{\s*\.\.\.', text[ch_i:ch_i + 12]):
                spread = True
            depth += 1
            continue
        if ch == '}':
            depth = max(0, depth - 1)
            continue
        if depth == 0:
            if ch == '>':
                break
            buf.append(ch)
    props = [t for t in re.findall(r'[A-Za-z_][\w:.-]*', ''.join(buf))]
    return props + (['...spread'] if spread else [])


def usage_sites(text, locals_, skip_ranges, max_sites):
    lines = text.split('\n')
    starts, off = [], 0
    for ln in lines:
        starts.append(off)
        off += len(ln) + 1
    sites, total = [], 0
    for i, ln in enumerate(lines, 1):
        if any(a <= i <= b for a, b in skip_ranges):
            continue
        for L in locals_:
            if not L or L == '*':
                continue
            m = re.search(r'(?<![\w$.])' + re.escape(L) + r'(?![\w$])', ln)
            if not m:
                continue
            total += 1
            jsx = re.search(r'<' + re.escape(L) + r'(?![\w$])', ln)
            if jsx:
                kind, props = 'render', jsx_props(text, starts[i - 1] + jsx.end())
            elif re.search(re.escape(L) + r'\s*\(', ln):
                kind, props = 'call', []
            elif re.search(re.escape(L) + r'\.', ln):
                kind, props = 'member', []
            else:
                kind, props = 'ref', []
            if len(sites) < max_sites:
                sites.append({'line': i, 'kind': kind, 'symbol': L, 'props': props, 'snippet': ln.strip()[:140]})
            break
    return sites, total


def node_kind(path, text, exports):
    base = posixpath.basename(path)
    stem = base.split('.')[0]
    if TEST_RE.search(path):
        return 'test'
    if re.search(r'(^|/)(hooks?)/', path) or re.match(r'use[A-Z]', stem):
        return 'hook'
    if path.endswith(('.vue', '.svelte')) or (path.endswith(('.tsx', '.jsx')) and stem[:1].isupper()) or \
            (path.endswith(('.tsx', '.jsx')) and re.search(r'<[A-Z][\w.]*|<[a-z]+[\s>]', text)):
        if re.search(r'(^|/)(pages?|app|routes?|views?|screens?)/', path):
            return 'page'
        return 'component'
    if base.startswith('index.') and text.count('export') and len(re.findall(r'(?m)^export\s.*from', text)) >= max(1, text.count('\n') // 3):
        return 'barrel'
    if path.endswith('.py'):
        return 'module'
    return 'module'


def parse_props(text):
    """TS only: {propName: required?} from the first interface/type named *Props*."""
    m = re.search(r'(?:interface|type)\s+\w*Props\w*\s*(?:=\s*)?(?:extends[^{]*)?\{([^{}]*)\}', text)
    if not m:
        return None
    props = {}
    for part in re.split(r'[;\n,]', m.group(1)):
        pm = re.match(r'\s*(?:readonly\s+)?([\w$]+)(\?)?\s*:', part)
        if pm:
            props[pm.group(1)] = not pm.group(2)
    return props


def tarjan(adj):
    index, low, onstack, stack, res, idx = {}, {}, set(), [], [], 0
    for v in list(adj):
        if v in index:
            continue
        work = [(v, iter(adj[v]))]
        index[v] = low[v] = idx; idx += 1; stack.append(v); onstack.add(v)
        while work:
            node, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = idx; idx += 1; stack.append(w); onstack.add(w)
                    work.append((w, iter(adj.get(w, ())))); advanced = True
                    break
                elif w in onstack:
                    low[node] = min(low[node], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop(); onstack.discard(w); comp.append(w)
                    if w == node:
                        break
                res.append(comp)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default='.')
    ap.add_argument('--base')
    ap.add_argument('--head', default='WORKTREE')
    ap.add_argument('--depth', type=int, default=3)
    ap.add_argument('--no-deps', action='store_true')
    ap.add_argument('--max-sites', type=int, default=12)
    ap.add_argument('--out', default='impact-graph.json')
    a = ap.parse_args()

    root = os.path.abspath(a.repo)
    repo = Repo(root, a.base, a.head)
    if a.base:
        # A branch name means "since it diverged", like `git diff base...head`: use the merge-base,
        # otherwise commits that landed on the base branch after the fork show up as reverse changes.
        mb = repo.git('merge-base', a.base, 'HEAD' if a.head == 'WORKTREE' else a.head, check=False).strip()
        repo.base = mb or a.base
    else:
        repo.base = detect_base(repo)
    changes = changed_files(repo)
    if not changes:
        raise SystemExit('No changed source files found (checked ' + ', '.join(SRC_EXT) + '). Try --base <ref>.')

    files = inventory(repo)
    deleted = {p for p, v in changes.items() if v['status'] == 'deleted'}
    resolvable = files | deleted
    cfgs = [f for f in (repo.git('ls-files', '*tsconfig.json', '*jsconfig.json', check=False).splitlines())
            if posixpath.basename(f) in ('tsconfig.json', 'jsconfig.json')]
    aliases, base_url = load_aliases(root, cfgs)

    # parse every source file once
    parsed = {}
    for f in sorted(files):
        t = repo.read(f)
        parsed[f] = parse_imports(t, f, resolvable, aliases, base_url)
    importers = defaultdict(list)  # target -> [(consumer, importRecord)]
    adj = {f: set() for f in files}
    for f, imps in parsed.items():
        for imp in imps:
            if imp['target']:
                importers[imp['target']].append((f, imp))
                if imp['target'] in adj:
                    adj[f].add(imp['target'])

    # BFS upward
    depth_of = {p: 0 for p in changes}
    q, edge_keys = deque(changes), set()
    while q:
        t = q.popleft()
        for c, imp in importers.get(t, []):
            if c == t:
                continue
            if c not in depth_of:
                if depth_of[t] + 1 > a.depth:
                    continue
                depth_of[c] = depth_of[t] + 1
                q.append(c)
            if depth_of[c] > depth_of[t] or (c in changes and t in changes):
                edge_keys.add((c, t))
    # lateral edges into barrels (index files that re-export): keeps "A -> index -> Changed" visible
    for t in list(depth_of):
        if depth_of[t] > 0 and t not in changes and node_kind(t, repo.read(t), set()) == 'barrel':
            for c, imp in importers.get(t, []):
                if c in depth_of and c != t and depth_of[c] >= 0:
                    edge_keys.add((c, t))
    # downward (dependencies), one level
    if not a.no_deps:
        for p, v in changes.items():
            if v['status'] == 'deleted':
                continue
            for imp in parsed.get(p, []):
                t = imp['target']
                if t and t in files and t != p:
                    if t not in depth_of:
                        depth_of[t] = -1
                    if depth_of[t] == -1 or t in changes:
                        edge_keys.add((p, t))

    # build edges with usage sites
    edges = []
    for c, t in sorted(edge_keys):
        recs = [imp for cc, imp in importers.get(t, []) if cc == c]
        if not recs:
            continue
        names, locals_, skip, line = [], [], [], recs[0]['line']
        kinds, bindings, exposed = set(), [], []
        for imp in recs:
            if imp['kind'] == 'reexport':
                exposed += [list(x) for x in imp.get('exposed', [])]
            else:
                bindings += [[x, y] for x, y in imp['names'] if y]
            names += [n for n, _ in imp['names']]
            locals_ += [l for _, l in imp['names']]
            skip.append((imp['line'], imp['endLine']))
            kinds.add(imp['kind'])
        sites, total = usage_sites(repo.read(c), locals_, skip, a.max_sites)
        edges.append({'from': c, 'to': t, 'names': sorted(set(names)), 'importLine': line,
                      'via': sorted(kinds), 'usages': sites, 'totalUses': total,
                      'bindings': bindings, 'exposed': exposed})

    # nodes
    nodes, exports_now = {}, {}
    for p, d in depth_of.items():
        text = repo.read(p)
        ch = changes.get(p)
        exports_now[p] = list_exports(text, p) if p in files else set()
        n = {'id': p, 'label': posixpath.basename(p), 'dir': posixpath.dirname(p),
             'kind': node_kind(p, text, exports_now[p]) if p in files else 'module',
             'role': 'changed' if ch else ('consumer' if d > 0 else 'dependency'),
             'depth': d, 'status': ch['status'] if ch else 'unchanged',
             'exports': sorted(exports_now[p]), 'added': 0, 'removed': 0,
             'changedSymbols': [], 'removedExports': [], 'addedExports': []}
        if ch:
            n.update({k: v for k, v in ch.items() if k != 'status'})
            hunks, lines = diff_hunks(repo, p)
            n['added'] = sum(1 for l in lines if l[0] == '+')
            n['removed'] = sum(1 for l in lines if l[0] == '-')
            if ch['status'] == 'added' and not lines and text:
                # untracked file: git diff does not see it, so every line is an addition
                n['added'] = text.count('\n') + (0 if text.endswith('\n') else 1)
            n['_difflines'] = lines
            if ch['status'] == 'added':
                n['changedSymbols'] = sorted(exports_now[p])
            elif ch['status'] != 'deleted':
                sl = sorted(symbol_lines(text, exports_now[p]).items(), key=lambda kv: kv[1])
                for i, (name, start) in enumerate(sl):
                    end = sl[i + 1][1] - 1 if i + 1 < len(sl) else 10 ** 9
                    if any(h0 <= end and h1 >= start for h0, h1 in hunks):
                        n['changedSymbols'].append(name)
            old_path = ch.get('renamedFrom', p)
            if ch['status'] in ('modified', 'renamed'):
                before = list_exports(repo.read_base(old_path), old_path)
                n['removedExports'] = sorted(before - exports_now[p])
                n['addedExports'] = sorted(exports_now[p] - before)
        nodes[p] = n
    fan_in = defaultdict(set)
    for e in edges:
        fan_in[e['to']].add(e['from'])
    for p, n in nodes.items():
        n['fanIn'] = len({c for c, _ in importers.get(p, [])})
        n['fanOut'] = len({i['target'] for i in parsed.get(p, []) if i['target']})

    # layout layer: longest path from the changed set (consumers sit to the left of what they use)
    layer = {p: 0 for p in nodes if nodes[p]['role'] == 'changed'}
    for p, n in nodes.items():
        layer.setdefault(p, -1 if n['role'] == 'dependency' else n['depth'])
    cap = a.depth + 2
    for _ in range(12):
        moved = False
        for e in edges:
            c, t = e['from'], e['to']
            if nodes[c]['role'] == 'consumer' and nodes[t]['role'] != 'dependency' and layer[c] <= layer[t] and layer[t] + 1 <= cap:
                layer[c] = layer[t] + 1; moved = True
        if not moved:
            break
    for p, n in nodes.items():
        n['layer'] = layer[p]

    # ---------- risks ----------
    risks, rid = [], 0

    def risk(sev, node, title, detail, related=()):
        nonlocal rid
        rid += 1
        risks.append({'id': f'r{rid}', 'severity': sev, 'nodeId': node, 'title': title,
                      'detail': detail, 'related': sorted(set(related))})

    # transitive consumers per changed node
    def upstream(start):
        seen, qq = set(), deque([start])
        while qq:
            x = qq.popleft()
            for c, _ in importers.get(x, []):
                if c not in seen and c != start:
                    seen.add(c); qq.append(c)
        return seen

    scc_of = {}
    for comp in tarjan(adj):
        if len(comp) > 1:
            for v in comp:
                scc_of[v] = comp

    def indirect_usages(p):
        res = []
        for e2 in edges:
            if e2['to'] != p or 'reexport' not in e2['via']:
                continue
            b = e2['from']
            exposed = set()
            for orig, exp in e2['exposed']:
                if orig == '*':
                    exposed |= {x for x in exports_now.get(p, ()) if x != 'default'} | {exp}
                else:
                    exposed.add(exp)
            for e1 in edges:
                if e1['to'] != b or e1['from'] == p:
                    continue
                locs = {loc for imp_n, loc in e1['bindings'] if imp_n in exposed or imp_n == '*'}
                sites = [x for x in e1['usages'] if x['symbol'] in locs]
                if locs:
                    res.append({'consumer': e1['from'], 'barrel': b, 'importLine': e1['importLine'],
                                'names': sorted(n_ for n_, l_ in e1['bindings'] if l_ in locs), 'usages': sites})
        return res

    def render_users(p):
        out = []
        for e in edges:
            if e['to'] == p:
                out += [(e['from'], x) for x in e['usages'] if x['kind'] == 'render']
        for ind in nodes[p].get('indirectUsages', []):
            out += [(ind['consumer'], x) for x in ind['usages'] if x['kind'] == 'render']
        return out

    for p, n in nodes.items():
        if n['role'] == 'changed':
            n['indirectUsages'] = indirect_usages(p)

    likely_tests = set()
    for p, n in nodes.items():
        if n['role'] != 'changed':
            continue
        direct = sorted({c for c, _ in importers.get(p, []) if c != p})
        trans = upstream(p)
        direct_all = sorted(set(direct) | {i['consumer'] for i in n.get('indirectUsages', [])})
        tests = sorted(c for c in trans if TEST_RE.search(c) and not c.endswith(('.stories.tsx', '.stories.jsx', '.stories.js', '.stories.ts')))
        likely_tests.update(tests)
        n['directConsumers'], n['transitiveConsumers'], n['tests'] = len(direct_all), len(trans), tests

        if n['status'] == 'deleted' and direct and not n.get('renamedTo'):
            risk('high', p, 'Deleted file is still imported',
                 f'{len(direct)} file(s) still import this path. They will fail to resolve unless updated in the same change.', direct)
        for name in n['removedExports']:
            users = [e['from'] for e in edges if e['to'] == p and (name in e['names'] or '*' in e['names'])]
            if name == 'default':
                users = [e['from'] for e in edges if e['to'] == p and ('default' in e['names'] or '*' in e['names'])]
            if users:
                risk('high', p, f'Removed export "{name}" is still used',
                     f'{len(users)} consumer(s) import "{name}" (or the whole module).', users)
            else:
                risk('low', p, f'Export "{name}" removed', 'No analysed consumer imports it; confirm nothing outside the repo (or via dynamic access) does.')
        if n['status'] == 'renamed' and n.get('renamedFrom') in deleted:
            old_users = [c for c, _ in importers.get(n['renamedFrom'], [])]
            if old_users:
                risk('high', p, 'Renamed file: importers still use the old path',
                     f'{len(old_users)} file(s) import {n["renamedFrom"]}.', old_users)
        if n['status'] in ('modified', 'renamed') and n['kind'] in ('component', 'page'):
            now_p, old_p = parse_props(repo.read(p)), parse_props(repo.read_base(n.get('renamedFrom', p)))
            if now_p is not None and old_p is not None:
                newly_req = [k for k, req in now_p.items() if req and not old_p.get(k, False)]
                gone = [k for k in old_p if k not in now_p]
                n['propChanges'] = {'newlyRequired': newly_req, 'removed': gone}
                for k in newly_req:
                    miss = sorted({c for c, x in render_users(p) if k not in x['props'] and '...spread' not in x['props']})
                    if miss:
                        risk('high', p, f'Required prop "{k}" is not passed by {len(miss)} consumer(s)',
                             f'"{k}" is required now ' + ('(new prop).' if k not in old_p else '(was optional).') +
                             ' These render sites do not pass it.', miss)
                for k in gone:
                    still = sorted({c for c, x in render_users(p) if k in x['props']})
                    if still:
                        risk('medium', p, f'Prop "{k}" removed but still passed',
                             'Consumers still pass a prop that no longer exists in the props type.', still)
        if n['status'] != 'deleted' and any(re.search(r'\bprops\b|Props\b|propTypes|PropTypes|defineProps|export let ', l) for l in n.get('_difflines', [])):
            ru = render_users(p)
            if ru:
                passed = sorted({pr for _, x in ru for pr in x['props']})
                risk('medium', p, 'Props contract may have changed',
                     'Diff touches props/prop types. Check every render site below passes the right props'
                     + (f' (props currently passed by consumers: {", ".join(passed)}).' if passed else '.'),
                     [c for c, _ in ru])
        if len(direct) >= 5 or len(trans) >= 10:
            risk('medium', p, 'Wide blast radius', f'{len(direct)} direct and {len(trans)} transitive consumers.', direct)
        if p in scc_of:
            risk('medium', p, 'Part of a circular dependency', ' -> '.join(sorted(scc_of[p])[:6]) + (' ...' if len(scc_of[p]) > 6 else ''), scc_of[p])
        areas = {'/'.join(c.split('/')[:2]) for c in direct}
        if len(areas) >= 3:
            risk('low', p, f'Used across {len(areas)} areas', ', '.join(sorted(areas)[:6]), direct)
        if n['status'] != 'deleted' and n['kind'] != 'test' and not tests:
            risk('low', p, 'No test reaches this file', 'No test file imports it directly or transitively (within analysed depth of the import graph).')
        n.pop('_difflines', None)
    for n in nodes.values():
        n.pop('_difflines', None)

    order = {'high': 0, 'medium': 1, 'low': 2}
    risks.sort(key=lambda r: (order[r['severity']], r['nodeId']))
    out = {
        'meta': {'repo': os.path.basename(root), 'base': repo.base, 'head': a.head, 'depth': a.depth,
                 'generated': time.strftime('%Y-%m-%d %H:%M'), 'heuristic': True,
                 'languages': sorted({os.path.splitext(p)[1] for p in nodes}),
                 'likelyTests': sorted(likely_tests),
                 'stats': {'changed': sum(1 for n in nodes.values() if n['role'] == 'changed'),
                           'consumers': sum(1 for n in nodes.values() if n['role'] == 'consumer'),
                           'dependencies': sum(1 for n in nodes.values() if n['role'] == 'dependency'),
                           'risks': len(risks)}},
        'nodes': sorted(nodes.values(), key=lambda n: (n['depth'] if n['depth'] >= 0 else 99, n['id'])),
        'edges': edges, 'risks': risks,
    }
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
    s = out['meta']['stats']
    print(f"{a.out}: {s['changed']} changed, {s['consumers']} consumers, {s['dependencies']} dependencies, "
          f"{len(edges)} edges, {s['risks']} auto-detected risks (base={repo.base})", file=sys.stderr)


if __name__ == '__main__':
    main()
