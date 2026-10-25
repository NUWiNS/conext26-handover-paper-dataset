"""Section 5.3 -- operational concentration of HO configurations."""
from _impl_runner import make

_PAPER = [("A3", "LTE"), ("A3", "5G"), ("A5", "LTE"), ("A5", "5G"),
          ("B1", "5G"), ("A2", "5G")]

FIGURES = {
    f"ho_contribution_per_config_{ev}_{radio}.pdf":
        make(f"ho_contribution_per_config_{ev}_{radio}.pdf")
    for ev, radio in _PAPER
}

if __name__ == "__main__":
    for n, fn in FIGURES.items():
        print("wrote", fn())
