"""Section 4 -- HO reporting events: diversity and signalling overhead.

Produces:
    ho_event_overhead_pct_by_event.pdf         (per-event conversion rate)

Inputs (processed tier):
    events/main_op_all_events_interface_list_{1,2,3,2024}.pkl   ~3.5 MB
    events/ho_event_counts.pkl                                  ~20 KB
        (derived; see prepare/make_event_tables.py)
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config
import common
from common import OP_COLORS


SHORT_EVENT = {
    "eventA1": "A1", "eventA2": "A2", "eventA3": "A3", "eventA4": "A4",
    "eventA5": "A5", "eventA6": "A6", "eventB1": "B1", "eventB2": "B2",
    "Periodic": "P",
    "5G\ndropped": "F", "LTE HO\n5G drop": "F", "SCG\nFailure": "F",
}
SHORT_EVENTS = ["F", "P", "A1", "A2", "A3", "A4", "A5", "A6", "B1", "B2"]
PANEL_ORDER = ["AT&T", "Verizon", "T-Mobile"]


def _by_origin(counter_for_radio):
    """Fold raw event labels into the paper's short codes."""
    out = {e: 0 for e in SHORT_EVENTS}
    for raw, n in counter_for_radio.items():
        short = SHORT_EVENT.get(raw)
        if short is not None:
            out[short] += n
    return out


def plot_event_conversion():
    """Share of reports that led to a HO, per event and origin radio.

    One panel per operator; within each, filled bars are handovers that
    started on LTE and hollow bars those that started on 5G. The ratio is
    HO-triggering reports over all reports of that event on that radio, so
    it answers "how often does this event actually move the UE".
    """
    all_counts = common.load_events_by_interface()
    derived = common.load_pickle("events", "ho_event_counts.pkl")
    if "ho_by_origin" not in derived:
        raise RuntimeError(
            "ho_event_counts.pkl predates the origin split; regenerate it with "
            "prepare/make_event_tables.py")
    ho_by_origin = derived["ho_by_origin"]

    overhead = {}
    for op in PANEL_ORDER:
        overhead[op] = {}
        for radio in ("LTE", "5G"):
            ho = _by_origin(ho_by_origin[op][radio])
            total = _by_origin(all_counts[op][radio])
            overhead[op][radio] = {
                e: (100.0 * ho[e] / total[e]) if total[e] else 0.0
                for e in SHORT_EVENTS
            }

    fig, ax = plt.subplots(3, 1, figsize=(4.5, 4.2))
    x = np.arange(len(SHORT_EVENTS))
    w = 0.3
    for i, op in enumerate(PANEL_ORDER):
        c = OP_COLORS[op]
        ax[i].bar(x - w / 2, [overhead[op]["LTE"][e] for e in SHORT_EVENTS], w,
                  label=f"{op} LTE", facecolor=c, edgecolor=c)
        ax[i].bar(x + w / 2, [overhead[op]["5G"][e] for e in SHORT_EVENTS], w,
                  label=f"{op} 5G", facecolor="none", edgecolor=c, linewidth=2)
        ax[i].set_xticks(x)
        ax[i].set_xticklabels(SHORT_EVENTS, rotation=45)
        ax[i].set_ylim(0, 80)
        ax[i].grid(True)
        ax[i].set_axisbelow(True)
        ax[i].legend(loc="upper left", fontsize=10)
        if i != len(PANEL_ORDER) - 1:
            ax[i].tick_params(axis="x", labelbottom=False)

    fig.text(-0.05, 0.5, "HO /All events (%)", va="center",
             rotation="vertical", fontsize=15)
    plt.tight_layout()
    p = config.out("ho_event_overhead_pct_by_event.pdf")
    plt.savefig(p)
    plt.close()
    return p


FIGURES = {
    "ho_event_overhead_pct_by_event.pdf": plot_event_conversion,
}

if __name__ == "__main__":
    for name, fn in FIGURES.items():
        print("wrote", fn())
