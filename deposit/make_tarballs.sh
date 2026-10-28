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
BUNDLE_SMALL=/mnt/nuwinsshared/moinak/conext26_dataset/bundle_small

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
echo "=== Tier 2: processed bundle ==="
if [[ -d $BUNDLE_SMALL ]]; then
  dst="$OUT/processed_bundle_small.tar.gz"
  if [[ -s $dst ]]; then
    echo "SKIP  $(basename "$dst") (already built)"
  else
    echo "BUILD $(basename "$dst")"
    tar --exclude=__pycache__ -I 'gzip -6' -cf "$dst" \
        -C "$(dirname "$BUNDLE_SMALL")" "$(basename "$BUNDLE_SMALL")"
    printf '      -> %s\n' "$(du -h "$dst" | cut -f1)"
  fi
else
  echo "!! $BUNDLE_SMALL missing; build it with prepare/make_processed_bundle.py" >&2
fi

echo
echo "=== Deposit ==="
ls -lh "$OUT"/*.tar.gz 2>/dev/null || { echo "nothing built" >&2; exit 1; }

echo
echo "=== SHA-256 ==="
( cd "$OUT" && sha256sum ./*.tar.gz | sed 's|\./||' | tee SHA256SUMS.txt )

echo
echo "Total: $(du -sh "$OUT" | cut -f1)"
