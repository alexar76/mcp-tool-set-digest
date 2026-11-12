#!/usr/bin/env bash
# Runs every check of this repository. Needs python3 (3.9+), node (20+) and go (1.21+).
#
#   scripts/check.sh
#
# With HISTOR and WARDEN checked out beside this folder (the monorepo layout), their own code is
# run over the vectors as well:
#   HISTOR_PYTHONPATH=<histor>:<awr/reference/python>  WARDEN_DIST=<warden>/dist  scripts/check.sh
set -euo pipefail
cd "$(dirname "$0")/.."

python3 vectors/generate.py --check
python3 implementations/python/tool_set_digest.py --vectors vectors/vectors.json
node implementations/javascript/tool-set-digest.mjs --vectors vectors/vectors.json
(cd implementations/go && go vet ./... && go run . --vectors ../../vectors/vectors.json)

# The three command lines give the same answer for the same input.
sample='[{"name":"b","inputSchema":{"maximum":1E2}},{"name":"a","description":"x","title":"A","annotations":{"readOnlyHint":true}}]'
py=$(printf '%s' "$sample" | python3 implementations/python/tool_set_digest.py)
js=$(printf '%s' "$sample" | node implementations/javascript/tool-set-digest.mjs)
go=$(cd implementations/go && printf '%s' "$sample" | go run .)
norm() { python3 -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1]), sort_keys=True))' "$1"; }
[ "$(norm "$py")" = "$(norm "$js")" ] && [ "$(norm "$js")" = "$(norm "$go")" ] || { echo "the command lines disagree: $py | $js | $go"; exit 1; }
echo "command lines agree: $(norm "$py")"

# The example printed in README.md is what the implementation prints.
readme=$(printf '%s' '[{"name": "read_file", "title": "Read file", "description": "Read a file from disk.", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}, "annotations": {"readOnlyHint": true}}]' | python3 implementations/python/tool_set_digest.py)
grep -qF -- "$readme" README.md || { echo "README.md shows another output than: $readme"; exit 1; }

if [ -n "${HISTOR_PYTHONPATH:-}" ]; then
  PYTHONPATH="$HISTOR_PYTHONPATH" "${HISTOR_PYTHON:-python3}" scripts/cross_check_histor.py
fi
if [ -n "${WARDEN_DIST:-}" ]; then
  node scripts/cross_check_warden.mjs "$WARDEN_DIST"
fi
echo "all checks passed"
