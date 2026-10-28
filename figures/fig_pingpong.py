"""Section 6 -- ping-pong handovers and the configurations behind them.

Produces:
    a3_ping_pong_distribution_15s.pdf          5G->5G ping-pongs, per operator
    a3_ping_pong_distribution_params_15s.pdf   ... split by (offset+hyst, TTT)
    a5_ping_pong_distribution_params_15s.pdf   T-Mobile A5, by (thresholds, TTT)
    b1_ping_pong_distribution_15s.pdf          LTE<->5G ping-pongs, per operator

Inputs (processed tier, full):
    handover/ping_pong_data.pkl                ~19 MB

A ping-pong is a handover that reverses within 15 seconds: the UE returns to
the cell it just left, on the same frequency. The fractions are reported
against the number of handovers triggered by the relevant event, so each one
answers "of the HOs this event caused, how many bounced straight back".

Ported from parse_sigmetrics_merged.py (lines 1084-1686), where the block was
parked behind `if 0:`.

NOTE ON REPRODUCIBILITY: the denominators and the "90% combination" lists
below are hardcoded in the original rather than derived here, and they are
reproduced verbatim so the regenerated figures match the published ones. They
come from the configuration-share analysis over the full handover tables
(main_op_ho_info_list_*.pkl); this module does not recompute them, so editing
the inputs will not change them. See DERIVED_CONSTANTS below.
"""
import math
import re

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config
import common

# Bar order is positional in the published figures and matches the key order
# in ping_pong_data.pkl; naming it explicitly keeps the colours correct
# regardless of how the pickle happens to iterate.
PP_ORDER = ["AT&T", "Verizon", "T-Mobile"]

# The parameter-breakdown figures use a DIFFERENT order: the original iterated
# the parameter-count dictionaries, whose literal order is AT&T, T-Mobile,
# Verizon. Using PP_ORDER there silently transposes two groups relative to the
# published figure, so the two orders are kept distinct on purpose.
PARAM_ORDER = ["AT&T", "T-Mobile", "Verizon"]

# Annotation palette, popped from the end as each parameter bar is drawn.
PARAM_COLORS = {
    "T-Mobile": ["deeppink", "magenta", "purple"],
    "Verizon": ["salmon", "red", "maroon"],
    "AT&T": ["aqua", "dodgerblue", "blue"],
}

PING_PONG_WINDOW_S = 15

# --------------------------------------------------------- DERIVED_CONSTANTS
# Counts of handovers triggered by each event, used as the denominators, and
# the parameter combinations covering ~90% of each operator's configurations.
# Hardcoded in the original; see the note in the module docstring.
OVERALL_5G_DIST = {"AT&T": 3278, "T-Mobile": 7687, "Verizon": 5809}
A3_5G_DIST = {"AT&T": 2131, "T-Mobile": 5191, "Verizon": 4916}
A5_5G_TMOBILE_DIST = 834
OVERALL_LTE_5G_DIST = {"AT&T": 3311, "T-Mobile": 2360, "Verizon": 2742}
B1_LTE_5G_DIST = {"AT&T": 3002, "T-Mobile": 1874, "Verizon": 2408}

A3_5G_PARAM_COUNT = {
    "AT&T": {(8.0, 640.0): 1971, (4.0, 320.0): 160},
    "T-Mobile": {(8.0, 640.0): 2867, (10.0, 640.0): 1796, (10.0, 320.0): 528},
    "Verizon": {(6.0, 256.0): 3809, (8.0, 256.0): 727, (8.0, 480.0): 380},
}
A5_5G_PARAM_COUNT = {
    "T-Mobile": {((-101.0, -95.0), 320.0): 292, ((-115.0, -108.0), 640.0): 117,
                 ((-31.0, -114.0), 640.0): 78, ((-117.0, -103.0), 320.0): 63},
}
B1_LTE_5G_PARAM_COUNT = {
    "AT&T": {(-121.0, 80.0): 402, (-112.0, 80.0): 1563, (-111.0, 40.0): 437},
    "T-Mobile": {(-115.0, 80.0): 483, (-112.0, 80.0): 657, (-109.0, 256.0): 409},
    "Verizon": {(-116.0, 256.0): 575, (-114.0, 256.0): 1001, (-105.0, 256.0): 246},
}

A3_90_COMBO = {
    "AT&T": [(8.0, 640.0), (4.0, 320.0)],
    "T-Mobile": [(8.0, 640.0), (10.0, 640.0), (10.0, 320.0)],
    "Verizon": [(6.0, 256.0), (8.0, 256.0), (8.0, 480.0)],
}
A5_90_COMBO = {
    "T-Mobile": [((-101.0, -95.0), 320.0), ((-115.0, -108.0), 640.0),
                 ((-31.0, -114.0), 640.0), ((-117.0, -103.0), 320.0),
                 ((-112.0, -111.0), 320.0), ((-112.0, -106.0), 320.0),
                 ((-118.0, -108.0), 640.0), ((-82.0, -106.0), 640.0),
                 ((-118.0, -111.0), 320.0), ((-118.0, -104.0), 640.0),
                 ((-110.0, -112.0), 320.0), ((-112.0, -105.0), 320.0),
                 ((-108.0, -108.0), 320.0), ((-102.0, -96.0), 320.0)],
}
B1_90_COMBO = {
    "AT&T": [(-112.0, 80.0), (-111.0, 40.0), (-121.0, 80.0),
             (-111.0, 80.0), (-120.0, 40.0), (-117.0, 80.0)],
    "T-Mobile": [(-112.0, 80.0), (-115.0, 80.0), (-109.0, 256.0),
                 (-111.0, 640.0), (-103.0, 640.0)],
    "Verizon": [(-114.0, 256.0), (-116.0, 256.0), (-105.0, 256.0),
                (-112.0, 256.0), (-107.0, 128.0), (-112.0, 1280.0),
                (-105.0, 128.0), (-111.0, 128.0), (-113.0, 1280.0),
                (-111.0, 1280.0)],
}

_CACHE = None


def _rsrp(value):
    """Normalise an RSRP threshold, which may be a level index or a dBm value."""
    try:
        v = float(value)
        return v if v < 0 else v - 156
    except (TypeError, ValueError):
        return float(re.findall(r"\d+", value)[-1])


def _key(params, *needles):
    """First parameter key containing all the needles, case-insensitively."""
    for k in params:
        low = k.lower()
        if all(n in low for n in needles):
            return k
    return None


def wilson_ci(k, n, z=1.96):
    """Wilson score interval, used for the error bars on the fraction bars."""
    p = k / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2))) / denom
    return center - half, center + half


def _analyse():
    """Walk the handover sequences and collect ping-pongs. Memoised."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    data = common.load_pickle("handover", "ping_pong_data.pkl")
    a3_hits = {op: [] for op in PP_ORDER}     # 5G->5G, A3-triggered
    a5_hits = {op: [] for op in PP_ORDER}     # 5G->5G, A5-triggered (T-Mobile)
    fiveg_pp = {op: [] for op in PP_ORDER}    # 5G->5G, any trigger
    b1_hits = {op: [] for op in PP_ORDER}     # LTE<->5G, B1-triggered
    lte_fiveg_pp = {op: [] for op in PP_ORDER}

    for op in PP_ORDER:
        hos = data[op]

        # ---- 5G -> 5G: consecutive HOs that return to the previous cell
        for i in range(1, len(hos)):
            cur, prev = hos[i], hos[i - 1]
            if not (all("5G" in p for p in cur[1].split("->"))
                    and all("5G" in p for p in prev[1].split("->"))):
                continue
            if cur[0] - prev[0] > PING_PONG_WINDOW_S:
                continue
            if not (cur[3] == prev[2] and cur[5] == prev[4]):
                continue

            entry = [cur[0], (prev[2], cur[2], cur[3]),
                     (prev[4], cur[4], cur[5]), prev[-1]]
            if fiveg_pp[op] and entry == fiveg_pp[op][-1]:
                continue      # the original skips exact repeats
            fiveg_pp[op].append(entry)

            params = prev[-1]
            if not params:
                continue
            keys = list(params)
            first_two = " ".join(keys[:2]).lower()

            if "a3" in first_two:
                ttt = float(params[_key(keys, "time", "trigger")].replace("ms", ""))
                offset = float(params[_key(keys, "offset")])
                hyst = float(params[_key(keys, "hyst")])
                combo = (offset + hyst, ttt)
                if combo in A3_90_COMBO[op]:
                    a3_hits[op].append(combo)

            elif "a5" in first_two and op == "T-Mobile":
                ttt = float(params[_key(keys, "time", "trigger")].replace("ms", ""))
                t1 = _rsrp(params[_key(keys, "threshold1")])
                t2 = _rsrp(params[_key(keys, "threshold2")])
                t1 = -t1 if t1 > 0 else t1
                t2 = -t2 if t2 > 0 else t2
                hyst = float(params[_key(keys, "hyst")])
                combo = ((t1 - hyst, t2 + hyst), ttt)
                if combo in A5_90_COMBO[op]:
                    a5_hits[op].append(combo)

        # ---- LTE -> 5G followed by 5G -> LTE back to the same 5G cell
        for i, ho in enumerate(hos):
            parts = ho[1].split("->")
            if not ("LTE" in parts[0] and "5G" in parts[1]):
                continue
            fiveg_pci = ho[3]
            for nxt in hos[i + 1:]:
                if nxt[0] - ho[0] > PING_PONG_WINDOW_S:
                    break
                nparts = nxt[1].split("->")
                if not ("5G" in nparts[0] and "LTE" in nparts[1]):
                    continue
                if nxt[2] != fiveg_pci:
                    continue

                entry = [ho[0], (ho[2], fiveg_pci), ho[-1]]
                if lte_fiveg_pp[op] and entry == lte_fiveg_pp[op][-1]:
                    continue
                lte_fiveg_pp[op].append(entry)

                params = ho[-1]
                if not params:
                    continue
                keys = list(params)
                first_two = " ".join(keys[:2]).lower()
                named_b1 = "b1" in first_two
                typed_b1 = ("trigger_type" in keys
                            and "b1" in str(params["trigger_type"]).lower())
                if not (named_b1 or typed_b1):
                    continue

                ttt = float(params[_key(keys, "time", "trigger")].replace("ms", ""))
                thr_key = _key(keys, "thresholdnr") or _key(keys, "threshold_1")
                try:
                    threshold = float(params[thr_key])
                except (TypeError, ValueError):
                    threshold = _rsrp(params[thr_key])
                    threshold = -threshold if threshold > 0 else threshold
                # A B1 named in the config carries its own hysteresis; one
                # inferred from trigger_type is a half-step and is doubled.
                hyst = float(params[_key(keys, "hyst")]) * (1 if named_b1 else 2)
                combo = (threshold + hyst, ttt)
                if combo in B1_90_COMBO[op]:
                    b1_hits[op].append(combo)

    _CACHE = {
        "a3": a3_hits, "a5": a5_hits, "b1": b1_hits,
        "fiveg_pp": fiveg_pp, "lte_fiveg_pp": lte_fiveg_pp,
        "a3_frac": {op: len(a3_hits[op]) / A3_5G_DIST[op] * 100 for op in PP_ORDER},
        "b1_frac": {op: len(b1_hits[op]) / B1_LTE_5G_DIST[op] * 100 for op in PP_ORDER},
        "a5_frac": {"T-Mobile": len(a5_hits["T-Mobile"]) / A5_5G_TMOBILE_DIST * 100},
    }
    return _CACHE


def _fraction_bars(fracs, hits, denom, name):
    """Per-operator fraction bars with Wilson CIs and sample sizes."""
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.grid(True, axis="y")
    bars = ax.bar(PP_ORDER, [fracs[op] for op in PP_ORDER],
                  color=[common.OP_COLORS[op] for op in PP_ORDER], width=0.45)

    for bar, op in zip(bars, PP_ORDER):
        lo, hi = wilson_ci(len(hits[op]), denom[op])
        ax.errorbar(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    yerr=[[bar.get_height() - lo * 100],
                          [hi * 100 - bar.get_height()]],
                    fmt="none", color="black", capsize=4, linewidth=1.5)
        ax.text(bar.get_x() + bar.get_width() / 2, hi * 100 + 0.5,
                f"N={denom[op]}", ha="center", va="bottom", fontsize=11)

    ax.set_ylabel("Fraction (%)", fontsize=19)
    ax.set_ylim(0, 32)
    ax.tick_params(axis="both", labelsize=16)
    plt.tight_layout()
    p = config.out(name)
    plt.savefig(p)
    plt.close()
    return p


def plot_a3_pingpong():
    r = _analyse()
    return _fraction_bars(r["a3_frac"], r["a3"], A3_5G_DIST,
                          "a3_ping_pong_distribution_15s.pdf")


def plot_b1_pingpong():
    r = _analyse()
    return _fraction_bars(r["b1_frac"], r["b1"], B1_LTE_5G_DIST,
                          "b1_ping_pong_distribution_15s.pdf")


def plot_a3_params():
    """A3 ping-pong rate split by (offset+hysteresis, TTT)."""
    hits = _analyse()["a3"]
    palette = {op: list(c) for op, c in PARAM_COLORS.items()}
    fig, ax = plt.subplots(figsize=(5, 4))
    width = 0.2
    x = np.arange(len(PARAM_ORDER))

    for i, op in enumerate(PARAM_ORDER):
        params = [p for p in A3_5G_PARAM_COUNT[op] if p in set(hits[op])]
        for j, param in enumerate(params):
            pct = hits[op].count(param) / A3_5G_PARAM_COUNT[op][param] * 100
            pos = x[i] + (j - len(params) / 2 + 0.2) * width
            ax.bar(pos, pct, width, color=palette[op].pop())
            # one label would collide with its neighbour; nudged as published
            shift, rot = ((-0.05, 48) if (op == "T-Mobile" and param == (8, 640))
                          else (0.07, 45))
            ax.text(pos + shift, pct, f"({int(param[0])},{int(param[1])})",
                    ha="center", va="bottom", rotation=rot, fontsize=13)

    ax.set_ylabel("Fraction (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(PARAM_ORDER)
    ax.tick_params(axis="both", labelsize=16)
    ax.grid(True, axis="y")
    ax.margins(y=0.2)
    plt.tight_layout()
    p = config.out("a3_ping_pong_distribution_params_15s.pdf")
    plt.savefig(p, bbox_inches="tight")
    plt.close()
    return p


def plot_a5_params():
    """T-Mobile A5 ping-pong rate split by (threshold pair, TTT)."""
    hits = _analyse()["a5"]["T-Mobile"]
    palette = list(PARAM_COLORS["T-Mobile"])
    fig, ax = plt.subplots(figsize=(3.5, 5))
    width = 0.03

    params = [p for p in A5_5G_PARAM_COUNT["T-Mobile"] if p in set(hits)]
    for j, param in enumerate(params):
        pct = hits.count(param) / A5_5G_PARAM_COUNT["T-Mobile"][param] * 100
        pos = (j - len(params) / 2 + 0.03) * width
        ax.bar(pos, pct, width, color=palette.pop())
        (t1, t2), ttt = param
        ax.text(pos - width / 2, pct,
                f"(({int(t1)},{int(t2)}),{int(ttt)})", ha="left", va="bottom",
                rotation=70 if ttt == 640 else 0, fontsize=16)

    ax.set_ylabel("Fraction (%)")
    ax.set_xticks([])
    ax.grid(True, axis="y")
    ax.margins(y=0.2)
    ax.tick_params(axis="y", labelsize=17)
    plt.tight_layout()
    p = config.out("a5_ping_pong_distribution_params_15s.pdf")
    plt.savefig(p, bbox_inches="tight")
    plt.close()
    return p


FIGURES = {
    "a3_ping_pong_distribution_15s.pdf": plot_a3_pingpong,
    "a3_ping_pong_distribution_params_15s.pdf": plot_a3_params,
    "a5_ping_pong_distribution_params_15s.pdf": plot_a5_params,
    "b1_ping_pong_distribution_15s.pdf": plot_b1_pingpong,
}

if __name__ == "__main__":
    for name, fn in FIGURES.items():
        print("wrote", fn())
