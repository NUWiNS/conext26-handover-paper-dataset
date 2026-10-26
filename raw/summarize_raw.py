"""Extract headline numbers from the raw deposit, to compare against the paper.

Streams the raw signalling exports and counts the RRC messages and handover
events that the analysis is built on, so an evaluator can confirm the data
says what the paper says it says -- without running the full pipeline.

    python raw/summarize_raw.py --data /path/to/raw
    python raw/summarize_raw.py --data /path/to/raw --limit 2000000
    python raw/summarize_raw.py --data /path/to/raw --kind flow

--limit caps rows read per file (default 2M) so a first pass over a large
deposit finishes quickly; pass --limit 0 to read everything.

What to expect (paper, Section 4): measurement reports dominate the
HO-related RRC traffic, rrcConnectionReconfiguration marks HO commands,
and the three operators differ substantially in volume.
"""
import argparse
import collections
import csv
import re
import sys
from pathlib import Path

csv.field_size_limit(sys.maxsize)

# RRC messages that matter for HO analysis
RRC_OF_INTEREST = [
    "measurementReport",
    "rrcConnectionReconfiguration",
    "rrcConnectionReconfigurationComplete",
    "rrcConnectionReestablishmentRequest",
    "rrcReconfiguration",
    "rrcReconfigurationComplete",
    "systemInformation",
    "scgFailureInformationNR",
]
OPERATORS = ["atnt", "tmobile", "verizon"]


def operator_of(path):
    """Infer operator from the filename, where the export encodes it."""
    name = path.name.lower()
    for op in OPERATORS:
        if name.startswith(op):
            return {"atnt": "AT&T", "tmobile": "T-Mobile", "verizon": "Verizon"}[op]
    for op in OPERATORS:
        if op in [p.lower() for p in path.parts]:
            return {"atnt": "AT&T", "tmobile": "T-Mobile", "verizon": "Verizon"}[op]
    return "unattributed"       # 2022 files are named by session, not operator


def clean(msg):
    """XCAL indents the message tree with underscores; strip them."""
    return re.sub(r"^_+", "", (msg or "").strip())


def scan(path, column, limit):
    """Count values of `column`, returning (Counter, rows_read)."""
    counts = collections.Counter()
    n = 0
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        rdr = csv.DictReader(fh)
        for row in rdr:
            n += 1
            v = clean(row.get(column))
            if v:
                counts[v] += 1
            if limit and n >= limit:
                break
    return counts, n


def trip_of(path, root):
    rel = path.relative_to(root).parts
    return rel[0] if rel[0].startswith("driving_trip") else "trip_1_2022"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--limit", type=int, default=2_000_000,
                    help="max rows per file (0 = all); default 2,000,000")
    ap.add_argument("--kind", choices=["msgs", "flow", "both"], default="both")
    a = ap.parse_args()
    root = Path(a.data).resolve()

    if a.kind in ("msgs", "both"):
        print("=" * 74)
        print("RRC messages in the message-log export  (column: Message)")
        print("=" * 74)
        files = sorted(root.glob("*/signalling_msgs_csv/*.csv")) + \
                sorted(root.glob("*/*/signalling_msgs_csv/*.csv"))
        by_op = collections.defaultdict(collections.Counter)
        rows_total = 0
        for p in files:
            counts, n = scan(p, "Message", a.limit)
            rows_total += n
            by_op[operator_of(p)].update(counts)
            print(f"  scanned {p.relative_to(root)}  ({n:,} rows)")
        print(f"\n  {'message':<40}" + "".join(f"{o:>12}" for o in
              ["AT&T", "T-Mobile", "Verizon"]))
        for m in RRC_OF_INTEREST:
            vals = [by_op[o].get(m, 0) for o in ["AT&T", "T-Mobile", "Verizon"]]
            if any(vals):
                print(f"  {m:<40}" + "".join(f"{v:>12,}" for v in vals))
        print(f"\n  rows scanned: {rows_total:,}"
              + ("" if not a.limit else f"   (capped at {a.limit:,}/file)"))

    if a.kind in ("flow", "both"):
        print()
        print("=" * 74)
        print("Handover events in the signalling-flow export  (column: LTE Handover)")
        print("=" * 74)
        files = sorted(root.glob("signalling_flow/*.csv")) + \
                sorted(root.glob("*/signalling_flow/*.csv")) + \
                sorted(root.glob("*/signalling_flow/*/*.csv"))
        files = [f for f in files if "debug" not in f.parts]
        per_trip = collections.defaultdict(collections.Counter)
        for p in files:
            counts, n = scan(p, "LTE Handover", a.limit)
            per_trip[trip_of(p, root)].update(counts)
        for trip in sorted(per_trip):
            tot = sum(per_trip[trip].values())
            print(f"\n  {trip}  ({tot:,} handover-annotated rows)")
            for k, v in per_trip[trip].most_common(8):
                print(f"      {v:>9,}  {k[:58]}")
        grand = sum(sum(c.values()) for c in per_trip.values())
        success = sum(c.get("Success", 0) for c in per_trip.values())
        failure = sum(c.get("Failure", 0) for c in per_trip.values())
        attempts = sum(v for c in per_trip.values() for k, v in c.items()
                       if k.startswith("Attempt"))
        print("\n  " + "-" * 70)
        print(f"  completed handovers (LTE Handover == 'Success') : {success:,}")
        print(f"  handover attempts   (LTE Handover ~ 'Attempt..') : {attempts:,}")
        print(f"  handover failures   (LTE Handover == 'Failure')  : {failure:,}")
        print(f"  all handover-annotated rows                      : {grand:,}")
        print("  " + "-" * 70)
        print("  The paper reports 48K HOs across the four campaigns (Section 1).")
        print("  'Success' counts here are LTE-annotated completions only; 5G HOs")
        print("  and 5G-failure-driven demotions are attributed by the parsing")
        print("  pipeline from the message log, so this number is a lower bound.")


if __name__ == "__main__":
    main()
