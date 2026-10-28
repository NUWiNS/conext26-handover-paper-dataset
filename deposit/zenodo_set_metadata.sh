#!/usr/bin/env bash
# Apply zenodo_metadata.json to an existing draft WITHOUT disturbing its
# reserved DOI.
#
#   export ZENODO_TOKEN=...                       # deposit:write is enough
#   ZENODO_DEPOSITION=23677824 bash zenodo_set_metadata.sh production
#
# The upload script deliberately leaves metadata alone when pointed at an
# existing deposition, so a draft created by hand keeps whatever was typed
# into the web form. This fills it in from the JSON instead.
#
# It merges rather than replaces: the draft's current metadata is fetched
# first and our fields are layered on top, so anything Zenodo maintains
# itself -- the prereserved DOI above all -- survives.
set -euo pipefail

TARGET=${1:-sandbox}
case "$TARGET" in
  sandbox)    API=https://sandbox.zenodo.org/api ;;
  production) API=https://zenodo.org/api ;;
  *) echo "usage: $0 {sandbox|production}" >&2; exit 2 ;;
esac

: "${ZENODO_TOKEN:?set ZENODO_TOKEN first}"
: "${ZENODO_DEPOSITION:?set ZENODO_DEPOSITION to the draft id}"
command -v jq >/dev/null || { echo "jq is required" >&2; exit 2; }
AUTH=(-H "Authorization: Bearer $ZENODO_TOKEN")

echo "== Fetching draft $ZENODO_DEPOSITION"
cur=$(curl -sS "${AUTH[@]}" "$API/deposit/depositions/$ZENODO_DEPOSITION")
[[ "$(jq -r '.id' <<<"$cur")" != "null" ]] || { jq . <<<"$cur"; exit 1; }
if [[ "$(jq -r '.submitted' <<<"$cur")" == "true" ]]; then
  echo "   note: this record is published; metadata edits are still allowed."
fi
echo "   reserved DOI: $(jq -r '.metadata.prereserve_doi.doi // .doi // "none"' <<<"$cur")"

echo "== Merging zenodo_metadata.json over the current metadata"
merged=$(jq -s '{metadata: (.[0].metadata * .[1].metadata)}' \
            <(jq '{metadata}' <<<"$cur") zenodo_metadata.json)

resp=$(curl -sS "${AUTH[@]}" -H "Content-Type: application/json" \
         -X PUT "$API/deposit/depositions/$ZENODO_DEPOSITION" -d "$merged")
if [[ "$(jq -r '.id // "null"' <<<"$resp")" == "null" ]]; then
  echo "failed:"; jq . <<<"$resp"; exit 1
fi

echo "== Applied"
jq -r '.metadata | "   title     : \(.title[0:70])…\n   creators  : \(.creators|length)\n   license   : \(.license // .rights // "unset")\n   related   : \(.related_identifiers|length) identifier(s)"' <<<"$resp"
echo "   reserved DOI still: $(jq -r '.metadata.prereserve_doi.doi // .doi // "none"' <<<"$resp")"
echo
echo "Review at ${API%/api}/deposit/$ZENODO_DEPOSITION then publish from the UI."
