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


def out(name):
    FIG_OUT.mkdir(parents=True, exist_ok=True)
    return FIG_OUT / name
