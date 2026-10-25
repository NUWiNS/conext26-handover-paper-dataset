"""Regenerate the figures in the CoNEXT '26 handover-configuration paper.

    python make_figures.py --data /path/to/processed --out ./figures_out
    python make_figures.py --list            # show figure -> module mapping
    python make_figures.py --only events     # run one module

Each module is independent: if the inputs for one are absent (for example
because only the small tier of the dataset was downloaded) it is reported
as skipped and the rest still run.
"""
import argparse
import importlib
import sys
import traceback

import config

MODULES = ["fig_events", "fig_aggressiveness", "fig_concentration"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", help="root of the processed dataset")
    ap.add_argument("--out", help="directory to write figures into")
    ap.add_argument("--only", nargs="*", help="run only these modules")
    ap.add_argument("--list", action="store_true",
                    help="list figures and exit")
    a = ap.parse_args()
    config.set_roots(a.data, a.out)

    mods = a.only if a.only else MODULES
    mods = [m if m.startswith("fig_") else "fig_" + m for m in mods]

    if a.list:
        for name in mods:
            m = importlib.import_module(name)
            print(f"{name}:")
            for fig in m.FIGURES:
                print(f"    {fig}")
        return

    print(f"data: {config.DATA_ROOT}")
    print(f"out:  {config.FIG_OUT}\n")
    ok = skipped = failed = 0
    for name in mods:
        try:
            m = importlib.import_module(name)
        except Exception:
            print(f"[FAIL] {name}: import error"); traceback.print_exc(); failed += 1
            continue
        for fig, fn in m.FIGURES.items():
            try:
                fn()
                print(f"  [ok]      {fig}"); ok += 1
            except SystemExit as e:              # config.data() missing input
                print(f"  [skipped] {fig}: {e}"); skipped += 1
            except Exception as e:
                print(f"  [FAILED]  {fig}: {type(e).__name__}: {e}"); failed += 1
    print(f"\n{ok} written, {skipped} skipped, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
