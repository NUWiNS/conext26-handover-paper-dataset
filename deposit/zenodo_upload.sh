#!/usr/bin/env bash
# Create a Zenodo draft, reserve its DOI, and stream the deposit tarballs up.
#
#   export ZENODO_TOKEN=...          # token with deposit:write ONLY
#   bash zenodo_upload.sh sandbox                 # dry run (10.5072 DOIs)
#   bash zenodo_upload.sh production              # create a fresh draft
#   ZENODO_DEPOSITION=23677824 \
#     bash zenodo_upload.sh production            # upload into an EXISTING draft
#
# Set ZENODO_DEPOSITION when the draft already exists and already has its DOI
# reserved -- the script then only uploads files and leaves the metadata and the
# reserved DOI exactly as they are.
#
# This script deliberately does NOT publish. Publishing is irreversible: the DOI
# goes live and the files are frozen (you may start a file correction within 30
# days of publishing, and must publish that correction within 45 days).
#
# Give the token deposit:write and NOT deposit:actions. deposit:actions is the
# scope that grants publishing, so a token without it cannot publish the record
# even by accident. Publish by hand from the web UI after checking the draft.
set -euo pipefail

TARGET=${1:-sandbox}
TARDIR=${2:-/mnt/nuwinsshared/moinak/conext26_dataset/tarballs}

case "$TARGET" in
  sandbox)    API=https://sandbox.zenodo.org/api ;;
  production) API=https://zenodo.org/api ;;
  *) echo "usage: $0 {sandbox|production} [tarball-dir]" >&2; exit 2 ;;
esac

: "${ZENODO_TOKEN:?set ZENODO_TOKEN first}"
command -v jq >/dev/null || { echo "jq is required" >&2; exit 2; }

AUTH=(-H "Authorization: Bearer $ZENODO_TOKEN")

if [[ -n "${ZENODO_DEPOSITION:-}" ]]; then
  echo "== Using existing draft $ZENODO_DEPOSITION on $TARGET"
  draft=$(curl -sS "${AUTH[@]}" "$API/deposit/depositions/$ZENODO_DEPOSITION")
  id=$(jq -r '.id' <<<"$draft")
  [[ "$id" != "null" ]] || { echo "could not open that draft:"; jq . <<<"$draft"; exit 1; }
  if [[ "$(jq -r '.submitted' <<<"$draft")" == "true" ]]; then
    echo "   refusing: deposition $id is already published; its files are frozen." >&2
    exit 1
  fi
  bucket=$(jq -r '.links.bucket' <<<"$draft")
  doi=$(jq -r '.metadata.prereserve_doi.doi // .doi // "none"' <<<"$draft")
  echo "   reserved DOI  : $doi  (metadata left untouched)"
else
  echo "== Creating draft on $TARGET"
  draft=$(curl -sS "${AUTH[@]}" -H "Content-Type: application/json" \
            -X POST "$API/deposit/depositions" -d '{}')
  id=$(jq -r '.id' <<<"$draft")
  bucket=$(jq -r '.links.bucket' <<<"$draft")
  [[ "$id" != "null" ]] || { echo "draft creation failed:"; jq . <<<"$draft"; exit 1; }
  echo "   deposition id : $id"

  echo "== Attaching metadata + reserving DOI"
  meta=$(jq '.metadata.prereserve_doi = true' zenodo_metadata.json)
  resp=$(curl -sS "${AUTH[@]}" -H "Content-Type: application/json" \
           -X PUT "$API/deposit/depositions/$id" -d "$meta")
  doi=$(jq -r '.metadata.prereserve_doi.doi // "none"' <<<"$resp")
  echo "   reserved DOI  : $doi"
  echo "   (reserved only -- it will not resolve until the record is published)"
fi
echo "   bucket        : $bucket"

echo "== Uploading tarballs"
shopt -s nullglob
for f in "$TARDIR"/*.tar.gz "$TARDIR"/SHA256SUMS.txt; do
  n=$(basename "$f")
  echo "   -> $n ($(du -h "$f" | cut -f1))"
  curl -sS --fail --progress-bar "${AUTH[@]}" \
       --upload-file "$f" "$bucket/$n" >/dev/null
done

echo
echo "Draft ready: ${API%/api}/deposit/$id"
echo "Reserved DOI: $doi"
echo "Review it in the browser, then publish from the UI."
