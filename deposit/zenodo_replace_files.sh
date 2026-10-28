#!/usr/bin/env bash
# Replace individual files on a Zenodo record that is already in edit state.
#
#   # 1. click "Edit" on the record in the browser first
#   export ZENODO_TOKEN=...                       # deposit:write is enough
#   ZENODO_DEPOSITION=23677824 bash zenodo_replace_files.sh production \
#       /path/to/processed_bundle_small.tar.gz \
#       /path/to/processed_bundle_medium.tar.gz \
#       /path/to/processed_bundle_full.tar.gz \
#       /path/to/SHA256SUMS.txt
#   # 2. click "Publish" on the record in the browser afterwards
#
# A bucket PUT replaces a file of the same name, so the old version does not
# need deleting first. Uploading through the API rather than the web form
# avoids holding a browser tab open through a multi-gigabyte transfer, where
# there is no resume.
#
# The edit and publish transitions need the deposit:actions scope. They are
# left to the browser on purpose: this script cannot publish, so it cannot
# freeze a record by accident.
set -euo pipefail

TARGET=${1:-sandbox}; shift || true
case "$TARGET" in
  sandbox)    API=https://sandbox.zenodo.org/api ;;
  production) API=https://zenodo.org/api ;;
  *) echo "usage: $0 {sandbox|production} FILE [FILE...]" >&2; exit 2 ;;
esac
[[ $# -gt 0 ]] || { echo "no files given" >&2; exit 2; }

: "${ZENODO_TOKEN:?set ZENODO_TOKEN first}"
: "${ZENODO_DEPOSITION:?set ZENODO_DEPOSITION to the record id}"
command -v jq >/dev/null || { echo "jq is required" >&2; exit 2; }
AUTH=(-H "Authorization: Bearer $ZENODO_TOKEN")

dep=$(curl -sS "${AUTH[@]}" "$API/deposit/depositions/$ZENODO_DEPOSITION")
[[ "$(jq -r '.id' <<<"$dep")" != "null" ]] || { jq . <<<"$dep"; exit 1; }
bucket=$(jq -r '.links.bucket // "null"' <<<"$dep")
state=$(jq -r '.state' <<<"$dep")

echo "== deposition $ZENODO_DEPOSITION  state=$state"
if [[ "$bucket" == "null" ]]; then
  cat >&2 <<'MSG'
No file bucket on this deposition. A published record exposes one only while
it is being edited: open the record in the browser, click Edit, then re-run.
MSG
  exit 1
fi

for f in "$@"; do
  [[ -f $f ]] || { echo "!! missing: $f" >&2; exit 1; }
  n=$(basename "$f")
  printf '   -> %-34s %s\n' "$n" "$(du -h "$f" | cut -f1)"
  curl -sS --fail --progress-bar "${AUTH[@]}" \
       --upload-file "$f" "$bucket/$n" >/dev/null
done

echo
echo "Uploaded. Files now on the draft:"
curl -sS "${AUTH[@]}" "$API/deposit/depositions/$ZENODO_DEPOSITION/files" \
  | jq -r '.[] | "   \(.filename)  \(.filesize)"' 2>/dev/null \
  || echo "   (listing unavailable; check the browser)"
echo
echo "Now publish from the browser: ${API%/api}/records/$ZENODO_DEPOSITION"
