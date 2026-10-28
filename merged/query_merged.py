#!/usr/bin/env python3
"""Pull slices out of the merged measurement data by trip, operator and date.

Each `<trip>_all_df.pkl` is a Python *list* of pandas DataFrames, one per
measurement run.  Every run carries a single `Operator` value and a
`Timestamp` column, so runs can be selected without materialising the whole
trip as one frame.

    # what is in the deposit
    python query_merged.py --data ./merged --list

    # one operator, one trip, as a list of per-run frames
    python query_merged.py --data ./merged --trip trip2_2023 --operator Verizon \
                           --out verizon_trip2.pkl

    # a date range, concatenated into a single frame, selected columns only
    python query_merged.py --data ./merged --trip trip4_2024 --operator AT\&T \
         --from 2024-11-20 --to 2024-11-25 \
         --columns Timestamp,Lat,Lon,Operator --concat --out slice.pkl

    # 1% row sample across every trip, for a quick look
    python query_merged.py --data ./merged --sample 0.01 --concat --out peek.pkl

Memory: a trip is loaded whole before filtering (pickle has no random access),
so peak usage is roughly the uncompressed size of that one trip's file. Work
one trip at a time if you are tight on RAM -- `--trip` does exactly that.
"""
import argparse, pickle, sys
from pathlib import Path

import pandas as pd


def trip_files(data: Path):
    """{trip_name: path} for every *_all_df.pkl in the data directory."""
    found = {}
    for p in sorted(data.glob("*_all_df.pkl")):
        found[p.name[: -len("_all_df.pkl")]] = p
    return found


def load_trip(path: Path):
    with path.open("rb") as fh:
        return pickle.load(fh)


def run_operator(df):
    if "Operator" not in df.columns or len(df) == 0:
        return None
    vals = df["Operator"].dropna().unique()
    return str(vals[0]) if len(vals) else None


def parse_time(series):
    """`Timestamp` is float64 Unix epoch SECONDS (e.g. 1684158868.09).

    Passing it to pd.to_datetime without unit="s" makes pandas read the values
    as nanoseconds and silently collapses every date to 1970-01-01, so the
    unit is not optional here. Returned tz-aware in UTC; the separate
    `GPS Time` column is local wall-clock and is not used for filtering.
    """
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_datetime(series, unit="s", errors="coerce", utc=True)
    return pd.to_datetime(series, errors="coerce", utc=True)


def run_timespan(df):
    if "Timestamp" not in df.columns:
        return None, None
    ts = parse_time(df["Timestamp"]).dropna()
    return (ts.min(), ts.max()) if len(ts) else (None, None)


def cmd_list(data: Path, only=None):
    files = trip_files(data)
    if not files:
        sys.exit(f"no *_all_df.pkl found under {data}")
    if only:
        missing = set(only) - set(files)
        if missing:
            sys.exit(f"unknown trip(s): {', '.join(sorted(missing))}\n"
                     f"available: {', '.join(sorted(files))}")
        files = {t: files[t] for t in only}
    elif len(files) > 1:
        print(f"listing {len(files)} trips one at a time; peak memory is the "
              f"largest single trip (~50 GB). Use --trip to do just one.\n",
              file=sys.stderr)
    for trip, path in files.items():
        print(f"\n=== {trip}  ({path.stat().st_size / 1e9:.1f} GB on disk)")
        runs = load_trip(path)
        agg = {}
        for df in runs:
            op = run_operator(df)
            if op is None:
                continue
            lo, hi = run_timespan(df)
            a = agg.setdefault(op, {"runs": 0, "rows": 0, "lo": None, "hi": None})
            a["runs"] += 1
            a["rows"] += len(df)
            if lo is not None:
                a["lo"] = lo if a["lo"] is None else min(a["lo"], lo)
                a["hi"] = hi if a["hi"] is None else max(a["hi"], hi)
        print(f"  {len(runs)} runs, {sum(len(d) for d in runs):,} rows, "
              f"{len(runs[0].columns)} columns")
        for op in sorted(agg):
            a = agg[op]
            span = (f"{str(a['lo'])[:10]} .. {str(a['hi'])[:10]}"
                    if a["lo"] is not None else "no timestamps")
            print(f"    {op:14} {a['runs']:5} runs  {a['rows']:12,} rows  {span}")
        del runs


def main():
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__)
    ap.add_argument("--data", required=True, type=Path,
                    help="directory holding the *_all_df.pkl files")
    ap.add_argument("--list", action="store_true",
                    help="show trips, operators and date ranges, then exit")
    ap.add_argument("--trip", action="append",
                    help="restrict to this trip (repeatable)")
    ap.add_argument("--operator", action="append",
                    help="restrict to this operator, case-insensitive (repeatable)")
    ap.add_argument("--from", dest="date_from", help="earliest date, YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", help="latest date, YYYY-MM-DD")
    ap.add_argument("--columns", help="comma-separated subset of columns to keep")
    ap.add_argument("--sample", type=float,
                    help="keep this fraction of rows (0-1), sampled per run")
    ap.add_argument("--concat", action="store_true",
                    help="return one concatenated DataFrame instead of a list")
    ap.add_argument("--out", type=Path, help="write the result as a pickle")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if not args.data.is_dir():
        sys.exit(f"--data {args.data} is not a directory")
    if args.list:
        cmd_list(args.data, args.trip)
        return
    if args.sample is not None and not 0 < args.sample <= 1:
        sys.exit("--sample must be in (0, 1]")

    files = trip_files(args.data)
    if args.trip:
        missing = set(args.trip) - set(files)
        if missing:
            sys.exit(f"unknown trip(s): {', '.join(sorted(missing))}\n"
                     f"available: {', '.join(sorted(files))}")
        files = {t: files[t] for t in args.trip}
    want_ops = {o.lower() for o in args.operator} if args.operator else None
    # Bounds are tz-aware UTC to match parse_time(); a naive bound would raise
    # on comparison against a tz-aware series.
    lo = pd.Timestamp(args.date_from, tz="UTC") if args.date_from else None
    hi = (pd.Timestamp(args.date_to, tz="UTC") + pd.Timedelta(days=1)) if args.date_to else None
    cols = [c.strip() for c in args.columns.split(",")] if args.columns else None

    kept, n_rows = [], 0
    for trip, path in files.items():
        print(f"scanning {trip} ...", file=sys.stderr, flush=True)
        runs = load_trip(path)
        for df in runs:
            op = run_operator(df)
            if op is None:
                continue
            if want_ops and op.lower() not in want_ops:
                continue
            if lo is not None or hi is not None:
                if "Timestamp" not in df.columns:
                    continue
                ts = parse_time(df["Timestamp"])
                mask = pd.Series(True, index=df.index)
                if lo is not None:
                    mask &= ts >= lo
                if hi is not None:
                    mask &= ts < hi
                df = df[mask]
                if len(df) == 0:
                    continue
            if cols:
                have = [c for c in cols if c in df.columns]
                if not have:
                    continue
                df = df[have]
            if args.sample is not None:
                df = df.sample(frac=args.sample, random_state=args.seed)
                if len(df) == 0:
                    continue
            df = df.copy()
            df["_trip"] = trip
            kept.append(df)
            n_rows += len(df)
        del runs

    print(f"\n{len(kept)} runs matched, {n_rows:,} rows", file=sys.stderr)
    if not kept:
        sys.exit("nothing matched")

    result = pd.concat(kept, ignore_index=True) if args.concat else kept
    if args.out:
        with args.out.open("wb") as fh:
            pickle.dump(result, fh, protocol=4)
        print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB)",
              file=sys.stderr)
    elif args.concat:
        print(result.head().to_string())
    else:
        print(f"(use --out to save, or --concat to preview)", file=sys.stderr)


if __name__ == "__main__":
    main()
