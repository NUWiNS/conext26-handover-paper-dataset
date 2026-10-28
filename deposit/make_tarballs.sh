#!/usr/bin/env bash
# Build the Zenodo deposit tarballs.
#
#   bash make_tarballs.sh [outdir]
#
# Tier 1 (merged measurement data) is one tarball per trip, each holding a
# single pickle renamed to the trip-qualified name that merged/README.md and
# merged/query_merged.py expect. Per-trip rather than one archive so a
# reviewer who wants 2023 does not download 2024 as well.
#
# Tier 2 (processed) is the trimmed bundle the figure scripts read.
#
# Already-built tarballs are skipped, so the script is safe to re-run.
set -euo pipefail

OUT=${1:-/mnt/nuwinsshared/moinak/conext26_dataset/tarballs}
BUNDLE_ROOT=/mnt/nuwinsshared/moinak/conext26_dataset
ANALYSIS_SRC=/home/moinakgh/csv_ho
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# trip label -> source all_df.pkl
declare -A MERGED=(
  [trip1_2022]=/home/moinakgh/csv_ho/merged_pickles/all_df.pkl
  [trip2_2023]=/home/moinakgh/csv_ho/driving_trip_2/merged_pickles/all_df.pkl
  [trip3_2023]=/home/moinakgh/csv_ho/driving_trip_3/merged_pickles/all_df.pkl
  [trip4_2024]=/home/moinakgh/csv_ho/driving_trip_lax_bos_2024/merged_pickles/all_df.pkl
)

mkdir -p "$OUT"

echo "=== Tier 1: merged measurement data ==="
for trip in $(printf '%s\n' "${!MERGED[@]}" | sort); do
  src=${MERGED[$trip]}
  dst="$OUT/${trip}_all_df.tar.gz"
  member="${trip}_all_df.pkl"

  if [[ ! -f $src ]]; then
    echo "!! $trip: $src missing, skipping" >&2
    continue
  fi
  if [[ -s $dst ]]; then
    echo "SKIP  $(basename "$dst") (already built)"
    continue
  fi

  printf 'BUILD %-28s from %s (%s)\n' "$(basename "$dst")" "$src" \
         "$(du -h "$src" | cut -f1)"
  t0=$SECONDS
  # --transform renames all_df.pkl -> <trip>_all_df.pkl inside the archive,
  # since all four sources share the same basename.
  tar --transform="s|^all_df\.pkl$|${member}|" \
      -I 'gzip -6' -cf "$dst" -C "$(dirname "$src")" all_df.pkl
  printf '      -> %s in %ss\n' "$(du -h "$dst" | cut -f1)" "$((SECONDS - t0))"
done

echo
echo "=== Tier 2: processed bundles ==="
# Tiers are cumulative, so each tarball is self-contained: a reviewer
# downloads the single one matching the figures they want to regenerate.
for tier in small medium full; do
  src="$BUNDLE_ROOT/bundle_$tier"
  dst="$OUT/processed_bundle_$tier.tar.gz"

  if [[ ! -d $src ]]; then
    echo "BUILD bundle_$tier"
    python3 "$REPO/prepare/make_processed_bundle.py" \
            --src "$ANALYSIS_SRC" --out "$src" --tier "$tier" >/dev/null || {
      echo "!! could not assemble bundle_$tier" >&2; continue; }
  fi
  if [[ -s $dst ]]; then
    echo "SKIP  $(basename "$dst") (already built)"
    continue
  fi
  printf 'BUILD %-34s from %s\n' "$(basename "$dst")" "$(du -sh "$src" | cut -f1)"
  t0=$SECONDS
  tar --exclude=__pycache__ -I 'gzip -6' -cf "$dst" \
      -C "$(dirname "$src")" "$(basename "$src")"
  printf '      -> %s in %ss\n' "$(du -h "$dst" | cut -f1)" "$((SECONDS - t0))"
done

echo
echo "=== Deposit ==="
ls -lh "$OUT"/*.tar.gz 2>/dev/null || { echo "nothing built" >&2; exit 1; }

echo
echo "=== SHA-256 ==="
( cd "$OUT" && sha256sum ./*.tar.gz | sed 's|\./||' | tee SHA256SUMS.txt )

echo
echo "Total: $(du -sh "$OUT" | cut -f1)"
