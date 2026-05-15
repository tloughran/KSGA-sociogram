#!/usr/bin/env python3
"""
Extract structured data from the Keough School Obsidian vault for the
KSGA-sociogram visualization.

Reads `_meta/instance.yaml` for the unit (institute) registry and structure-group
palette, then scans all *.md files. Each file is tagged with a `unit` key that
drives node color in the rendered sociogram:

  - Community page (Institutes and Centers/<Name>.md) → its own institute id
  - Faculty page with institute_affiliations[] → first-listed institute id
  - Otherwise → top-level folder name (mapped via STRUCTURE_GROUP_FOLDERS)

Edges are built from wikilinks only (Keough vault doesn't yet carry the
PRS/ASSUMPTION/FINDING/etc. reference-ID convention the C2A2 wiki uses).

Usage: python3 extract_vault_data.py <vault_path> > vault_data.json
"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml  # PyYAML — present on every Python install we care about


def _parse_simple_yaml(text):
    """Wrapper kept for compatibility with the original API."""
    try:
        return yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        print(f'YAML parse error: {e}', file=sys.stderr)
        return {}


def _parse_simple_yaml_legacy(text):
    """Parse a constrained YAML subset. Returns a dict.

    Supports:
      key: scalar
      key:
        nested: scalar
      key:
        - item
        - item
      key:
        - field1: v
          field2: v
    """
    root = {}
    stack = [(0, root)]      # (indent, container)
    list_item = None         # current dict being built inside a list
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        stripped = raw.split('#', 1)[0].rstrip()
        if not stripped.strip():
            continue
        indent = len(raw) - len(raw.lstrip(' '))
        line = stripped.strip()

        # Pop the stack until our indent fits
        while stack and indent < stack[-1][0]:
            stack.pop()
            list_item = None

        if line.startswith('- '):
            # List item under the current container key
            parent_indent, parent = stack[-1]
            # parent must be a list (we represent unsettled lists by binding a
            # key whose value we then convert to a list on first '- ').
            content = line[2:].strip()
            # Re-resolve: find the containing key whose value is a list
            list_holder, list_key = _find_pending_list(stack)
            if list_holder is None:
                # Standalone list (rare in instance.yaml) — skip gracefully
                continue
            if ':' in content:
                # Inline mapping for the list item
                item = {}
                k, v = content.split(':', 1)
                item[k.strip()] = _coerce(v.strip())
                list_holder[list_key].append(item)
                list_item = item
                stack.append((indent + 2, item))
            else:
                list_holder[list_key].append(_coerce(content))
                list_item = None
        elif ':' in line:
            k, v = line.split(':', 1)
            k = k.strip()
            v = v.strip()
            parent_indent, parent = stack[-1]
            if v == '':
                # Could be a nested mapping OR a list. We don't know yet.
                # Default to dict; a subsequent '- ' will convert.
                new = {}
                parent[k] = new
                stack.append((indent + 2, new))
                # Mark this key as a possible list holder
                parent.setdefault('__pending_list__', set()).add(k)
            else:
                parent[k] = _coerce(v)
    _strip_pending(root)
    return root


def _find_pending_list(stack):
    """Walk the stack from top to bottom, find the most recent dict that has a
    __pending_list__ entry; convert that key's value to a list (if not already
    a list) and return (parent_dict, key)."""
    for indent, container in reversed(stack):
        if isinstance(container, dict) and '__pending_list__' in container:
            pending = container['__pending_list__']
            if pending:
                # Pop any one pending key (we don't track order; instance.yaml
                # has unambiguous structure)
                # Actually we need the most recently introduced — convert the
                # value that is currently an empty dict
                for k in list(pending):
                    if isinstance(container.get(k), dict) and not container[k]:
                        container[k] = []
                        pending.discard(k)
                        return container, k
    return None, None


def _coerce(v):
    """Coerce a YAML scalar string to bool/int/None/str."""
    if v == 'true':
        return True
    if v == 'false':
        return False
    if v in ('null', '~', ''):
        return None
    # Strip quotes
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    try:
        if '.' in v:
            return float(v)
        return int(v)
    except ValueError:
        return v


def _strip_pending(obj):
    if isinstance(obj, dict):
        obj.pop('__pending_list__', None)
        for v in obj.values():
            _strip_pending(v)
    elif isinstance(obj, list):
        for v in obj:
            _strip_pending(v)


# --- Frontmatter parsing -----------------------------------------------------

FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)


def parse_frontmatter(content):
    """Return (frontmatter_dict, body_text). Empty dict if no frontmatter."""
    m = FRONTMATTER_RE.match(content)
    if not m:
        return {}, content
    fm_text = m.group(1)
    body = content[m.end():]
    fm = _parse_simple_yaml(fm_text)
    return fm, body


# --- Top-level folder → structure-group mapping ------------------------------
# Folders not in this map default to 'root'. Underscore-prefixed folders
# (_architecture, _meta) are normalized to their non-underscore equivalents.

STRUCTURE_GROUP_FOLDERS = {
    'About':                  'sga_umbrella',
    'Academics':              'programs',
    'Faculty':                'faculty',
    'Staff':                  'faculty',
    'Institutes and Centers': 'institutes_other',  # only fires if frontmatter doesn't already assign an institute id
    'Locations':              'locations',
    'News':                   'news',
    'PRS':                    'prs',
    '_architecture':          'architecture',
    '_meta':                  'meta',
    'agents':                 'agents',
}


# --- Wikilink extraction -----------------------------------------------------

WIKILINK_RE = re.compile(r'\[\[([^\]|#]+?)(?:#[^\]|]+?)?(?:\|[^\]]+?)?\]\]')


def extract_wikilinks(text):
    return list({m.group(1).strip() for m in WIKILINK_RE.finditer(text)})


def extract_title(body, fallback):
    for line in body.split('\n'):
        line = line.strip()
        if line.startswith('# '):
            return line[2:].strip()
    return fallback


# --- Per-file processing -----------------------------------------------------

def file_unit(rel_path, fm, institute_paths):
    """Determine the unit key for color/grouping.

    Priority:
      1. Community page (path matches an institute's path field) → institute id
      2. Faculty with institute_affiliations[] → first-listed institute id
      3. Top-level folder mapped via STRUCTURE_GROUP_FOLDERS
      4. 'root'
    """
    # Normalize for path comparison
    rp = rel_path.replace(os.sep, '/')

    # 1. Community page
    for inst_id, inst_path in institute_paths.items():
        if rp == inst_path:
            return 'institute/' + inst_id

    # 2. Faculty with affiliations
    affs = fm.get('institute_affiliations') if isinstance(fm, dict) else None
    if affs and isinstance(affs, list) and affs:
        first = affs[0]
        if isinstance(first, dict) and first.get('institute'):
            return 'institute/' + first['institute']

    # 3. Top-level folder
    parts = rp.split('/', 1)
    top = parts[0]
    if top in STRUCTURE_GROUP_FOLDERS:
        return STRUCTURE_GROUP_FOLDERS[top]

    return 'root'


def all_affiliations(fm):
    """Return all institute ids in a file's affiliations (for multi-edging)."""
    affs = fm.get('institute_affiliations') if isinstance(fm, dict) else None
    if not affs or not isinstance(affs, list):
        return []
    out = []
    for a in affs:
        if isinstance(a, dict) and a.get('institute'):
            out.append(a['institute'])
    return out


def scan_vault(vault_path, institute_paths):
    """Walk the vault and return file records."""
    vault = Path(vault_path)
    files = []
    skip_dirs = {'.git', '.obsidian', 'node_modules'}
    for md in sorted(vault.rglob('*.md')):
        if any(part in skip_dirs for part in md.parts):
            continue
        rel = md.relative_to(vault).as_posix()
        try:
            content = md.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue
        fm, body = parse_frontmatter(content)
        unit = file_unit(rel, fm, institute_paths)
        mtime = datetime.fromtimestamp(os.path.getmtime(md)).strftime('%Y-%m-%d')
        files.append({
            'filepath': rel,
            'filename': md.name,
            'unit': unit,
            'title': fm.get('title') if isinstance(fm, dict) and fm.get('title') else extract_title(body, md.stem),
            'type': fm.get('type') if isinstance(fm, dict) else None,
            'date': fm.get('last_updated') if isinstance(fm, dict) and fm.get('last_updated') else mtime,
            'epistemic_status': fm.get('epistemic_status') if isinstance(fm, dict) else None,
            'wikilinks': extract_wikilinks(body),
            'all_affiliations': all_affiliations(fm),
            'size_bytes': len(content.encode('utf-8')),
            'content': content[:8000],  # cap preview at 8KB for the right panel
        })
    return files


def build_edges(files, institute_paths):
    """Wikilink edges + affiliation edges from each faculty to all their
    institutes (so multi-affiliation shows up visually)."""
    # Build a name → filepath lookup. We match by filename stem (no extension)
    # which is the Obsidian default for unambiguous wikilinks.
    stem_to_path = {}
    for f in files:
        stem = Path(f['filename']).stem
        if stem not in stem_to_path:
            stem_to_path[stem] = f['filepath']
        # Some Obsidian wikilinks use the full relative path
        stem_to_path[f['filepath']] = f['filepath']

    edges = []
    seen = set()

    def add_edge(s, t, kind):
        key = (s, t, kind)
        if key in seen or s == t:
            return
        seen.add(key)
        edges.append({'source': s, 'target': t, 'type': kind})

    for f in files:
        # Wikilink edges
        for link in f['wikilinks']:
            target = stem_to_path.get(link)
            if target:
                add_edge(f['filepath'], target, 'wikilink')

        # Affiliation edges — for multi-institute people, draw an explicit
        # edge to each institute they list (Tom's "multiple edging" rule)
        for inst_id in f['all_affiliations']:
            inst_path = institute_paths.get(inst_id)
            if inst_path:
                add_edge(f['filepath'], inst_path, 'affiliation')

    return edges


# --- Main --------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print('Usage: extract_vault_data.py <vault_path>', file=sys.stderr)
        sys.exit(2)
    vault_path = sys.argv[1]
    if not os.path.isdir(vault_path):
        print(f'Error: {vault_path} is not a directory', file=sys.stderr)
        sys.exit(1)

    # Load instance.yaml
    instance_file = Path(vault_path) / '_meta' / 'instance.yaml'
    if not instance_file.exists():
        print(f'Error: {instance_file} not found', file=sys.stderr)
        sys.exit(1)
    instance = _parse_simple_yaml(instance_file.read_text(encoding='utf-8'))

    communities = instance.get('communities') or []
    institute_paths = {}
    institute_labels = {}
    for c in communities:
        if isinstance(c, dict) and c.get('id') and c.get('path'):
            cid = c['id']
            institute_paths[cid] = c['path'].replace(os.sep, '/')
            institute_labels[cid] = c.get('label', cid)

    files = scan_vault(vault_path, institute_paths)
    edges = build_edges(files, institute_paths)

    # Roll up units present in the data (drives the sidebar)
    units_present = sorted({f['unit'] for f in files})

    output = {
        'metadata': {
            'extraction_date': datetime.now().isoformat(),
            'vault_path': vault_path,
            'total_files': len(files),
            'instance': {
                'id': instance.get('instance', {}).get('id'),
                'name': instance.get('instance', {}).get('name'),
            },
        },
        'institutes': [
            {'id': cid, 'label': institute_labels[cid], 'path': institute_paths[cid]}
            for cid in institute_paths
        ],
        'units_present': units_present,
        'files': files,
        'edges': edges,
    }
    json.dump(output, sys.stdout, indent=2, ensure_ascii=False, default=str)


if __name__ == '__main__':
    main()
