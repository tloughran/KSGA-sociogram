# KSGA Sociogram

Force-directed visualization of the Keough School of Global Affairs wiki vault.
Companion to the C2A2 sociogram pattern (tloughran/C2A2-wiki), built as a
proof-of-concept showing that the same accelerator/detector toolchain ports to
any well-structured Obsidian community vault.

**Live:** `https://tloughran.github.io/KSGA-sociogram/` (once Pages is enabled
on `main`).

## What this shows

- **Nodes:** every `.md` file in the Keough vault (~470 at PoC).
- **Color:** by associated institute or structure group. The 9 institutes
  (Ansari, Kellogg, Keough-Naughton, Klau, Kroc, Liu, McKenna, Nanovic, Pulte)
  each have their own hue. Faculty with `institute_affiliations[]` in their
  frontmatter inherit the colour of their **first-listed** affiliation.
- **Edges:** wikilinks (solid) plus affiliation edges (dashed) — a faculty
  member with multiple affiliations is drawn to *each* listed institute, so
  multi-affiliation is visible as a connection pattern rather than a colour
  blend.
- **Right panel:** rendered markdown for the clicked node, with `[[wikilinks]]`
  navigable in-place. Shows the file's `relationship_bucket` as a pill.
- **Gold ring:** people in the `central_plus_institute/*` bucket — appearing
  in BOTH the Keough central directory AND an institute people page — get a
  thin bright outer stroke. The highest-confidence provenance class is
  highlighted; the others render unchanged. Opacity is deliberately reserved
  for the canonical `epistemic_status` channel (Pathway 14) when it lands.

## Build

Requires Python 3 and PyYAML.

```bash
pip install pyyaml --break-system-packages   # one-time
python3 scripts/extract_vault_data.py /path/to/keough/vault > /tmp/keough.json
python3 scripts/generate_visualization.py /tmp/keough.json index.html
```

Or use the convenience script:

```bash
./scripts/build.sh /path/to/keough/vault
```

Output is a single self-contained `index.html` (~1.2 MB, embeds all data
inline, loads d3 and marked from CDN).

## Source vault

The Keough vault lives in a private repo (tloughran/keough-wiki). This repo
holds only the rendered sociogram and the scripts that build it — no vault
contents.

## Design notes

- **PoC scope:** force graph + filters + right-panel markdown + search.
  Narration engine, Score modes, and the temporal slider from the C2A2
  Sociogram are deliberately out of scope for first cut.
- **Palette:** 9 institute colours chosen for dark-theme legibility, mirroring
  the muted-but-distinct C2A2 thinker palette.
- **Edges:** the affiliation edges show data the wikilinks don't — many faculty
  pages don't yet link to their institute pages textually but do encode the
  relationship in frontmatter. The dashed-line treatment makes them visually
  distinguishable from the wikilink edges.
- **Data gaps as feature:** institutes whose faculty haven't been ingested yet
  (Keough-Naughton, Klau, McKenna) show only their hub node. The map reveals
  ingestion progress at a glance.

## License

Code under MIT. Embedded vault content reflects public-directory information
from keough.nd.edu and the institute-specific subdomains; per the
`keough-wiki-faculty-ingest` agent's `consent_level: public-directory` rule.
