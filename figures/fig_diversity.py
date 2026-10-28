"""Section 5.1 -- diversity of HO configuration parameters.

Produces:
    richness_overall.pdf          (Fig. Richness of HO configuration parameters)
    richness_comp_2022_2024.pdf   (Fig. Richness comparison, R(2024) - R(2022))

Inputs:
    aggressiveness/op_metric_selected_dict.pkl   ~49 MB   (small tier)
    diversity/overall_{2022,2024}.pkl            ~44 KB   (small tier)

Richness R is simply the number of distinct values an operator uses for a
given (event, parameter) pair, so both figures reduce to counting distinct
values and differencing them across campaigns.

Ported from parse_sigmetrics_diversity_merged.py. In the original, the
richness figure sat ~1,250 lines inside extract_measurement_report_data(),
recomputing the per-operator metric dictionary from the four
measurement_report_data.pkl files each run. That dictionary is already
deposited as op_metric_selected_dict.pkl, so this module reads it directly:
same numbers, a fraction of the inputs, and the figure moves from the medium
tier to the small one.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config
import common

# Plot order and colours as published; T-Mobile is violet in these two
# figures rather than the magenta common.OP_COLORS uses elsewhere.
PLOT_ORDER = ["Verizon", "AT&T", "T-Mobile"]
DIV_COLORS = {"AT&T": "deepskyblue", "T-Mobile": "violet", "Verizon": "red"}

EVENTS = ["A1", "A2", "A3", "A4", "A5", "A6", "B1", "B2", "Periodic"]

# Parameters each event is expected to carry, used to emit placeholder bars
# where an operator never configures that event on a given RAT.
DEFAULT_FIELDS = {
    "A1": ["hysteresis", "threshold", "time to trigger"],
    "A2": ["hysteresis", "threshold", "time to trigger"],
    "A3": ["hysteresis", "offset", "time to trigger"],
    "A4": ["hysteresis", "threshold neighbor", "time to trigger"],
    "A5": ["hysteresis", "threshold", "threshold neighbor", "time to trigger"],
    "A6": ["hysteresis", "offset", "time to trigger"],
    "B1": ["hysteresis", "threshold neighbor", "time to trigger"],
    "B2": ["threshold", "threshold neighbor", "hysteresis", "time to trigger"],
    "Periodic": ["hysteresis", "time to trigger"],
}

# The paper labels the x axis by parameter index rather than by name. Fields
# are numbered alphabetically WITHIN each event, which is not the order
# DEFAULT_FIELDS lists them in for B2 -- numbering that list as written would
# shift indices 23-25 and silently relabel the published x axis.
PARAM_INDEX = {
    f"{ev} {field}": i + 1
    for i, (ev, field) in enumerate(
        (ev, f) for ev in EVENTS for f in sorted(DEFAULT_FIELDS[ev])
    )
}

# Descriptive columns carried alongside the configuration parameters; they are
# context, not parameters, so they are excluded from the richness count.
EXCLUDED = ("modified_tech", "timezone", "road", "sa_nsa", "trigger_quantity")

# richness() in the original: the number of distinct values.
_richness = lambda values: len(set(values))


def _richness_table(per_op):
    """{operator: {event: {parameter: R}}} from a metric-selection dict."""
    out = {}
    for op in PLOT_ORDER:
        out[op] = {}
        for ev in EVENTS:
            out[op][ev] = {}
            if ev not in per_op.get(op, {}):
                continue
            for metric, values in per_op[op][ev].items():
                if any(tok in metric for tok in EXCLUDED):
                    continue
                out[op][ev][metric.replace("_", " ")] = _richness(values)
    return out


def _bars(table, filler):
    """Flatten {event: {param: value}} into label-sorted bar lists.

    Events an operator never configures are filled with `filler` so every
    operator contributes the same number of bars and the groups stay aligned.
    """
    labels, lengths = [], []
    for ev in EVENTS:
        row = table[ev] or {f: filler for f in DEFAULT_FIELDS[ev]}
        for field, value in row.items():
            labels.append(f"{ev} {field}")
            lengths.append(value)
    order = sorted(range(len(labels)), key=lambda i: labels[i])
    return [labels[i] for i in order], [lengths[i] for i in order]


def plot_richness_overall():
    """Distinct configured values per event parameter, LTE and 5G."""
    lte_raw, nr_raw = common.load_pickle(
        "aggressiveness", "op_metric_selected_dict.pkl")
    lte, nr = _richness_table(lte_raw), _richness_table(nr_raw)

    fig, ax = plt.subplots(2, figsize=(25, 8), sharey=True)
    width = 0.3

    for i, op in enumerate(PLOT_ORDER):
        lte_labels, lte_vals = _bars(lte[op], 0)
        nr_labels, nr_vals = _bars(nr[op], 0)
        off = width * i
        ax[0].bar(np.arange(len(lte_vals)) + off, lte_vals, width=width,
                  color=DIV_COLORS[op])
        ax[1].bar(np.arange(len(nr_vals)) + off, nr_vals, width=width,
                  color=DIV_COLORS[op], label=op)

    ax[0].set_ylabel("$R_{LTE}$", fontsize=30)
    ax[1].set_ylabel("$R_{5G}$", fontsize=30)
    ax[1].legend(fontsize=22, loc="upper right")
    for a, labels in ((ax[0], lte_labels), (ax[1], nr_labels)):
        a.set_xticks(np.arange(len(labels)) + width,
                     [f"{PARAM_INDEX[l]}: {l}" for l in labels])
        a.tick_params(axis="y", labelsize=22)
        a.set_yticks([0, 20, 40, 60])
        a.grid(True)
    ax[1].tick_params(axis="x", rotation=55, labelsize=22)
    ax[0].set_xticklabels([""] * len(lte_labels))
    ax[0].set_ylim(0, 60)
    plt.setp(ax[1].xaxis.get_majorticklabels(), ha="right")

    plt.tight_layout()
    p = config.out("richness_overall.pdf")
    plt.savefig(p)
    plt.close()
    return p


def plot_richness_delta():
    """Change in richness between the 2022 and 2024 campaigns."""
    (_, _, rich_lte_22, _), (_, _, rich_nr_22, _) = common.load_pickle(
        "diversity", "overall_2022.pkl")
    (_, _, rich_lte_24, _), (_, _, rich_nr_24, _) = common.load_pickle(
        "diversity", "overall_2024.pkl")

    def delta(new, old):
        out = {}
        for op in PLOT_ORDER:
            out[op] = {}
            for ev in EVENTS:
                out[op][ev] = {}
                for metric, value in new.get(op, {}).get(ev, {}).items():
                    try:
                        out[op][ev][metric] = value - old[op][ev][metric]
                    except KeyError:
                        # configured in 2024 but not 2022 (or vice versa):
                        # the published figure marks the whole event N/A
                        out[op][ev] = {}
                        break
        return out

    d_lte, d_nr = delta(rich_lte_24, rich_lte_22), delta(rich_nr_24, rich_nr_22)

    fig, ax = plt.subplots(2, figsize=(14, 6))
    width = 0.2
    MISSING = -99
    na_lte, na_nr = {}, {}

    for i, op in enumerate(PLOT_ORDER):
        lte_labels, lte_vals = _bars(d_lte[op], MISSING)
        nr_labels, nr_vals = _bars(d_nr[op], MISSING)
        na_lte[op] = [v == MISSING for v in lte_vals]
        na_nr[op] = [v == MISSING for v in nr_vals]
        off = width * i
        lte_bars = ax[0].bar(np.arange(len(lte_vals)) + off,
                             [0 if v == MISSING else v for v in lte_vals],
                             width=width, color=DIV_COLORS[op], label=op)
        nr_bars = ax[1].bar(np.arange(len(nr_vals)) + off,
                            [0 if v == MISSING else v for v in nr_vals],
                            width=width, color=DIV_COLORS[op])

    # "N/A" is annotated only where no operator configured the parameter.
    for a, bars, flags in ((ax[0], lte_bars, na_lte), (ax[1], nr_bars, na_nr)):
        all_missing = [all(flags[op][i] for op in PLOT_ORDER)
                       for i in range(len(bars))]
        for bar, missing in zip(bars, all_missing):
            if missing:
                a.annotate("N/A",
                           xy=(bar.get_x() - bar.get_width() / 2, bar.get_height()),
                           xytext=(0, 3), textcoords="offset points",
                           ha="center", va="bottom", fontsize=15)

    ax[0].set_ylabel("$\\Delta R$ (LTE)", fontsize=25)
    ax[1].set_ylabel("$\\Delta R$ (5G)", fontsize=25)
    ax[0].legend(fontsize=24, loc="lower right")
    for a, labels in ((ax[0], lte_labels), (ax[1], nr_labels)):
        a.axhline(0, color="black", lw=1)
        a.set_xticks(np.arange(len(labels)) + width,
                     [str(PARAM_INDEX[l]) for l in labels])
        a.tick_params(axis="y", labelsize=22)
        a.grid(True)
    ax[1].tick_params(axis="x", rotation=45, labelsize=22)
    ax[0].set_xticklabels([""] * len(lte_labels))
    ax[1].set_xlabel("Parameter index", fontsize=28)

    plt.tight_layout()
    p = config.out("richness_comp_2022_2024.pdf")
    plt.savefig(p)
    plt.close()
    return p


FIGURES = {
    "richness_overall.pdf": plot_richness_overall,
    "richness_comp_2022_2024.pdf": plot_richness_delta,
}

if __name__ == "__main__":
    for name, fn in FIGURES.items():
        print("wrote", fn())
