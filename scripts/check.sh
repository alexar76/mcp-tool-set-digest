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

check_pagination() {
  local complete partial output
  for complete in "{\"tools\":$sample}" "{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"tools\":$sample}}"; do
    output=$(printf '%s' "$complete" | "$@")
    [ "$(norm "$output")" = "$(norm "$py")" ] || { echo "$* hashes the wrapped input differently: $output"; return 1; }
  done
  for partial in '{"tools":[],"nextCursor":"page2"}' '{"jsonrpc":"2.0","id":1,"result":{"tools":[],"nextCursor":""}}'; do
    if output=$(printf '%s' "$partial" | "$@"); then
      echo "$* accepted a partial page: $output"
      return 1
    fi
    python3 - "$output" <<'PY'
import json
import sys

out = json.loads(sys.argv[1])
if out.get("error") != "TSD-PAGE" or {"contract", "extras"}.intersection(out):
    sys.exit(f"expected TSD-PAGE without digests: {out}")
PY
  done
}
check_pagination python3 implementations/python/tool_set_digest.py
check_pagination node implementations/javascript/tool-set-digest.mjs
(cd implementations/go && check_pagination go run .)
echo "command lines reject partial pages"

# Section 3: an object with both tools and result is no input form (TSD-TOOL, no digests); two tools
# members are a repeated name, and the last one counts.
check_wrappers() {
  local ambiguous repeated output
  for ambiguous in "{\"tools\":$sample,\"result\":{\"tools\":$sample}}" '{"tools":[],"result":null}' \
      "{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"tools\":$sample,\"result\":{}}}"; do
    if output=$(printf '%s' "$ambiguous" | "$@"); then
      echo "$* accepted tools next to result: $output"
      return 1
    fi
    python3 - "$output" <<'PY'
import json
import sys

out = json.loads(sys.argv[1])
if out.get("error") != "TSD-TOOL" or {"contract", "extras"}.intersection(out):
    sys.exit(f"expected TSD-TOOL without digests: {out}")
PY
  done
  for repeated in "{\"tools\":[{\"name\":\"x\"}],\"tools\":$sample}" \
      "{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"tools\":[],\"tools\":$sample}}"; do
    output=$(printf '%s' "$repeated" | "$@")
    [ "$(norm "$output")" = "$(norm "$py")" ] || { echo "$* did not read the last tools member: $output"; return 1; }
  done
}
check_wrappers python3 implementations/python/tool_set_digest.py
check_wrappers node implementations/javascript/tool-set-digest.mjs
(cd implementations/go && check_wrappers go run .)
echo "command lines refuse tools next to result and read the last of two tools members"

# Section 12: the depth floor, the same answer from the three readers, no crash at 100,000 levels.
python3 scripts/check_depth.py

# The example printed in README.md is what the implementation prints.
readme=$(printf '%s' '[{"name": "read_file", "title": "Read file", "description": "Read a file from disk.", "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}, "annotations": {"readOnlyHint": true}}]' | python3 implementations/python/tool_set_digest.py)
grep -qF -- "$readme" README.md || { echo "README.md shows another output than: $readme"; exit 1; }

# vectors/jcs-subset.json (RFC 8785 alone, for any JSON value) is what the three implementations answer now.
python3 scripts/jcs_subset.py --check

# The worked example in notes/implementation-admission.md is what its script prints.
python3 notes/implementation_admission_example.py | while IFS= read -r line; do
  grep -qF -- "$line" notes/implementation-admission.md || { echo "notes/implementation-admission.md lacks: $line"; exit 1; }
done

if [ -n "${HISTOR_PYTHONPATH:-}" ]; then
  PYTHONPATH="$HISTOR_PYTHONPATH" "${HISTOR_PYTHON:-python3}" scripts/cross_check_histor.py
fi
if [ -n "${WARDEN_DIST:-}" ]; then
  node scripts/cross_check_warden.mjs "$WARDEN_DIST"
fi
echo "all checks passed"
