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

The release has two tiers. Tier 1 is in this repository under `data/` via
Git LFS and mirrored on Zenodo; tier 2 is on Zenodo.

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

See [`merged/README.md`](merged/README.md) for the data model and the column
reference.

### Tier 2 — processed

The derived pickles the figures are computed from, plus the figure scripts in
this repository. ~53 MB.

## Getting the data

The merged tarballs are in this repository under `data/`, stored with Git LFS,
and mirrored in the Zenodo record.

### From GitHub

```bash
git lfs install
git clone https://github.com/NUWiNS/conext26-handover-paper-dataset.git
cd conext26-handover-paper-dataset           # ~1.7 GB of LFS objects
```

To avoid pulling all four trips, skip the LFS download on clone and fetch only
what you need:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/NUWiNS/conext26-handover-paper-dataset.git
cd conext26-handover-paper-dataset
git lfs pull --include="data/trip2_2023_all_df.tar.gz"
```

> **Checksums will fail until you pull.** Files you have not fetched are
> 134-byte LFS pointers, not archives, so `sha256sum -c` reports them as
> FAILED. That is expected — verify only what you have actually pulled.

### From Zenodo

```bash
curl -LO https://zenodo.org/records/23677824/files/trip2_2023_all_df.tar.gz
curl -LO https://zenodo.org/records/23677824/files/processed_bundle_small.tar.gz
```

### Verify and unpack

```bash
sha256sum -c data/SHA256SUMS.txt --ignore-missing
tar -xzf data/trip2_2023_all_df.tar.gz        # -> trip2_2023_all_df.pkl
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

```bibtex
@article{ghoshal:conext2026,
  title={Too Many Reports, Too Few Handovers: A Large-Scale Study of Configuration Inefficiencies in Operational 5G Networks},
  author={Ghoshal, Moinak and Khan, Imran and Dinh, Phuc and Kong, Z. Jonny and Basit, Omar and Wang, Sizhe and Feng, Yufei and Hu, Y Charlie and Koutsonikolas, Dimitrios},
  booktitle={In Proceedings of the 22nd ACM International Conference on Emerging Networking EXperiments and Technologies},
  year={2026}
}
```
