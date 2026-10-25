"""Derive the small event-count tables used by figures/fig_events.py.

Reads the large HO-classification pickle from the *full* tier of the dataset
and writes a few-kilobyte summary so that reviewers reproducing the event
figures do not need the multi-gigabyte input.

    python prepare/make_event_tables.py \
        --ho-dump /path/to/dump_all_imcs_mod_merged.pkl \
        --out     /path/to/processed/events/ho_event_counts.pkl
"""
import argparse
import pickle as pkl
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "figures"))
from common import FAILURE_KEYS, OPS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ho-dump", required=True,
                    help="dump_all_imcs_mod_merged.pkl (full tier)")
    ap.add_argument("--out", required=True, help="output .pkl path")
    a = ap.parse_args()

    with open(a.ho_dump, "rb") as fh:
        blob = pkl.load(fh)
    ho_classification = blob[0]          # main_op_ho_classification_list

    # events that actually triggered a HO, per operator
    ho_events = {}
    for op, per_ho in ho_classification.items():
        c = Counter()
        for ev_list in per_ho.values():
            for raw in ev_list:
                c[raw.strip().replace("nan ", "")] += 1
        ho_events[op] = c

    # the "F" bucket: SCG failure + 5G drop + LTE-HO-with-5G-drop
    failure = {op: sum(ho_events[op].get(k, 0) for k in FAILURE_KEYS)
               for op in ho_events}

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as fh:
        pkl.dump({"ho_events": ho_events, "failure": failure}, fh, protocol=4)

    print(f"wrote {out} ({out.stat().st_size/1024:.1f} KB)")
    for op in OPS:
        print(f"  {op:<10} HO-triggering events={sum(ho_events.get(op, {}).values()):>7}"
              f"  F={failure.get(op, 0)}")


if __name__ == "__main__":
    main()
