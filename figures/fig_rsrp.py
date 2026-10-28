"""Section 3 -- overall signal quality across operators and technologies.

Produces:
    rsrp_rsrq_subplots.pdf        (Fig. RSRP/RSRQ distributions)
    rsrq_dist_basic.pdf           (RSRQ CDFs, LTE and 5G)
    rsrp_rsrq_percentiles.csv     (the P25/P50/P75 table printed in the text)

Inputs (processed tier, medium):
    rsrp/rsrp_freq_dict_{1,2,3,2024}.pkl        ~1.1 GB

Each pickle is {operator: [DataFrame, ...]}, one frame per measurement run,
already trimmed to the signal columns.

Two quirks of the inputs are handled explicitly rather than by position:

* The 2024 campaign spells the LTE columns with a space before the unit
  ("... RSRP [dBm]") where the earlier three do not ("... RSRP[dBm]"), so
  every column is looked up through a candidate list.
* The 2022 campaign carries no RSRQ columns at all, and its dict has extra
  keys ("(Searching)", "No service") that are UE radio states rather than
  operators. Both are skipped rather than special-cased per trip.
"""
import csv

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

import config
import common
from common import OPS, OP_COLORS

TRIPS = ["1", "2", "3", "2024"]

# The published figure orders the boxes T-Mobile, AT&T, Verizon and uses a
# paler plum for T-Mobile than common.OP_COLORS does. Both are kept local to
# this module so the regenerated figure sits beside the paper's without a
# reviewer having to wonder whether the data differs too.
BOX_ORDER = ["T-Mobile", "AT&T", "Verizon"]
BOX_COLORS = {"T-Mobile": "plum", "AT&T": "deepskyblue", "Verizon": "red"}

# Column spellings differ between campaigns; first match wins.
LTE_RSRP = ["LTE KPI PCell Serving RSRP[dBm]", "LTE KPI PCell Serving RSRP [dBm]"]
NR_RSRP = ["5G KPI PCell RF Serving SS-RSRP [dBm]", "5G KPI PCell RF Serving SS-RSRP[dBm]"]
LTE_RSRQ = ["LTE KPI PCell Serving RSRQ[dB]", "LTE KPI PCell Serving RSRQ [dB]"]
NR_RSRQ = ["5G KPI PCell RF Serving SS-RSRQ [dB]", "5G KPI PCell RF Serving SS-RSRQ[dB]"]

_CACHE = None


def _first_present(df, candidates):
    """Values of the first candidate column present, NaNs dropped."""
    for c in candidates:
        if c in df.columns:
            return df[c].dropna().tolist()
    return []


def _collect():
    """{metric: {radio: {operator: [values]}}} across all four campaigns.

    Memoised: both figures and the percentile table need the same ~1.1 GB of
    pickles, and reading them once keeps the module usable on a laptop.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    out = {m: {r: {op: [] for op in OPS} for r in ("LTE", "5G")}
           for m in ("RSRP", "RSRQ")}
    wanted = {
        ("RSRP", "LTE"): LTE_RSRP, ("RSRP", "5G"): NR_RSRP,
        ("RSRQ", "LTE"): LTE_RSRQ, ("RSRQ", "5G"): NR_RSRQ,
    }

    for tag in TRIPS:
        per_op = common.load_pickle("rsrp", f"rsrp_freq_dict_{tag}.pkl")
        for op_raw, frames in per_op.items():
            op = common.OP_DICT.get(op_raw)
            if op is None:        # "(Searching)", "No service"
                continue
            for df in frames:
                for (metric, radio), cands in wanted.items():
                    out[metric][radio][op].extend(_first_present(df, cands))
        del per_op

    _CACHE = out
    return out


def plot_rsrq_cdf():
    """RSRQ CDFs, LTE and 5G side by side."""
    data = _collect()["RSRQ"]
    fig, ax = plt.subplots(1, 2, figsize=(8, 4))

    for i, radio in enumerate(("LTE", "5G")):
        for op in OPS:
            vals = np.sort(np.asarray(data[radio][op], dtype=float))
            vals = vals[~np.isnan(vals)]
            if vals.size:
                ax[i].plot(vals, np.linspace(0, 1, vals.size),
                           color=OP_COLORS[op], label=op)
        ax[i].set_xlabel("RSRQ (dB)", fontsize=20)
        ax[i].set_xlim(-25, 0)
        ax[i].set_ylim(0, 1)
        ax[i].grid()
        ax[i].tick_params(axis="both", labelsize=17)

    ax[0].set_ylabel("CDF", fontsize=25)
    ax[0].set_title("LTE", fontweight="bold", fontsize=23)
    ax[1].set_title("5G", fontweight="bold", fontsize=23)
    ax[0].legend(loc="best", fontsize=17)

    plt.tight_layout()
    p = config.out("rsrq_dist_basic.pdf")
    plt.savefig(p)
    plt.close()
    return p


def plot_rsrp_rsrq_box():
    """Boxplots of RSRP and RSRQ, grouped by radio and split by operator."""
    data = _collect()
    box_w = 0.12
    centers = {"LTE": 0.0, "5G": 1.0}
    offsets = [(i - (len(BOX_ORDER) - 1) / 2) * box_w
               for i in range(len(BOX_ORDER))]

    fig, axes = plt.subplots(1, 2, figsize=(5, 4), sharey=False)
    # y-limits as published; the RSRQ panel is clipped tighter than the
    # full data range so the inter-operator differences stay legible.
    specs = [("RSRP (dBm)", "RSRP", (-120, -60)), ("RSRQ (dB)", "RSRQ", (-20, -6))]

    for ax, (title, metric, ylim) in zip(axes, specs):
        for radio in ("LTE", "5G"):
            series = [data[metric][radio][op] for op in BOX_ORDER]
            if not any(series):
                continue
            bp = ax.boxplot(series,
                            positions=[centers[radio] + o for o in offsets],
                            widths=box_w * 0.9, patch_artist=True,
                            showfliers=False, whis=[5, 95],
                            medianprops=dict(color="black", linewidth=1.4))
            for patch, op in zip(bp["boxes"], BOX_ORDER):
                patch.set_facecolor(BOX_COLORS[op])
                patch.set_edgecolor("none")
                patch.set_alpha(0.85)

        ax.set_xticks(list(centers.values()))
        ax.set_xticklabels(list(centers), fontsize=18, fontweight="bold")
        ax.set_xlim(-0.5, 1.5)
        ax.set_title(title, fontsize=15, fontweight="bold")
        ax.set_ylim(ylim)
        ax.tick_params(axis="y", labelsize=10)
        ax.set_axisbelow(True)
        ax.grid(True, axis="y", alpha=0.4)

    handles = [mpatches.Patch(facecolor=BOX_COLORS[op], edgecolor="none", label=op)
               for op in BOX_ORDER]
    fig.legend(handles=handles, loc="lower center", ncol=len(BOX_ORDER),
               fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.subplots_adjust(bottom=0.22)

    p = config.out("rsrp_rsrq_subplots.pdf")
    fig.savefig(p)
    plt.close(fig)
    return p


def write_percentiles():
    """P25/P50/P75 per operator and radio, for the numbers quoted in the text."""
    data = _collect()
    p = config.out("rsrp_rsrq_percentiles.csv")
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["metric", "operator", "technology", "n", "p25", "p50", "p75"])
        for metric in ("RSRP", "RSRQ"):
            for op in OPS:
                for radio in ("LTE", "5G"):
                    arr = np.asarray(data[metric][radio][op], dtype=float)
                    arr = arr[~np.isnan(arr)]
                    if arr.size == 0:
                        w.writerow([metric, op, radio, 0, "", "", ""])
                        continue
                    q = np.percentile(arr, [25, 50, 75])
                    w.writerow([metric, op, radio, arr.size,
                                f"{q[0]:.2f}", f"{q[1]:.2f}", f"{q[2]:.2f}"])
    return p


FIGURES = {
    "rsrp_rsrq_subplots.pdf": plot_rsrp_rsrq_box,
    "rsrq_dist_basic.pdf": plot_rsrq_cdf,
    "rsrp_rsrq_percentiles.csv": write_percentiles,
}

if __name__ == "__main__":
    for name, fn in FIGURES.items():
        print("wrote", fn())
