"""Shared helpers: operator naming, event relabelling, colours, loaders.

Extracted from the analysis pipeline used to produce the paper so that the
figure scripts stay small and share one definition of each convention.
"""
import pickle as pkl
from collections import Counter

import config

# ---------------------------------------------------------------- operators
OPS = ["AT&T", "T-Mobile", "Verizon"]

# raw operator keys appearing in the pickles -> display name
OP_DICT = {
    "verizon": "Verizon", "Verizon": "Verizon",
    "tmobile": "T-Mobile", "T-Mobile": "T-Mobile",
    "atnt": "AT&T", "AT&T": "AT&T",
}

OP_COLORS = {"Verizon": "red", "AT&T": "deepskyblue", "T-Mobile": "magenta"}

# aggressiveness classes (shared with the paper's colour key)
CLS_COLOR = {
    "aggressive": "#d62728",
    "moderate": "#ff7f0e",
    "conservative": "#2ca02c",
}

# events kept in the per-technology breakdowns; these three raw keys are
# folded into a single "F" (failure) bucket, and these are dropped entirely.
IGNORE_EVENTS = {"Unknown", "reportCGI", "periodical"}
FAILURE_KEYS = ["5G\ndropped", "LTE HO\n5G drop", "SCG\nFailure"]


def mod_ho_label(ho_type):
    """Normalise a raw HO/event label to the canonical event name.

    This is the labelling used throughout the paper; keep it in sync with
    the parsing pipeline in the raw-data bundle.
    """
    ho_type = ho_type.strip().replace("nan ", "")
    if "reportStrongestCells" in ho_type and "+" not in ho_type:
        ho_type = "Periodic"
    if "Unknown" in ho_type or "unknown" in ho_type:
        ho_type = "Unknown"
    if "Handover Success + 5G switch" in ho_type:
        ho_type = "LTE HO\n5G drop"
    if "A6" in ho_type:
        ho_type = "eventA6"
    if "ulInformationTransferMRDC-r15 + A2" in ho_type:
        ho_type = "eventA2"
    if "scgFailureInformationNR" in ho_type:
        ho_type = "SCG\nFailure"
    if "+" in ho_type and ho_type not in (
        "Handover Success + 5G switch",
        "ulInformationTransferMRDC-r15 + A2",
    ):
        ho_type = "5G\ndropped"
    if ho_type == "eventB1_NR_r15":
        ho_type = "eventB1"
    return ho_type


def load_pickle(*parts):
    with open(config.data(*parts), "rb") as fh:
        return pkl.load(fh)


# ------------------------------------------------------- per-trip event data
# The four measurement campaigns, in chronological order.
TRIPS = ["1", "2", "3", "2024"]


def load_events_by_interface():
    """Merge the per-trip reporting-event lists, split by LTE / 5G.

    Returns {operator: {"LTE": Counter, "5G": Counter}} of event counts.
    """
    merged = {}
    for tag in TRIPS:
        d = load_pickle("events", f"main_op_all_events_interface_list_{tag}.pkl")
        for op_raw, per_rat in d.items():
            op = OP_DICT.get(op_raw)
            if op is None:          # "(Searching)", "No service", ...
                continue
            slot = merged.setdefault(op, {"LTE": [], "5G": []})
            slot["LTE"].extend(per_rat["LTE"])
            slot["5G"].extend(per_rat["5G"])
    return {
        op: {rat: Counter(mod_ho_label(x) for x in lst)
             for rat, lst in per_rat.items()}
        for op, per_rat in merged.items()
    }


def event_universe(counts):
    """Sorted event names present in any operator/RAT, minus ignored ones."""
    seen = set()
    for per_rat in counts.values():
        for c in per_rat.values():
            seen |= set(c)
    return sorted(seen - IGNORE_EVENTS)


def pretty_event(name):
    return name.replace("event", "").replace("\n", " ")
