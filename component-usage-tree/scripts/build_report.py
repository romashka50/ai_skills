#!/usr/bin/env python3
"""
build_report.py - render impact-graph.json into one self-contained, clickable HTML file.

Usage:
  python build_report.py impact-graph.json [--out impact-map.html] [--guide guide.html] [--title "..."] [--mermaid impact.mmd]

The JSON is the output of analyze_changes.py, optionally enriched by the agent:
  meta.summary            one or two plain sentences shown on the overview
  risks[]                 extra findings, each {severity: high|medium|low, nodeId, title,
                          detail, related: [nodeIds], source: "review"}
  nodes[].note            a short note shown on that node's panel
Anything that does not reference a real node id is dropped with a warning, so the
viewer never shows a dangling link.
"""
import argparse, datetime, html, json, os, re, sys

SEVS = {'high', 'medium', 'low'}


def validate(g):
    ids = {n['id'] for n in g['nodes']}
    warn = []
    clean = []
    seen = {r.get('id') for r in g['risks'] if r.get('id')}
    nxt = len(g['risks']) + 1
    for r in g['risks']:
        if r.get('severity') not in SEVS:
            warn.append(f"risk '{r.get('title')}': bad severity {r.get('severity')!r}, dropped")
            continue
        if r.get('nodeId') not in ids:
            warn.append(f"risk '{r.get('title')}': nodeId {r.get('nodeId')!r} not in graph, dropped")
            continue
        if not r.get('id'):
            while f'r{nxt}' in seen:
                nxt += 1
            r['id'] = f'r{nxt}'; seen.add(r['id'])
        rel = [x for x in r.get('related', []) if x in ids]
        if len(rel) != len(r.get('related', [])):
            warn.append(f"risk '{r['title']}': removed unknown related ids")
        r['related'] = rel
        r.setdefault('detail', '')
        clean.append(r)
    order = {'high': 0, 'medium': 1, 'low': 2}
    clean.sort(key=lambda r: (order[r['severity']], r['nodeId']))
    g['risks'] = clean
    g['meta']['stats']['risks'] = len(clean)
    return warn


FILE_BLOCK = re.compile(r'<details\b[^>]*\bdata-node="([^"]+)"[^>]*>.*?</details>', re.S)


def attach_guides(g, guide_html):
    """Copy each walkthrough block (<details class="file" data-node="path">) onto its graph node."""
    ids = {n['id']: n for n in g['nodes']}
    warn, found = [], set()
    for m in FILE_BLOCK.finditer(guide_html):
        node_id = html.unescape(m.group(1))
        block = re.sub(r'<script\b.*?</script>', '', m.group(0), flags=re.S | re.I)
        block = re.sub(r'\son\w+="[^"]*"', '', block)
        if node_id not in ids:
            warn.append(f"walkthrough block data-node={node_id!r} matches no graph node, not linked")
            continue
        opening = block[:block.index('>') + 1]
        if not re.search(r'\sopen\b', opening):
            block = block.replace('<details', '<details open', 1)
        ids[node_id]['guide'] = block
        found.add(node_id)
    for n in g['nodes']:
        if n['role'] == 'changed' and n['id'] not in found:
            warn.append(f"changed file {n['id']} has no walkthrough block (data-node) in the guide")
    g['meta']['hasGuide'] = True
    return warn


GLUE = """<script>
addEventListener('message', function (e) {
  var d = e.data; if (!d || d.cim !== 'walk') return;
  var nodes = document.querySelectorAll('details.file[data-node]');
  for (var i = 0; i < nodes.length; i++) if (nodes[i].getAttribute('data-node') === d.id) { nodes[i].open = true; nodes[i].scrollIntoView({ behavior: 'smooth', block: 'start' }); return; }
});
</script>"""


def embed(guide_html, viewer_html):
    frame = ('<h2 id="impact-map">Usage tree</h2>\n'
             '<p class="meta">Click a file to see what changed, why, and everywhere it is used. Static analysis: a map of where to look, not proof.</p>\n'
             '<iframe id="impact-frame" title="Component usage tree" loading="lazy" '
             'style="width:100%;height:85vh;min-height:560px;border:1px solid var(--border);border-radius:10px;background:var(--surface)" '
             'srcdoc="' + html.escape(viewer_html, quote=True) + '"></iframe>\n' + GLUE + '\n')
    if '<!-- IMPACT_MAP -->' in guide_html:
        out = guide_html.replace('<!-- IMPACT_MAP -->', frame, 1)
    elif '<h2 id="walkthrough"' in guide_html:
        out = guide_html.replace('<h2 id="walkthrough"', frame + '<h2 id="walkthrough"', 1)
    else:
        out = guide_html.replace('</main>', frame + '</main>', 1)
    toc = '<li><a href="#impact-map">Usage tree</a></li>'
    if 'href="#impact-map"' not in out:
        out = re.sub(r'(<li><a href="#before-after">.*?</li>)', lambda m: m.group(1) + '\n      ' + toc, out, count=1, flags=re.S)
    return out


def mermaid(g):
    """Plain-text fallback for PR comments / terminals: changed=amber/green/red, consumers=grey."""
    ids = {n['id']: f'n{i}' for i, n in enumerate(g['nodes'])}
    risky = {r['nodeId'] for r in g['risks'] if r['severity'] == 'high'} | {x for r in g['risks'] if r['severity'] == 'high' for x in r.get('related', [])}
    lines = ['flowchart LR']
    for n in g['nodes']:
        label = n['label'].replace('"', "'") + ('<br/>' + n['status'] if n['role'] == 'changed' else '')
        lines.append(f'  {ids[n["id"]]}["{label}"]')
    for e in g['edges']:
        lab = '|re-export|' if 'reexport' in e['via'] else (f'|{e["totalUses"]}x|' if e['totalUses'] else '')
        lines.append(f'  {ids[e["to"]]} -->{lab} {ids[e["from"]]}')  # imported file --> file that uses it
    lines += ['  classDef modified fill:#fbf0d9,stroke:#a86a00;', '  classDef added fill:#def3e7,stroke:#1f7a4d;',
              '  classDef deleted fill:#fbe3e3,stroke:#b42323,stroke-dasharray:4 3;', '  classDef renamed fill:#e3ebfc,stroke:#3557c4,stroke-width:3px;',
              '  classDef consumer fill:#fff,stroke:#9aa4b5;', '  classDef dependency fill:#eef0f4,stroke:#d5d9e1,stroke-dasharray:4 3;',
              '  classDef risk stroke:#dc2626,stroke-width:3px;']
    for n in g['nodes']:
        cls = n['status'] if n['role'] == 'changed' else n['role']
        lines.append(f'  class {ids[n["id"]]} {cls}' + (',risk' if n['id'] in risky else '') + ';')
    return '\n'.join(lines) + '\n'


def main():
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument('graph')
    ap.add_argument('--out', help='default: .visual-guides/<YYYY-MM-DD>-impact-map.html (same folder the visualisation skill uses)')
    ap.add_argument('--title')
    ap.add_argument('--guide', help='visualisation guide HTML (walkthrough blocks carry data-node="path"); the usage tree is embedded into it and node clicks show its before/after/why')
    ap.add_argument('--mermaid', help='also write a Mermaid flowchart (.mmd) to this path')
    a = ap.parse_args()

    if not a.out:
        a.out = os.path.join('.visual-guides', f'{datetime.date.today().isoformat()}-impact-map.html')
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.graph, encoding='utf-8') as f:
        g = json.load(f)
    for w in validate(g):
        print('warning:', w, file=sys.stderr)
    guide_html = None
    if a.guide:
        guide_html = open(a.guide, encoding='utf-8').read()
        for w in attach_guides(g, guide_html):
            print('warning:', w, file=sys.stderr)
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'template.html'), encoding='utf-8').read()
    data = json.dumps(g, ensure_ascii=False).replace('</', '<\\/').replace('<!--', '<\\!--')
    title = a.title or f"Change impact map - {g['meta']['repo']}"
    html_mod = tpl.replace('__TITLE__', title.replace('<', '&lt;')).replace('__GRAPH_JSON__', data)
    if guide_html is not None:
        html_out = embed(guide_html, html_mod)
    else:
        html_out = html_mod
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(html_out)
    if a.mermaid:
        with open(a.mermaid, 'w', encoding='utf-8') as f:
            f.write(mermaid(g))
    print(f'{a.out}: {os.path.getsize(a.out) // 1024} KB, {len(g["nodes"])} nodes, {len(g["risks"])} issues', file=sys.stderr)


if __name__ == '__main__':
    main()
