#!/usr/bin/env python3
"""
Generate the KSGA Sociogram HTML from extracted Keough vault data.

Input:  JSON produced by extract_vault_data.py
Output: self-contained HTML (D3 force graph + marked.js for the right panel)

Usage:
    python3 generate_visualization.py <input.json> <output.html>

Design notes:
- Palette indexed by INSTITUTE (per Tom's spec: color by associated unit, not
  individually). The 9 institutes get distinct muted hues; structure groups
  (faculty/programs/locations/etc.) get supporting colors. The Keough School
  umbrella node sits at the centre with a neutral colour.
- Faculty inherit their FIRST-LISTED institute's colour but still draw an
  affiliation edge to EVERY institute they list (Tom's "multiple edging" rule).
- No narration UI. The narration engine is out of scope for the PoC.
- Self-contained: D3 and marked loaded from CDN; data is embedded inline so the
  page works as a static asset served by GitHub Pages with no build step.
"""

import json
import sys
from pathlib import Path


# 9 institute colors + structure-group palette
COLORS = {
    # Institutes (the unit axis — these drive sidebar swatches)
    'institute/keough-school':    '#7A8B8B',  # neutral slate — umbrella node
    'institute/ansari':           '#C9A84C',  # amber (religion)
    'institute/kellogg':          '#5A8EAF',  # blue (international flagship)
    'institute/keough-naughton':  '#3D9E89',  # jade (Irish studies)
    'institute/klau':             '#C45B5B',  # red (civil/human rights)
    'institute/kroc':             '#8B5DAB',  # purple (peace studies)
    'institute/liu':              '#4A8A7A',  # teal (Asia)
    'institute/mckenna':          '#C08B3E',  # orange (human dev + business)
    'institute/nanovic':          '#9A7A5A',  # warm brown (European studies)
    'institute/pulte':            '#C47A9A',  # rose (global development)

    # Structure groups (the non-institute axis)
    'sga_umbrella':     '#5E9B76',  # green — About / school-level
    'institutes_other': '#8A9098',  # grey — Institutes MOC
    'programs':         '#B87D3E',  # warm bronze — Academic programs
    'faculty':          '#A85D3A',  # rust — Faculty/Staff without an institute
    'locations':        '#5A72A8',  # indigo — Locations
    'news':             '#6B7B7B',  # slate — News
    'prs':              '#7A6B8A',  # mauve — PRS
    'architecture':     '#5B7FA5',  # steel blue — Architecture pathways
    'meta':             '#A8923A',  # ochre — Meta
    'agents':           '#8B6DAE',  # lavender — Agents
    'root':             '#9A9A9A',  # neutral grey — uncategorized
}


LABELS = {
    'institute/keough-school':    'Keough School (umbrella)',
    'institute/ansari':           'Ansari',
    'institute/kellogg':          'Kellogg',
    'institute/keough-naughton':  'Keough-Naughton',
    'institute/klau':             'Klau',
    'institute/kroc':             'Kroc',
    'institute/liu':              'Liu',
    'institute/mckenna':          'McKenna',
    'institute/nanovic':          'Nanovic',
    'institute/pulte':            'Pulte',
    'sga_umbrella':     'About / SGA',
    'institutes_other': 'Institutes (MOC)',
    'programs':         'Academic Programs',
    'faculty':          'Faculty (unaffiliated)',
    'locations':        'Locations',
    'news':             'News',
    'prs':              'PRS',
    'architecture':     'Architecture',
    'meta':             'Meta',
    'agents':           'Agents',
    'root':             'Other',
}


# Sidebar grouping order: institutes first, then structure groups
INSTITUTE_ORDER = [
    'institute/keough-school',
    'institute/ansari',
    'institute/kellogg',
    'institute/keough-naughton',
    'institute/klau',
    'institute/kroc',
    'institute/liu',
    'institute/mckenna',
    'institute/nanovic',
    'institute/pulte',
]

STRUCTURE_ORDER = [
    'sga_umbrella',
    'programs',
    'faculty',
    'locations',
    'news',
    'prs',
    'architecture',
    'meta',
    'agents',
    'institutes_other',
    'root',
]


def build_graph_data(data):
    """Turn extractor output into D3 nodes + links."""
    files = data['files']
    edges = data['edges']

    filepath_to_idx = {f['filepath']: i for i, f in enumerate(files)}

    nodes = []
    for f in files:
        unit = f['unit']
        nodes.append({
            'id': f['filepath'],
            'title': f['title'],
            'filename': f['filename'],
            'unit': unit,
            'color': COLORS.get(unit, COLORS['root']),
            'type': f.get('type') or '',
            'date': str(f.get('date') or ''),
            'epistemic_status': f.get('epistemic_status') or '',
            'size': max(4, min(14, 4 + (f.get('size_bytes', 0) or 0) ** 0.5 / 30)),
            'content': f.get('content', ''),
        })

    links = []
    for e in edges:
        if e['source'] in filepath_to_idx and e['target'] in filepath_to_idx:
            links.append({
                'source': e['source'],
                'target': e['target'],
                'type': e['type'],
            })

    return nodes, links


def generate_html(data, nodes, links):
    """Compose the self-contained HTML page.

    Per project convention: regular strings (not f-strings) for the big
    template, data injected by concatenation with json.dumps output."""
    instance_name = data.get('metadata', {}).get('instance', {}).get('name', 'KSGA Sociogram')

    nodes_json = json.dumps(nodes, ensure_ascii=False)
    links_json = json.dumps(links, ensure_ascii=False)
    colors_json = json.dumps(COLORS, ensure_ascii=False)
    labels_json = json.dumps(LABELS, ensure_ascii=False)
    institute_order_json = json.dumps(INSTITUTE_ORDER)
    structure_order_json = json.dumps(STRUCTURE_ORDER)

    html = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>KSGA Sociogram</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://d3js.org/d3.v7.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/marked/12.0.2/marked.min.js"></script>
<style>
  :root {
    --bg: #0a0a0f;
    --panel: #15161c;
    --panel-2: #1c1e26;
    --fg: #d8d8e0;
    --fg-dim: #9a9aa6;
    --fg-mute: #6a6a76;
    --border: #2a2c36;
    --accent: #c9a84c;
    --link: #88b2d8;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; padding: 0; }
  body {
    background: var(--bg); color: var(--fg);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
    overflow: hidden;
  }
  #app {
    display: grid;
    grid-template-columns: 260px 1fr 440px;
    grid-template-rows: 44px 1fr;
    height: 100vh;
  }
  #topbar {
    grid-column: 1 / -1;
    display: flex; align-items: center; gap: 16px;
    padding: 0 16px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
  }
  #topbar h1 {
    margin: 0; font-size: 14px; font-weight: 600;
    color: var(--accent); letter-spacing: 0.3px;
  }
  #topbar .sub { color: var(--fg-dim); font-size: 11px; }
  #topbar .grow { flex: 1; }
  #search {
    background: var(--panel-2);
    color: var(--fg);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 4px 8px;
    font-size: 12px;
    min-width: 220px;
    outline: none;
  }
  #search:focus { border-color: var(--accent); }
  button.tool {
    background: var(--panel-2);
    color: var(--fg);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 4px 10px;
    font-size: 12px;
    cursor: pointer;
  }
  button.tool:hover { border-color: var(--accent); color: var(--accent); }

  #sidebar {
    background: var(--panel);
    border-right: 1px solid var(--border);
    overflow-y: auto;
    padding: 12px 12px;
  }
  #sidebar h3 {
    margin: 14px 0 6px;
    font-size: 11px;
    font-weight: 600;
    color: var(--fg-dim);
    text-transform: uppercase;
    letter-spacing: 0.6px;
  }
  #sidebar h3:first-child { margin-top: 0; }
  .row {
    display: flex; align-items: center; gap: 6px;
    padding: 2px 0;
    cursor: pointer;
    font-size: 12px;
    color: var(--fg);
  }
  .row:hover { color: var(--accent); }
  .row input[type=checkbox] { cursor: pointer; }
  .swatch {
    display: inline-block;
    width: 10px; height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .row .count {
    margin-left: auto;
    color: var(--fg-mute);
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }
  #graph-wrap { position: relative; background: var(--bg); overflow: hidden; }
  svg { width: 100%; height: 100%; display: block; }
  .link { stroke-opacity: 0.35; }
  .link.affiliation { stroke-dasharray: 3 2; }
  .node circle { stroke: #0a0a0f; stroke-width: 1; cursor: pointer; }
  .node text {
    pointer-events: none;
    fill: var(--fg-dim);
    font-size: 9px;
    text-anchor: middle;
  }
  .node.dim circle { opacity: 0.08; }
  .node.dim text { opacity: 0; }
  .node.selected circle { stroke: var(--accent); stroke-width: 2; }

  #right-panel {
    background: var(--panel);
    border-left: 1px solid var(--border);
    overflow-y: auto;
    padding: 16px;
  }
  #right-panel .empty {
    color: var(--fg-mute);
    font-style: italic;
    margin-top: 16px;
  }
  #right-panel h2 {
    margin: 0 0 6px;
    font-size: 15px;
    color: var(--accent);
  }
  #right-panel .meta {
    color: var(--fg-dim);
    font-size: 11px;
    margin-bottom: 12px;
  }
  #right-panel .meta .pill {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 2px;
    background: var(--panel-2);
    margin-right: 4px;
  }
  #right-panel .body {
    color: var(--fg);
    font-size: 12.5px;
    line-height: 1.5;
    word-wrap: break-word;
  }
  #right-panel .body h1 { font-size: 16px; margin: 12px 0 6px; }
  #right-panel .body h2 { font-size: 14px; margin: 10px 0 6px; color: var(--fg); }
  #right-panel .body h3 { font-size: 13px; margin: 8px 0 4px; }
  #right-panel .body a { color: var(--link); }
  #right-panel .body code { background: var(--panel-2); padding: 1px 4px; border-radius: 2px; }
  #right-panel .body pre { background: var(--panel-2); padding: 8px; overflow-x: auto; }
  #right-panel .body blockquote {
    border-left: 2px solid var(--border);
    padding-left: 8px;
    color: var(--fg-dim);
    margin: 8px 0;
  }
  #right-panel .wikilink { color: var(--link); cursor: pointer; }
  #right-panel .wikilink.dead { color: var(--fg-mute); text-decoration: line-through; }

  #legend {
    position: absolute;
    right: 12px; top: 12px;
    background: rgba(21, 22, 28, 0.85);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 8px 10px;
    font-size: 11px;
    color: var(--fg-dim);
    backdrop-filter: blur(4px);
  }
  #legend div { display: flex; align-items: center; gap: 6px; padding: 1px 0; }
  #legend .line { width: 18px; height: 0; border-top: 1px solid var(--fg-dim); }
  #legend .line.aff { border-top: 1px dashed var(--fg-dim); }

  #status {
    position: absolute;
    left: 12px; bottom: 12px;
    color: var(--fg-mute);
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }
</style>
</head>
<body>
<div id="app">
  <div id="topbar">
    <h1>KSGA Sociogram</h1>
    <span class="sub" id="instance-name">""" + instance_name + """</span>
    <span class="grow"></span>
    <input id="search" type="text" placeholder="Search file or title…">
    <button class="tool" onclick="resetView()">Reset</button>
    <button class="tool" onclick="toggleLabels()">Names</button>
    <button class="tool" onclick="fitAll()">Fit All</button>
  </div>

  <div id="sidebar">
    <div style="margin-bottom: 10px;">
      <label class="row"><input type="checkbox" id="chk-all" checked onchange="toggleAll(this.checked)"> <span>All</span></label>
    </div>
    <h3>Units</h3>
    <div id="unit-filters"></div>
    <h3>Structure groups</h3>
    <div id="structure-filters"></div>
  </div>

  <div id="graph-wrap">
    <svg id="svg"></svg>
    <div id="legend">
      <div><span class="line"></span> wikilink</div>
      <div><span class="line aff"></span> affiliation</div>
    </div>
    <div id="status"></div>
  </div>

  <div id="right-panel">
    <div class="empty">Click a node to view its file. Wikilinks are clickable.</div>
  </div>
</div>

<script>
const NODES = """ + nodes_json + """;
const LINKS = """ + links_json + """;
const COLORS = """ + colors_json + """;
const LABELS = """ + labels_json + """;
const INSTITUTE_ORDER = """ + institute_order_json + """;
const STRUCTURE_ORDER = """ + structure_order_json + """;

// --- Sidebar ----------------------------------------------------------------

const unitCounts = {};
NODES.forEach(n => { unitCounts[n.unit] = (unitCounts[n.unit] || 0) + 1; });

const activeUnits = new Set(Object.keys(unitCounts));  // start with all on

function renderSidebar() {
  const u = d3.select('#unit-filters');
  const s = d3.select('#structure-filters');
  u.selectAll('*').remove();
  s.selectAll('*').remove();

  function addRow(parent, unit, withSwatch) {
    if (!(unit in unitCounts)) return;  // skip units that have no nodes
    const row = parent.append('label').attr('class', 'row');
    row.append('input')
      .attr('type', 'checkbox')
      .property('checked', activeUnits.has(unit))
      .on('change', function() {
        if (this.checked) activeUnits.add(unit); else activeUnits.delete(unit);
        applyFilters();
      });
    if (withSwatch) {
      row.append('span')
        .attr('class', 'swatch')
        .style('background', COLORS[unit] || '#888');
    }
    row.append('span').text(LABELS[unit] || unit);
    row.append('span').attr('class', 'count').text(unitCounts[unit]);
  }

  INSTITUTE_ORDER.forEach(unit => addRow(u, unit, true));
  STRUCTURE_ORDER.forEach(unit => addRow(s, unit, true));
}

function toggleAll(checked) {
  if (checked) {
    Object.keys(unitCounts).forEach(u => activeUnits.add(u));
  } else {
    activeUnits.clear();
  }
  document.querySelectorAll('#unit-filters input, #structure-filters input')
    .forEach(cb => { cb.checked = checked; });
  applyFilters();
}

// --- Force graph ------------------------------------------------------------

const svg = d3.select('#svg');
const wrap = document.getElementById('graph-wrap');
let width = wrap.clientWidth;
let height = wrap.clientHeight;
svg.attr('viewBox', [-width/2, -height/2, width, height]);

const g = svg.append('g');
const linkLayer = g.append('g').attr('class', 'links');
const nodeLayer = g.append('g').attr('class', 'nodes');

const zoom = d3.zoom()
  .scaleExtent([0.1, 8])
  .on('zoom', (event) => g.attr('transform', event.transform));
svg.call(zoom);

const sim = d3.forceSimulation(NODES)
  .force('link', d3.forceLink(LINKS).id(d => d.id).distance(40).strength(0.4))
  .force('charge', d3.forceManyBody().strength(-60))
  .force('center', d3.forceCenter(0, 0))
  .force('collide', d3.forceCollide().radius(d => d.size + 2));

const linkSel = linkLayer.selectAll('line').data(LINKS).enter().append('line')
  .attr('class', d => 'link ' + d.type)
  .attr('stroke', d => d.type === 'affiliation' ? '#7a7a86' : '#4a4a56')
  .attr('stroke-width', d => d.type === 'affiliation' ? 1.2 : 0.8);

const nodeSel = nodeLayer.selectAll('g').data(NODES).enter().append('g')
  .attr('class', 'node')
  .call(d3.drag()
    .on('start', (event, d) => { if (!event.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
    .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
    .on('end', (event, d) => { if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }))
  .on('click', (event, d) => { selectNode(d); event.stopPropagation(); });

nodeSel.append('circle')
  .attr('r', d => d.size)
  .attr('fill', d => d.color);

nodeSel.append('title').text(d => d.title + '  ·  ' + (LABELS[d.unit] || d.unit));

const labelSel = nodeSel.append('text')
  .attr('dy', d => -d.size - 2)
  .text(d => d.title);

let showLabels = false;
labelSel.style('display', 'none');

sim.on('tick', () => {
  linkSel
    .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
    .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
  nodeSel.attr('transform', d => 'translate(' + d.x + ',' + d.y + ')');
});

// --- Filters / labels / view -----------------------------------------------

function applyFilters() {
  const search = document.getElementById('search').value.toLowerCase().trim();
  let visible = 0, total = NODES.length;
  nodeSel.classed('dim', d => {
    const unitOk = activeUnits.has(d.unit);
    const searchOk = !search ||
      (d.title && d.title.toLowerCase().includes(search)) ||
      (d.filename && d.filename.toLowerCase().includes(search));
    const ok = unitOk && searchOk;
    if (ok) visible++;
    return !ok;
  });
  linkSel.style('opacity', d => {
    const s = typeof d.source === 'object' ? d.source : NODES.find(n => n.id === d.source);
    const t = typeof d.target === 'object' ? d.target : NODES.find(n => n.id === d.target);
    if (!s || !t) return 0.1;
    const sActive = activeUnits.has(s.unit);
    const tActive = activeUnits.has(t.unit);
    return (sActive && tActive) ? 0.35 : 0.05;
  });
  document.getElementById('status').textContent =
    visible + ' / ' + total + ' nodes  ·  ' + LINKS.length + ' edges';
}

function toggleLabels() {
  showLabels = !showLabels;
  labelSel.style('display', showLabels ? null : 'none');
}

function resetView() {
  document.getElementById('search').value = '';
  toggleAll(true);
  document.getElementById('chk-all').checked = true;
}

function fitAll() {
  const xs = NODES.map(d => d.x || 0);
  const ys = NODES.map(d => d.y || 0);
  if (xs.length === 0) return;
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const dx = maxX - minX, dy = maxY - minY;
  const scale = Math.min(width / (dx + 80), height / (dy + 80), 1.5);
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
  svg.transition().duration(500).call(
    zoom.transform,
    d3.zoomIdentity.translate(0, 0).scale(scale).translate(-cx, -cy)
  );
}

document.getElementById('search').addEventListener('input', applyFilters);

window.addEventListener('resize', () => {
  width = wrap.clientWidth;
  height = wrap.clientHeight;
  svg.attr('viewBox', [-width/2, -height/2, width, height]);
});

// --- Right panel ------------------------------------------------------------

const stemToNode = {};
NODES.forEach(n => {
  const stem = n.filename.replace(/\\.md$/, '');
  if (!(stem in stemToNode)) stemToNode[stem] = n;
});

function renderWikilinks(html) {
  return html.replace(/\\[\\[([^\\]|#]+?)(?:#[^\\]|]+?)?(?:\\|([^\\]]+?))?\\]\\]/g,
    (m, target, alias) => {
      const text = alias || target;
      const node = stemToNode[target.trim()];
      if (node) {
        return '<span class="wikilink" data-target="' + node.id.replace(/"/g, '&quot;') + '">' + text + '</span>';
      }
      return '<span class="wikilink dead">' + text + '</span>';
    });
}

function selectNode(d) {
  nodeSel.classed('selected', n => n === d);
  const panel = d3.select('#right-panel');
  panel.selectAll('*').remove();
  panel.append('h2').text(d.title);
  const meta = panel.append('div').attr('class', 'meta');
  meta.append('span').attr('class', 'pill')
    .style('color', d.color).text(LABELS[d.unit] || d.unit);
  if (d.type) meta.append('span').attr('class', 'pill').text(d.type);
  if (d.epistemic_status) meta.append('span').attr('class', 'pill').text(d.epistemic_status);
  if (d.date) meta.append('span').attr('class', 'pill').text(d.date);
  meta.append('div').style('margin-top', '4px')
    .style('font-family', 'ui-monospace, Menlo, monospace')
    .style('color', 'var(--fg-mute)')
    .text(d.id);

  const body = panel.append('div').attr('class', 'body');
  // marked converts the markdown body; we then process [[wikilinks]] in the
  // rendered HTML. Frontmatter delimiters are stripped by a simple regex.
  let md = d.content || '';
  md = md.replace(/^---\\s*[\\s\\S]*?---\\s*/m, '');
  let rendered = marked.parse(md);
  rendered = renderWikilinks(rendered);
  body.html(rendered);
  body.selectAll('.wikilink').on('click', function() {
    const target = this.getAttribute('data-target');
    if (!target) return;
    const node = NODES.find(n => n.id === target);
    if (node) selectNode(node);
  });
}

// --- Init -------------------------------------------------------------------

renderSidebar();
applyFilters();
setTimeout(fitAll, 800);  // let force simulation settle a bit before fitting
</script>
</body>
</html>
"""
    return html


def main():
    if len(sys.argv) < 3:
        print('Usage: generate_visualization.py <input.json> <output.html>', file=sys.stderr)
        sys.exit(2)
    in_path = sys.argv[1]
    out_path = sys.argv[2]
    data = json.loads(Path(in_path).read_text(encoding='utf-8'))
    nodes, links = build_graph_data(data)
    html = generate_html(data, nodes, links)
    Path(out_path).write_text(html, encoding='utf-8')
    print(f'Wrote {out_path} ({len(html):,} bytes, {len(nodes)} nodes, {len(links)} links)',
          file=sys.stderr)


if __name__ == '__main__':
    main()
