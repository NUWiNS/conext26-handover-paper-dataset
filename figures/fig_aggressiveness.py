"""Section 5.2 -- aggressiveness of HO configurations (Fig. aggressiveness_*)."""
from _impl_runner import make

# A6 is produced but not shown in the paper (A6 is a used/disabled choice,
# discussed through its share of reported events instead).
FIGURES = {
    f"aggressiveness_{ev}.pdf": make(f"aggressiveness_{ev}.pdf")
    for ev in ("A1", "A2", "A3", "A5", "B1", "A6")
}

if __name__ == "__main__":
    for n, fn in FIGURES.items():
        print("wrote", fn())
