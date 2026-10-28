"""Path configuration for the figure-generation scripts.

All data paths are resolved relative to a single root so the scripts run
unmodified on any machine.  Set the root in one of two ways:

    export CONEXT26_DATA=/path/to/processed       # environment variable
    python make_figures.py --data /path/to/processed

If neither is given, ``./processed`` next to the repository root is used.
"""
import os
import sys
from pathlib import Path

import matplotlib
import matplotlib.style          # not pulled in by `import matplotlib`
matplotlib.use("Agg")

_REPO_ROOT = Path(__file__).resolve().parent.parent

# The paper's figures were styled by a matplotlibrc that happened to sit in
# the analysis working directory, so it applied only when the scripts were
# run from there. Applying it explicitly on import keeps the regenerated
# figures identical regardless of the current directory.
matplotlib.style.use(Path(__file__).resolve().parent / "paper.mplstyle")

DATA_ROOT = Path(
    os.environ.get("CONEXT26_DATA", _REPO_ROOT / "processed")
).resolve()

FIG_OUT = Path(
    os.environ.get("CONEXT26_FIGS", _REPO_ROOT / "figures_out")
).resolve()


def set_roots(data=None, figs=None):
    """Override the roots at runtime (used by make_figures.py)."""
    global DATA_ROOT, FIG_OUT
    if data:
        DATA_ROOT = Path(data).resolve()
    if figs:
        FIG_OUT = Path(figs).resolve()
    FIG_OUT.mkdir(parents=True, exist_ok=True)


def data(*parts):
    """Resolve a path under DATA_ROOT, failing with a useful message."""
    p = DATA_ROOT.joinpath(*parts)
    if not p.exists():
        sys.exit(
            f"missing input: {p}\n"
            f"  DATA_ROOT is {DATA_ROOT}\n"
            f"  Set CONEXT26_DATA or pass --data. See MANIFEST.md for which\n"
            f"  tier of the dataset each figure needs."
        )
    return p


# Figure number each output carries in the paper (Proc. ACM Netw. 4, CoNEXT4,
# Article 64). Outputs absent from this table are not in the paper and are
# written without a prefix, which makes the distinction visible in a listing.
PAPER_FIG = {
    "all_events_overall_vs_ho_LTE.pdf": 2,
    "all_events_overall_vs_ho_5G.pdf": 2,
    "ho_event_overhead_pct_by_event.pdf": 3,
    "richness_overall.pdf": 4,
    "richness_comp_2022_2024.pdf": 5,
    "rsrp_rsrq_subplots.pdf": 6,
    **{f"aggressiveness_{e}.pdf": 8
       for e in ("A1", "A2", "A3", "A5", "B1")},
    **{f"ho_contribution_per_config_{e}.pdf": 9
       for e in ("A3_LTE", "A3_5G", "A5_LTE", "A5_5G", "B1_5G", "A2_5G")},
    "a3_ping_pong_distribution_15s.pdf": 10,
    "a3_ping_pong_distribution_params_15s.pdf": 10,
    "a5_ping_pong_distribution_params_15s.pdf": 12,
    "b1_ping_pong_distribution_15s.pdf": 13,
}


def paper_name(name):
    """Prefix an output with its paper figure number, e.g. fig03_<name>."""
    n = PAPER_FIG.get(name)
    return f"fig{n:02d}_{name}" if n else name


def out(name):
    FIG_OUT.mkdir(parents=True, exist_ok=True)
    return FIG_OUT / paper_name(name)
