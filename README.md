# [CoNEXT '26] Too Many Reports, Too Few Handovers: A Large-Scale Study of Configuration Inefficiencies in Operational 5G Networks

In this repository, we release the dataset and scripts used in the CoNEXT '26
paper, *Too Many Reports, Too Few Handovers: A Large-Scale Study of
Configuration Inefficiencies in Operational 5G Networks*.

The dataset was collected during four cross-country driving trips across the US
over a 27-month period, covering 15,000+ km and all three major US operators
(AT&T, T-Mobile, and Verizon), both LTE and 5G, both 5G architectures (NSA and
SA), and all 5G frequency bands (low, mid, and high).

**Data archive:** [10.5281/zenodo.23677824](https://doi.org/10.5281/zenodo.23677824)

## Contents

The release has two tiers. Both are on Zenodo; this repository holds only the
code.

### Tier 1 — merged measurement data

The per-run merged dataframes every analysis in the paper is computed from:
**17,771 runs, 16,508,113 rows**, spanning 2022-08-07 to 2024-11-08. One
tarball per trip.

| Tarball | Trip | Uncompressed |
|---|---|---|
| `trip1_2022_all_df.tar.gz` | 2022 cross-country | 19 GB |
| `trip2_2023_all_df.tar.gz` | 2023 Boston–Chicago | 7.3 GB |
| `trip3_2023_all_df.tar.gz` | 2023 | 12 GB |
| `trip4_2024_all_df.tar.gz` | 2024 LAX–Boston | 25 GB |

They compress roughly 25×, so the whole tier is about 2 GB to download; the
exact sizes are in `SHA256SUMS.txt` in the Zenodo record.

See [`merged/README.md`](merged/README.md) for the data model, the column
reference, and three behaviours that will otherwise catch you out.

These are called *merged* rather than *raw* because they join three XCAL Solo
exports and add parser-derived columns. The underlying XCAL CSV exports are
~188 GB and are not deposited.

### Tier 2 — processed

The derived pickles the figures are computed from, plus the figure scripts in
this repository. ~53 MB — enough for the figures in §4, §5.2 and §5.3.

## Getting the data

```bash
# smallest useful download: everything the figure scripts need
curl -LO https://zenodo.org/records/23677824/files/processed_bundle_small.tar.gz
tar -xzf processed_bundle_small.tar.gz

# one trip of merged data
curl -LO https://zenodo.org/records/23677824/files/trip2_2023_all_df.tar.gz
tar -xzf trip2_2023_all_df.tar.gz
```

Verify any download against `SHA256SUMS.txt` from the same record:

```bash
sha256sum -c SHA256SUMS.txt --ignore-missing
```

Then explore the merged data by trip, operator and date:

```bash
pip install -r requirements.txt
python merged/query_merged.py --data . --trip trip2_2023 --list
python merged/query_merged.py --data . --trip trip2_2023 --operator Verizon \
       --from 2023-05-14 --to 2023-05-15 --concat --out verizon.pkl
```

> One trip is loaded whole before filtering, so peak memory is roughly twice
> the uncompressed file. Work one trip at a time; loading all four at once
> needs about 120 GB.

## Regenerating the figures

```bash
pip install -r requirements.txt
cd figures
python make_figures.py --data /path/to/processed --out ../figures_out
```

Useful flags:

```bash
python make_figures.py --list              # figure -> module mapping
python make_figures.py --only events       # run a single module
```

Paths are resolved through `figures/config.py`, from `--data` or the
`CONEXT26_DATA` environment variable; nothing is hardcoded. Each module is
independent, so if you have only part of the dataset the rest still run and
the missing ones are reported as skipped.

`MANIFEST.md` lists every figure in the paper, the script that produces it,
the data it needs, and which tier that data lives in.

## Layout

```
merged/
  query_merged.py        slice tier 1 by trip, operator and date
  README.md              data model and column reference
figures/
  config.py              path resolution
  common.py              operator/event naming, colours, loaders
  fig_events.py          §4  reporting events and signalling overhead
  fig_aggressiveness.py  §5.2 configuration aggressiveness
  fig_concentration.py   §5.3 operational concentration
  make_figures.py        driver
prepare/
  make_event_tables.py   derives the small event tables
  make_processed_bundle.py  assembles the tier-2 bundle
deposit/
  make_tarballs.sh       builds the deposit tarballs and checksums
  zenodo_metadata.json   record metadata
  zenodo_upload.sh       uploads to a Zenodo draft
```

## Citation

If you use this dataset, please cite the CoNEXT '26 paper and the Zenodo
record:

- Paper: [10.1145/3856978](https://doi.org/10.1145/3856978) — *Proc. ACM Netw.*
  4, CoNEXT4, Article 64 (December 2026).
- Dataset: [10.5281/zenodo.23677824](https://doi.org/10.5281/zenodo.23677824)
