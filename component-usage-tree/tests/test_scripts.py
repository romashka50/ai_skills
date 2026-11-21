"""Regression tests for analyze_changes.py and build_report.py.

Run from the repo root:  python3 -B -m unittest discover -s component-usage-tree/tests -v
Each test builds a throwaway git repo, so only Python 3 and git are needed.
"""
import json, os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, '..', 'scripts')
sys.path.insert(0, SCRIPTS)
import analyze_changes as A  # noqa: E402
import build_report as B  # noqa: E402


def sh(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def write(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


class Repo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self._tmp.name)
        sh(self.root, 'git', 'init', '-q', '-b', 'main')
        sh(self.root, 'git', 'config', 'user.email', 't@t.t')
        sh(self.root, 'git', 'config', 'user.name', 't')

    def tearDown(self):
        self._tmp.cleanup()

    def commit(self, msg='c'):
        sh(self.root, 'git', 'add', '-A')
        sh(self.root, 'git', 'commit', '-qm', msg)

    def analyze(self, *extra):
        out = os.path.join(self.root, '.graph.json')
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'analyze_changes.py'), '--repo', self.root, '--out', out, *extra],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out, encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def node(g, nid):
        return next(n for n in g['nodes'] if n['id'] == nid)


class AnalyzerTests(Repo):
    def test_explicit_base_uses_merge_base(self):
        write(self.root, 'src/util.ts', 'export const a = 1;\n')
        self.commit('base')
        sh(self.root, 'git', 'checkout', '-q', '-b', 'feature')
        write(self.root, 'src/util.ts', 'export const a = 2;\n')
        self.commit('feat')
        sh(self.root, 'git', 'checkout', '-q', 'main')
        write(self.root, 'src/mainonly.ts', 'export const m = 1;\n')
        self.commit('main moves on')
        sh(self.root, 'git', 'checkout', '-q', 'feature')
        g = self.analyze('--base', 'main')
        changed = {n['id'] for n in g['nodes'] if n['role'] == 'changed'}
        self.assertEqual(changed, {'src/util.ts'})  # not also a "deleted" src/mainonly.ts

    def test_tsconfig_alias_with_glob_in_include(self):
        write(self.root, 'tsconfig.json', '{\n // c\n "compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["src/*"]},},\n'
                                         ' "include": ["src/**/*"], "exclude": ["**/*.spec.ts"]\n}\n')
        write(self.root, 'src/lib/f.ts', 'export const f = 1;\n')
        write(self.root, 'src/ui/a.ts', "import { f } from '@/lib/f';\nconsole.log(f);\n")
        self.commit()
        write(self.root, 'src/lib/f.ts', 'export const f = 2;\n')
        g = self.analyze()
        self.assertEqual({e['from'] for e in g['edges']}, {'src/ui/a.ts'})

    def test_tsconfig_extends_in_sub_package(self):
        write(self.root, 'packages/web/tsconfig.base.json', '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}')
        write(self.root, 'packages/web/tsconfig.json', '{"extends":"./tsconfig.base.json"}')
        write(self.root, 'packages/web/src/lib/f.ts', 'export const f = 1;\n')
        write(self.root, 'packages/web/src/ui/a.ts', "import { f } from '@/lib/f';\nconsole.log(f);\n")
        self.commit()
        write(self.root, 'packages/web/src/lib/f.ts', 'export const f = 2;\n')
        g = self.analyze()
        self.assertEqual({e['from'] for e in g['edges']}, {'packages/web/src/ui/a.ts'})

    def test_esm_js_specifier_resolves_to_ts(self):
        write(self.root, 'src/util.ts', 'export const a = 1;\n')
        write(self.root, 'src/app.ts', "import { a } from './util.js';\nconsole.log(a);\n")
        self.commit()
        write(self.root, 'src/util.ts', 'export const a = 2;\n')
        self.assertEqual(len(self.analyze()['edges']), 1)

    def test_form_feed_in_changed_file_does_not_crash(self):
        write(self.root, 'ff.py', 'x = 1\n\x0c\x0c\ny = 2\n')
        self.commit()
        write(self.root, 'ff.py', 'x = 1\n\x0c\x0c\ny = 3\n')
        g = self.analyze()
        n = self.node(g, 'ff.py')
        self.assertEqual((n['added'], n['removed']), (1, 1))

    def test_untracked_new_file_counts_lines_and_exports(self):
        write(self.root, 'src/a.ts', 'export const a = 1;\n')
        self.commit()
        write(self.root, 'src/new.ts', 'export const enum Color { R }\nexport abstract class Foo {}\nexport const { p, q: r } = obj;\n')
        g = self.analyze()
        n = self.node(g, 'src/new.ts')
        self.assertEqual(n['added'], 3)
        self.assertTrue({'Color', 'Foo', 'p', 'r'} <= set(n['exports']), n['exports'])
        self.assertNotIn('enum', n['exports'])

    def test_commonjs_removed_export_still_used(self):
        write(self.root, 'lib.js', 'exports.foo = 1;\nexports.bar = 2;\n')
        write(self.root, 'use.js', "const { foo, bar } = require('./lib');\nconsole.log(foo, bar);\n")
        self.commit()
        write(self.root, 'lib.js', 'exports.foo = 1;\n')
        g = self.analyze()
        high = [r for r in g['risks'] if r['severity'] == 'high']
        self.assertTrue(any('"bar"' in r['title'] for r in high), g['risks'])

    def test_commonjs_object_exports_and_whole_module_require(self):
        self.assertEqual(A.list_exports('module.exports = { a, b: 2, c() {} };', 'x.js'), {'a', 'b', 'c'})
        write(self.root, 'lib.js', 'module.exports = { foo, bar };\n')
        write(self.root, 'use.js', "const lib = require('./lib');\nlib.foo();\n")
        self.commit()
        write(self.root, 'lib.js', 'module.exports = { foo };\n')
        g = self.analyze()
        self.assertTrue(any('"bar"' in r['title'] and r['severity'] == 'high' for r in g['risks']), g['risks'])

    def test_python_star_import_counts_as_use(self):
        write(self.root, 'pkg/__init__.py', '')
        write(self.root, 'pkg/mod.py', 'def a(): pass\ndef b(): pass\n')
        write(self.root, 'pkg/use.py', 'from .mod import *\n')
        self.commit()
        write(self.root, 'pkg/mod.py', 'def a(): pass\n')
        g = self.analyze()
        self.assertTrue(any('"b"' in r['title'] and r['severity'] == 'high' for r in g['risks']), g['risks'])


class StripJsoncTests(unittest.TestCase):
    def test_strings_with_comment_markers_survive(self):
        raw = '{"a": "src/*", "b": "x//y", /* c */ "c": [1,],} // end'
        self.assertEqual(json.loads(A.strip_jsonc(raw)), {'a': 'src/*', 'b': 'x//y', 'c': [1]})


class BuildReportTests(Repo):
    def test_nested_details_stay_inside_the_block(self):
        html = ('<details class="file" data-node="a.ts"><summary>s</summary>'
                '<details class="hunk"><summary>h</summary>x</details><p>AFTER NESTED</p></details>'
                '<details class="file" data-node="b.ts"></details>')
        blocks = dict(B.file_blocks(html))
        self.assertIn('AFTER NESTED', blocks['a.ts'])
        self.assertNotIn('b.ts', blocks['a.ts'])
        self.assertEqual(set(blocks), {'a.ts', 'b.ts'})

    def test_rename_old_path_has_no_warning_and_json_stays_valid(self):
        write(self.root, 'src/util.ts', 'export const a = 1;\nexport const b = 2;\nexport const c = 3;\nexport const d = 4;\n')
        self.commit()
        sh(self.root, 'git', 'mv', 'src/util.ts', 'src/helpers.ts')
        g = self.analyze()
        graph = os.path.join(self.root, '.graph.json')
        guide = os.path.join(self.root, 'guide.html')
        write(self.root, 'guide.html', '<main><h2 id="before-after">x</h2><!-- IMPACT_MAP --><h2 id="walkthrough">w</h2>'
                                       '<details class="file" data-node="src/helpers.ts"><!-- c --></details></main>')
        out = os.path.join(self.root, 'out.html')
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'build_report.py'), graph, '--guide', guide, '--out', out],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('has no walkthrough block', r.stderr)
        import html as H, re
        with open(out, encoding='utf-8') as f:
            doc = f.read()
        page = H.unescape(re.search(r'srcdoc="(.*?)"></iframe>', doc, re.S).group(1))
        data = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>', page, re.S).group(1)
        json.loads(data)  # the viewer does JSON.parse on this; an HTML comment in a guide block must not break it


if __name__ == '__main__':
    unittest.main()
