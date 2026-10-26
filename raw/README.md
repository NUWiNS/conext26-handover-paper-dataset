# Raw data

The raw deposit holds the Accuver XCAL exports from the four driving
campaigns, before any parsing. Two scripts let you confirm the deposit is
complete and that it contains what the paper says it contains, without
running the full pipeline.

## 1. Integrity

```bash
python raw/check_raw.py --data /path/to/raw            # minutes
python raw/check_raw.py --data /path/to/raw --full     # exact row counts
```

Walks the deposit, parses every CSV header, checks the columns each export
kind must have, and reports per-file status plus a summary. Exits non-zero
on any missing or malformed file.

`--data` may point at the whole deposit or at a single unpacked trip
directory; both are recognised. Note that if you pipe the output, `$?` is
the exit status of the pipe, not of the checker -- check it directly. Expected output on a complete deposit:

```
kind                   files          size            rows
message log               51      26.60 GB         51,000+
signalling flow           99       0.32 GB         94,858+
KPI time series          144       9.76 GB        120,000+
5G SIB                     9       0.02 GB          9,000+

All files present and parseable.
```

## 2. Content

```bash
python raw/summarize_raw.py --data /path/to/raw --kind flow --limit 0
python raw/summarize_raw.py --data /path/to/raw --kind msgs --limit 400000
```

Streams the signalling exports and counts what the analysis is built on.
The flow pass reports completed handovers; the message pass reports the RRC
messages per operator. On the full deposit the flow pass gives:

```
completed handovers (LTE Handover == 'Success') : 28,845
handover attempts   (LTE Handover ~ 'Attempt..') : 29,140
handover failures   (LTE Handover == 'Failure')  : 80
all handover-annotated rows                      : 220,941
```

The paper reports 48K HOs in total (§1). The 28,845 here are LTE-annotated
completions in the signalling-flow export only; 5G handovers and
5G-failure-driven demotions are attributed by the parsing pipeline from the
message log, so this is a lower bound, not a mismatch.

A message pass capped at 400K rows/file gives measurement-report counts in
the thousands per operator, with `rrcConnectionReconfiguration` (the HO
command) tracking them closely — the behaviour §4 describes.

## The campaigns are not uniform

Both scripts allow for this; it is a property of the exports, not damage:

| | 2022 (trip 1) | 2023 (trips 2-3) | 2024 (trip 4) |
|---|---|---|---|
| message-log columns | Index, Time, Lon, Lat, Chipset Timestamp, Code, Message, Detail | + SIM | Index, Time, Message, Detail only |
| signalling flow | flat directory | flat directory | nested per operator |
| template data | `.csv` | `.csv` | `.xlsx` |
| file granularity | per XCAL session (45-49 files) | per operator per day | per operator per day |

The KPI time series for trips 2-4 exists only as parsed pickles; the source
CSV was not retained. Trip 1 retains `merged_csv/`.
