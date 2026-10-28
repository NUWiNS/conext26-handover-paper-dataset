"""Section 4 -- reports fired versus handovers actually performed.

Produces:
    all_events_overall_vs_ho_LTE.pdf    (Fig. 2, LTE-origin)
    all_events_overall_vs_ho_5G.pdf     (Fig. 2, 5G-origin)

Inputs (processed tier, small):
    events/main_op_all_events_interface_list_{1,2,3,2024}.pkl   ~3.5 MB
    events/ho_event_counts.pkl                                  ~1 KB
        (derived; see prepare/make_event_tables.py)

Each operator gets a row: a wide panel of per-event counts, filled for all
reports and hollow for the ones that led to a handover, plus a narrow panel
carrying the row totals on its own scale. The gap between the two bars is the
signalling the network paid for without moving the UE.

Ported from parse_sigmetrics_merged.py:3454-3552.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config
import common
from common import OP_COLORS
from fig_events import SHORT_EVENT, SHORT_EVENTS, PANEL_ORDER, _by_origin


def _fmt_count(v):
    """Axis labels as whole thousands, truncated -- 1500 shows as 1K."""
    v = int(round(v))
    return f"{v // 1000}K" if v >= 1000 else str(v)


def _series(radio):
    """(all-report counts, HO counts, totals) per operator for one origin radio."""
    all_counts = common.load_events_by_interface()
    derived = common.load_pickle("events", "ho_event_counts.pkl")
    if "ho_by_origin" not in derived:
        raise RuntimeError(
            "ho_event_counts.pkl predates the origin split; regenerate it with "
            "prepare/make_event_tables.py")
    failure = derived["failure"]

    overall, ho = {}, {}
    for op in PANEL_ORDER:
        totals = _by_origin(all_counts[op][radio])
        # F is the failure bucket rather than a reported event, and it is
        # attributed to 5G only -- an LTE-origin handover cannot be counted
        # as a 5G drop. This mirrors the breakdown in Fig 7.
        totals["F"] = 0 if radio == "LTE" else failure.get(op, 0)
        overall[op] = [totals[e] for e in SHORT_EVENTS]
        ho[op] = [_by_origin(derived["ho_by_origin"][op][radio])[e]
                  for e in SHORT_EVENTS]
    return overall, ho


def _plot(radio, name):
    overall, ho = _series(radio)
    t_overall = {op: sum(overall[op]) for op in PANEL_ORDER}
    t_ho = {op: sum(ho[op]) for op in PANEL_ORDER}

    # Shared ceilings so the three operator rows stay comparable.
    ev_ceil = max(max(overall[op] + ho[op]) for op in PANEL_ORDER) or 1
    ev_ceil = int(np.ceil(ev_ceil * 1.10 / 1000) * 1000) or 1
    t_ceil = max(max(t_overall[op], t_ho[op]) for op in PANEL_ORDER) or 1
    t_ceil = int(np.ceil(t_ceil * 1.05 / 1000) * 1000) or 1

    # The script in the tree says 5.5, but the published PDF is 377.856 x
    # 274.479 pt, which only 4.0 reproduces -- the same drift seen in A5,
    # where the figure was copied into the paper before a later edit. Height
    # is pinned to the published geometry.
    fig = plt.figure(figsize=(6.0, 4.0))
    gs = fig.add_gridspec(nrows=3, ncols=2, width_ratios=[10, 2.4],
                          height_ratios=[1, 1, 1], wspace=0.22, hspace=0.32)
    x = np.arange(len(SHORT_EVENTS))
    w = 0.32
    mid_ax = None

    for i, op in enumerate(PANEL_ORDER):
        ax_ev = fig.add_subplot(gs[i, 0])
        ax_t = fig.add_subplot(gs[i, 1])
        c = OP_COLORS[op]

        ax_ev.bar(x - w / 2, overall[op], w, facecolor=c, edgecolor=c)
        ax_ev.bar(x + w / 2, ho[op], w, facecolor="none", edgecolor=c,
                  linewidth=2)
        ax_ev.set_xticks(x)
        ax_ev.set_xticklabels(SHORT_EVENTS if i == 2 else [],
                              rotation=45, fontsize=11)
        ax_ev.set_ylim(0, ev_ceil)
        ax_ev.set_yticks([0, ev_ceil / 2, ev_ceil])
        ax_ev.set_yticklabels([_fmt_count(v) for v in (0, ev_ceil / 2, ev_ceil)],
                              fontsize=10)
        ax_ev.grid(True, axis="y", alpha=0.35, linewidth=0.5)
        ax_ev.set_axisbelow(True)
        ax_ev.set_title(op, fontsize=11, fontweight="bold", color=c,
                        loc="left", pad=4)

        ax_t.bar(0, t_overall[op], 0.55, facecolor=c, edgecolor=c)
        ax_t.bar(1, t_ho[op], 0.55, facecolor="none", edgecolor=c, linewidth=2)
        ax_t.set_xticks([0.5])
        ax_t.set_xticklabels(["Total"] if i == 2 else [], fontsize=11,
                             fontweight="bold")
        ax_t.set_xlim(-0.7, 1.7)
        ax_t.set_ylim(0, t_ceil)
        ax_t.set_yticks([0, t_ceil / 2, t_ceil])
        ax_t.set_yticklabels([_fmt_count(v) for v in (0, t_ceil / 2, t_ceil)],
                             fontsize=9, rotation=45)
        ax_t.grid(True, axis="y", alpha=0.35, linewidth=0.5)
        ax_t.set_axisbelow(True)

        if i == 1:
            mid_ax = ax_ev

    if mid_ax is not None:
        handles = [
            plt.Rectangle((0, 0), 1, 1, facecolor="#666", edgecolor="#666",
                          label="Overall"),
            plt.Rectangle((0, 0), 1, 1, facecolor="none", edgecolor="#666",
                          linewidth=2, label="Active HO"),
        ]
        mid_ax.legend(handles=handles, loc="upper right", fontsize=11,
                      framealpha=0.9)

    p = config.out(name)
    plt.savefig(p, bbox_inches="tight")
    plt.close()
    return p


def plot_overall_vs_ho_lte():
    return _plot("LTE", "all_events_overall_vs_ho_LTE.pdf")


def plot_overall_vs_ho_5g():
    return _plot("5G", "all_events_overall_vs_ho_5G.pdf")


FIGURES = {
    "all_events_overall_vs_ho_LTE.pdf": plot_overall_vs_ho_lte,
    "all_events_overall_vs_ho_5G.pdf": plot_overall_vs_ho_5g,
}

if __name__ == "__main__":
    for name, fn in FIGURES.items():
        print("wrote", fn())
