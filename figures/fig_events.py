"""Section 4 -- HO reporting events: diversity and signalling overhead.

Produces:
    all_events_break_tech_mod_normalized.pdf   (Fig. normalised triggered events)
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
from common import OPS, OP_COLORS


def _normalised_shares():
    """Per-operator share of each event within its own technology total.

    The denominator includes the failure ("F") bucket, matching the
    normalisation used for the figure in the paper.
    """
    counts = common.load_events_by_interface()
    events = common.event_universe(counts)
    derived = common.load_pickle("events", "ho_event_counts.pkl")
    failure = derived["failure"]

    shares = {}
    for op in OPS:
        row = {}
        for rat in ("LTE", "5G"):
            c = counts[op][rat]
            # the F bar is prepended to the 5G series only
            extra = failure.get(op, 0) if rat == "5G" else 0
            total = extra + sum(c.get(e, 0) for e in events)
            row[rat] = {e: 100.0 * c.get(e, 0) / total for e in events} if total else {}
        shares[op] = row
    return events, shares


def plot_normalised_events():
    events, shares = _normalised_shares()
    x = np.arange(len(events))
    width = 0.3

    fig, ax = plt.subplots(3, 1, figsize=(4, 6))
    for i, op in enumerate(OPS):
        color = OP_COLORS[op]
        lte = [shares[op]["LTE"].get(e, 0) for e in events]
        fiveg = [shares[op]["5G"].get(e, 0) for e in events]
        ax[i].bar(x - width / 2, lte, width, label=f"{op} LTE",
                  facecolor=color, edgecolor=color)
        ax[i].bar(x + width / 2, fiveg, width, label=f"{op} 5G",
                  facecolor="none", edgecolor=color, linewidth=2)
        ax[i].set_ylim(0, 100)
        ax[i].set_yticks([0, 25, 50, 75, 100])
        ax[i].set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
        ax[i].grid(True, axis="y")
        ax[i].legend(loc="upper right")
        if i == len(OPS) - 1:
            ax[i].set_xticks(x)
            ax[i].set_xticklabels([common.pretty_event(e) for e in events], rotation=45)
        else:
            ax[i].set_xticks([])
    plt.tight_layout()
    p = config.out("all_events_break_tech_mod_normalized.pdf")
    plt.savefig(p)
    plt.close()
    return p


def plot_event_conversion():
    """Per-event conversion rate: HO-triggering reports / all reports."""
    counts = common.load_events_by_interface()
    events = common.event_universe(counts)
    derived = common.load_pickle("events", "ho_event_counts.pkl")
    ho_events = derived["ho_events"]

    x = np.arange(len(events))
    width = 0.26
    fig, ax = plt.subplots(figsize=(7, 3))
    for i, op in enumerate(OPS):
        tot = {e: counts[op]["LTE"].get(e, 0) + counts[op]["5G"].get(e, 0)
               for e in events}
        conv = [100.0 * ho_events.get(op, {}).get(e, 0) / tot[e] if tot[e] else 0
                for e in events]
        ax.bar(x + (i - 1) * width, conv, width, label=op,
               facecolor=OP_COLORS[op], edgecolor=OP_COLORS[op])
    ax.set_xticks(x)
    ax.set_xticklabels([common.pretty_event(e) for e in events], rotation=45)
    ax.set_ylabel("Reports leading to a HO (%)")
    ax.grid(True, axis="y")
    ax.legend()
    plt.tight_layout()
    p = config.out("ho_event_overhead_pct_by_event.pdf")
    plt.savefig(p)
    plt.close()
    return p


FIGURES = {
    "all_events_break_tech_mod_normalized.pdf": plot_normalised_events,
    "ho_event_overhead_pct_by_event.pdf": plot_event_conversion,
}

if __name__ == "__main__":
    for name, fn in FIGURES.items():
        print("wrote", fn())
