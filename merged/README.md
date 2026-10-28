# Merged measurement data

This is the primary data tier of the deposit: the per-run merged dataframes
that every analysis in the paper is computed from. One file per driving trip.

A note on naming: these are called *merged* rather than *raw* because they are
a join of three XCAL Solo exports (the per-second PHY/KPI series, the
signalling flow, and the RRC message log) plus a handful of columns derived by
our parser. The underlying XCAL CSV exports are ~188 GB and are not part of
this deposit; see the top-level README.

## Files

| File | Trip | Dates | Runs | Rows |
|---|---|---|---|---|
| `trip1_2022_all_df.pkl` | 2022, cross-country | 2022-08-07 – 2022-08-15 | 5,921 | 5,173,008 |
| `trip2_2023_all_df.pkl` | 2023, Boston–Chicago | 2023-05-13 – 2023-05-16 | 1,064 | 1,859,096 |
| `trip3_2023_all_df.pkl` | 2023 | 2023-08-05 – 2023-08-08 | 8,632 | 3,252,927 |
| `trip4_2024_all_df.pkl` | 2024, LAX–Boston | 2024-11-01 – 2024-11-08 | 2,154 | 6,223,082 |
| | | | **17,771** | **16,508,113** |

Per operator:

| Trip | Operator | Runs | Rows | Dates |
|---|---|---|---|---|
| trip1_2022 | AT&T | 1,186 | 1,571,993 | 2022-08-08 – 2022-08-15 |
| trip1_2022 | T-Mobile | 2,183 | 1,571,710 | 2022-08-08 – 2022-08-15 |
| trip1_2022 | Verizon | 1,903 | 1,677,087 | 2022-08-07 – 2022-08-15 |
| trip1_2022 | `(Searching)` | 9 | 10,431 | 2022-08-08 |
| trip1_2022 | `No service` | 30 | 32,233 | 2022-08-15 |
| trip2_2023 | AT&T | 686 | 648,891 | 2023-05-13 – 2023-05-16 |
| trip2_2023 | T-Mobile | 171 | 613,356 | 2023-05-13 – 2023-05-16 |
| trip2_2023 | Verizon | 207 | 596,849 | 2023-05-13 – 2023-05-16 |
| trip3_2023 | AT&T | 274 | 1,110,355 | 2023-08-05 – 2023-08-08 |
| trip3_2023 | T-Mobile | 7,957 | 1,175,316 | 2023-08-05 – 2023-08-08 |
| trip3_2023 | Verizon | 401 | 967,256 | 2023-08-05 – 2023-08-08 |
| trip4_2024 | AT&T | 1,037 | 2,065,308 | 2024-11-01 – 2024-11-08 |
| trip4_2024 | T-Mobile | 517 | 2,042,870 | 2024-11-01 – 2024-11-08 |
| trip4_2024 | Verizon | 600 | 2,114,904 | 2024-11-01 – 2024-11-08 |

## Data model

Each file unpickles to a **Python `list` of `pandas.DataFrame`**, one frame per
measurement run. It is *not* a single DataFrame:

```python
import pickle
runs = pickle.load(open("trip2_2023_all_df.pkl", "rb"))
type(runs)      # list
len(runs)       # 1064
runs[0].shape   # (4420, 362)
```

`runs[0].shape` works; `runs.shape` raises `AttributeError`. Every frame in a
run carries exactly one `Operator` value, so runs can be selected by operator
without touching the row data.

## Quick start

```bash
pip install -r ../requirements.txt

# what is in here
python query_merged.py --data . --list

# one operator from one trip
python query_merged.py --data . --trip trip2_2023 --operator Verizon \
                       --out verizon_trip2.pkl

# a date range, selected columns, as one concatenated frame
python query_merged.py --data . --trip trip4_2024 --operator AT\&T \
       --from 2024-11-01 --to 2024-11-03 \
       --columns Timestamp,Lat,Lon,Operator,Handover_5G --concat --out slice.pkl

# 1% sample of everything, for a quick look
python query_merged.py --data . --sample 0.01 --concat --out peek.pkl
```

## Three things that will bite you

**1. `Timestamp` is float64 Unix epoch *seconds*.** Converting it without
specifying the unit makes pandas read the values as nanoseconds and silently
collapse every date to 1970-01-01 — no error, just wrong answers:

```python
pd.to_datetime(df["Timestamp"])              # WRONG -> 1970-01-01 00:00:01.68
pd.to_datetime(df["Timestamp"], unit="s")    # right -> 2023-05-15 13:54:28
```

Values are UTC and `Timestamp` is non-null on 100% of rows. The separate
`GPS Time` column is local wall-clock and is sparse — the column exists on
every row but is populated on only 7.6% of them (measured on trip 2) — so it
is not suitable for filtering.

**2. There is no fixed schema.** Columns vary run to run, because XCAL only
emits fields the chipset actually reported:

| | Columns |
|---|---|
| Union across all four trips | **840** |
| Union within one trip | 657 – 769 |
| Common to every run of one trip | 228 – 340 |
| Common to every run of every trip | **171** |

Always check for a column before using it. Do not assume a frame's columns
match its neighbour's:

```python
if "5G KPI PCell RF Serving SSB RSRP [dBm]" in df.columns:
    ...
```

**3. `Operator` sometimes holds a radio state, not an operator.** Trip 1
contains `(Searching)` (9 runs) and `No service` (30 runs) — UE states that
reached the field during cell reselection. Together they are 42,664 rows, 0.8%
of that trip. Filter to the three operator names explicitly rather than
grouping by whatever `Operator` happens to contain.

A related point on comparability: run *counts* differ wildly between operators
(trip 3 has 7,957 T-Mobile runs against 274 AT&T) because logs were segmented
differently, but row counts per operator are close to balanced within each
trip — the three phones drove the same routes simultaneously. Weight by rows,
not by runs.

## Column reference

840 distinct columns across the deposit, in these families:

| Family | Prefix / pattern | Union | Always present | What it is |
|---|---|---|---|---|
| Identity & time | `Operator`, `Phone_num`, `Timestamp`, `Diff_Timestamp` | 4 | 3 | run identity, epoch seconds, inter-sample gap |
| GPS & mobility | `GPS *`, `Lat`, `Lon` | 28 | 11 | position, speed, heading, satellite detail |
| 5G NR KPIs | `5G KPI *` | 470 | 98 | serving/neighbour RSRP, RSRQ, SINR, MCS, BLER, RB counts, PDSCH/PUSCH throughput, PCI, beam index |
| LTE KPIs | `LTE KPI *` | 160 | 37 | the LTE equivalents |
| Throughput & app | `*Throughput*`, `Smart Phone *` | 142 | 16 | app-layer and network-layer byte counters |
| Reporting events | `Event *`, `event*`, `B1_`, `B2_`, `Periodic_` | 34 | 8 | per-event trigger records (A1–A6, B1, B2, periodic) |
| HO & meas config | `Handover_*`, `Measconfig_*`, `MeasurementReport_*` | 9 | 9 | **parser-derived**, see below |
| SIBs | `sib*` | 17 | 0 | decoded system information blocks |
| Signalling | `DM`, `Interface`, `LTE Handover`, `NR Handover`, `Piggybacked RRC/NAS` | 5 | 0 | fields carried over from the signalling-flow export |
| Timing advance | `Qualcomm 5G-NR MAC CE Timing Advance Info *` | — | 0 | TA command and adjustment, where the chipset reported it |

The nine parser-derived columns, which carry the handover configurations the
paper analyses, are present in **every** run of every trip:

```
Handover_5G                           Measconfig_LTE-reportConfigEUTRA
Handover_LTE                          Measconfig_LTE-reportConfigInterRAT
Measconfig_5G                         Measconfig_LTE-reportConfigNR
Measconfig_LTE                        MeasurementReport_5G
                                      MeasurementReport_LTE
```

`Measconfig_*` hold the measurement configuration advertised by the network
(event thresholds, offsets, hysteresis, time-to-trigger, trigger quantity).
`Handover_*` mark executed handovers. `MeasurementReport_*` mark reports sent
by the UE. These are our parser's output, extracted from RRC reconfiguration
messages in the underlying message log.

## Memory

Pickle has no random access, so a trip is loaded whole before any filtering.
Peak memory is roughly the uncompressed file size times two:

| File | Uncompressed | Approx. peak RAM |
|---|---|---|
| `trip2_2023_all_df.pkl` | 7.3 GB | ~15 GB |
| `trip1_2022_all_df.pkl` | 19 GB | ~40 GB |
| `trip4_2024_all_df.pkl` | 25 GB | ~50 GB |

**Load one trip at a time.** Loading all four at once needs roughly 120 GB and
will take down a machine that does not have it. `query_merged.py --trip` does
the right thing by default.

To keep memory flat, iterate rather than accumulate:

```python
for run_df in pickle.load(open("trip4_2024_all_df.pkl", "rb")):
    result.append(summarise(run_df))     # keep the summary, not the frame
```

## Versions

These are pickles, which are sensitive to library versions. Use the pins in
`../requirements.txt` (Python 3.10, numpy 2.2.2, pandas 2.3.1). The files were
written in 2024 and still reference the pre-NumPy-2.0 module path
`numpy.core.multiarray`; they load under the pinned versions through NumPy's
compatibility shim, which emits an `ImportWarning`. Newer NumPy may drop that
shim.
