#!/usr/bin/env bash
# Build the KSGA Sociogram from a Keough vault directory.
#
# Usage:  ./scripts/build.sh <vault_path>
# Output: ./index.html in the repo root.

set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <vault_path>" >&2
  exit 2
fi

VAULT="$1"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

python3 "$HERE/scripts/extract_vault_data.py" "$VAULT" > "$SCRATCH/data.json"
python3 "$HERE/scripts/generate_visualization.py" "$SCRATCH/data.json" "$HERE/index.html"

echo "Built $HERE/index.html"
