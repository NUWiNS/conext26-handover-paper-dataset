"""Section 5.2 -- aggressiveness of HO configurations (Fig. aggressiveness_*)."""
from _impl_runner import make

# A5 and A6 no longer get a panel. A6 is not in the paper at all; A5 is
# dropped at the author's request. A5 is still analysed, because Fig 9 needs
# its per-config tables.
FIGURES = {
    f"aggressiveness_{ev}.pdf": make(f"aggressiveness_{ev}.pdf")
    for ev in ("A1", "A2", "A3", "B1")
}

if __name__ == "__main__":
    for n, fn in FIGURES.items():
        print("wrote", fn())
