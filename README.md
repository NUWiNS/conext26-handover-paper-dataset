# [CoNEXT '26] Too Many Reports, Too Few Handovers: A Large-Scale Study of Configuration Inefficiencies in Operational 5G Networks

In this repository, we release the dataset and scripts used in the CoNEXT '26
paper, *Too Many Reports, Too Few Handovers: A Large-Scale Study of
Configuration Inefficiencies in Operational 5G Networks*.

The dataset was collected during four cross-country driving trips across the US
over a 27-month period, covering 15,000+ km and all three major US operators
(AT&T, T-Mobile, and Verizon), both LTE and 5G, both 5G architectures (NSA and
SA), and all 5G frequency bands (low, mid, and high).

## Contents

The release has two parts:

- **Raw** — the per-trip measurement logs and the parsing pipeline that turns
  them into the processed tables. Large (~200 GB); deposited separately.
- **Processed** — the derived pickles the paper's figures are computed from,
  plus the figure-generation scripts in this repository. Small enough to work
  with directly (the figures in §4, §5.2 and §5.3 need ~53 MB).

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
figures/
  config.py              path resolution
  common.py              operator/event naming, colours, loaders
  fig_events.py          §4  reporting events and signalling overhead
  fig_aggressiveness.py  §5.2 configuration aggressiveness
  fig_concentration.py   §5.3 operational concentration
  make_figures.py        driver
prepare/
  make_event_tables.py   derives the small event tables from the full tier
```

## Citation

If you use this dataset, please cite the CoNEXT '26 paper.
