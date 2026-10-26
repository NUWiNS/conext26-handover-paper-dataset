"""Integrity check for the raw deposit.

Verifies that the raw exports are present, parseable, and carry the columns
the parsing pipeline expects. Prints one line per file plus a summary, and
exits non-zero if anything is missing or malformed.

    python raw/check_raw.py --data /path/to/raw
    python raw/check_raw.py --data /path/to/raw --full    # exact row counts

By default only the header and first 1000 rows of each file are read, so a
large deposit checks in minutes. --full streams every row.

Note the campaigns are not uniform, and the checker allows for it:
  * 2022 message logs carry Lon/Lat; 2023 carry SIM/Code; 2024 carry
    only Index/Time/Message/Detail.
  * 2024 signalling-flow files are nested one level deeper, per operator.
  * 2024 template data ships as .xlsx; earlier campaigns ship .csv.
"""
import argparse
import csv
import sys
from pathlib import Path

csv.field_size_limit(sys.maxsize)

# name -> dict(globs, must, any_of, exts)
#   must   : columns required in every campaign
#   any_of : each entry is a set; at least one member must be present
KINDS = [
    dict(name="message log",
         globs=["*/signalling_msgs_csv", "*/*/signalling_msgs_csv"],
         must={"Index", "Message", "Detail"},
         any_of=[{"Time"}],
         exts={".csv"}),
    dict(name="signalling flow",
         globs=["signalling_flow", "*/signalling_flow"],
         must={"UE", "Interface", "Message"},
         any_of=[{"TimeStamp", "Time"}],
         exts={".csv"}),
    dict(name="KPI time series",
         globs=["merged_csv", "template_data", "*/template_data", "*/merged_csv"],
         must=set(),
         any_of=[{"Timestamp", "TIME_STAMP"}, {"Lon", "Lat"}],
         exts={".csv", ".xlsx"}),
    dict(name="5G SIB",
         globs=["*/signalling_messages_5G_SIB"],
         must=set(), any_of=[], exts={".csv"}),
]


def data_files(root, globs, exts):
    """All data files under the matching directories, recursing but
    skipping derived debug/ output."""
    out = []
    for pat in globs:
        for d in sorted(root.glob(pat)):
            if not d.is_dir():
                continue
            for p in sorted(d.rglob("*")):
                if p.is_file() and p.suffix.lower() in exts \
                        and "debug" not in p.relative_to(d).parts:
                    out.append(p)
    return sorted(set(out))


def check_file(path, must, any_of, full):
    """Return (rows, problems, error)."""
    if path.suffix.lower() == ".xlsx":
        # Not parsed here: validating xlsx would pull in a heavy dependency.
        return 0, [], None
    try:
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            rdr = csv.reader(fh)
            hdr = [h.strip().lstrip("﻿") for h in next(rdr)]
            cols = set(hdr)
            problems = sorted(must - cols)
            for group in any_of:
                if not (group & cols):
                    problems.append("one of " + "/".join(sorted(group)))
            n = 0
            for _ in rdr:
                n += 1
                if not full and n >= 1000:
                    break
            return n, problems, None
    except StopIteration:
        return 0, [], "empty file"
    except Exception as e:                      # noqa: BLE001
        return 0, [], f"{type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="root of the raw deposit")
    ap.add_argument("--full", action="store_true", help="stream every row")
    ap.add_argument("--quiet", action="store_true", help="only print problems")
    a = ap.parse_args()
    root = Path(a.data).resolve()
    if not root.is_dir():
        sys.exit(f"not a directory: {root}")

    print(f"raw root: {root}")
    print(f"mode    : {'full scan' if a.full else 'header + first 1000 rows'}\n")

    problems, totals = [], []
    for kind in KINDS:
        files = data_files(root, kind["globs"], kind["exts"])
        if not files:
            problems.append(f"{kind['name']}: no files matched {kind['globs']}")
            print(f"  [ABSENT]  {kind['name']}")
            continue
        nrows = nbytes = 0
        for p in files:
            rows, probs, err = check_file(p, kind["must"], kind["any_of"], a.full)
            nrows += rows
            nbytes += p.stat().st_size
            rel = p.relative_to(root)
            if err:
                problems.append(f"{rel}: {err}")
                print(f"  [ERROR]   {rel}: {err}")
            elif probs:
                problems.append(f"{rel}: missing {probs}")
                print(f"  [MISSING] {rel}: {probs}")
            elif not a.quiet:
                tag = "xlsx (not parsed)" if p.suffix == ".xlsx" else \
                      (f"{rows:,} rows" if a.full else f"{rows:,}+ rows")
                print(f"  [ok]      {rel}  ({p.stat().st_size/1048576:.0f} MB, {tag})")
        totals.append((kind["name"], len(files), nbytes, nrows))

    print("\n" + "=" * 70)
    print(f"{'kind':<20}{'files':>8}{'size':>14}{'rows':>16}")
    for name, nf, nb, nr in totals:
        rows = f"{nr:,}" if a.full else f"{nr:,}+"
        print(f"{name:<20}{nf:>8}{nb/1073741824:>11.2f} GB{rows:>16}")
    print("=" * 70)
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems[:30]:
            print("  -", p)
        sys.exit(1)
    print("\nAll files present and parseable.")


if __name__ == "__main__":
    main()
