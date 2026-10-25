"""Run the ported analysis module once, no matter how many figures ask for it."""
import runpy

_RAN = False


def run_impl():
    global _RAN
    if not _RAN:
        runpy.run_module("_aggressiveness_impl", run_name="__main__")
        _RAN = True


def make(name):
    import config

    def fn():
        run_impl()
        p = config.FIG_OUT / name
        if not p.exists():
            raise RuntimeError(f"{name} was not produced by the analysis module")
        return p
    fn.__name__ = "plot_" + name.replace(".pdf", "").replace("-", "_")
    return fn
