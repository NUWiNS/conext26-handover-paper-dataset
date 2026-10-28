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

    # Same counts, but split by the ORIGIN radio of the handover: the first
    # half of an "X->Y" transition key. Figs 2 and 3 compare HOs that started
    # on LTE against those that started on 5G, which the flattened table above
    # cannot answer. Transition keys carry technology detail (NSA/SA and band),
    # so the origin is taken as "5G" when the left side mentions 5G at all.
    ho_by_origin = {}
    for op, per_ho in ho_classification.items():
        slot = {"LTE": Counter(), "5G": Counter()}
        for transition, ev_list in per_ho.items():
            origin = "5G" if "5G" in transition.split("->")[0] else "LTE"
            for raw in ev_list:
                slot[origin][raw.strip().replace("nan ", "")] += 1
        ho_by_origin[op] = slot

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as fh:
        pkl.dump({"ho_events": ho_events, "failure": failure,
                  "ho_by_origin": ho_by_origin}, fh, protocol=4)

    print(f"wrote {out} ({out.stat().st_size/1024:.1f} KB)")
    for op in OPS:
        by_o = ho_by_origin.get(op, {})
        print(f"  {op:<10} HO-triggering events={sum(ho_events.get(op, {}).values()):>7}"
              f"  F={failure.get(op, 0):>5}"
              f"  LTE-origin={sum(by_o.get('LTE', {}).values()):>7}"
              f"  5G-origin={sum(by_o.get('5G', {}).values()):>7}")


if __name__ == "__main__":
    main()
