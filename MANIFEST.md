# Figure manifest

Every figure in the camera-ready (Proc. ACM Netw. 4, CoNEXT4, Article 64),
the script that produces it, and the data tier it needs.

```bash
pip install -r requirements.txt
cd figures
python make_figures.py --data /path/to/processed --out ../figures_out
```

Outputs are named after the figure they reproduce, e.g.
`fig08_aggressiveness_A5.pdf` for Fig. 8. Anything a module writes that is
not in the paper is left unprefixed, so a directory listing separates the
two at a glance.

Modules run independently: figures whose inputs are absent are reported as
**skipped**, the rest still run. There are 21 outputs in all; the small tier
alone produces 16 of them.

## Data tiers

Assemble with `prepare/make_processed_bundle.py --tier {small,medium,full}`.
Tiers are cumulative.

| Tier | Contents | Size | Figures |
|---|---|---|---|
| small | `events/`, `aggressiveness/`, 2 files of `diversity/` | **53 MB** | 2, 3, 4, 5, 8, 9 |
| medium | + `rsrp/`, rest of `diversity/` | ~1.2 GB | 6 |
| full | + `handover/` | ~19.7 GB | 10, 12(c), 13(a) |

The Figures column lists only what each tier adds, and only figures this
repository actually generates. Figures of the paper that are not listed
anywhere in this table are not produced by any tier; see the status table
below for which those are and why.

## Status by paper figure

| Fig | Caption | Script | Tier | Status |
|---|---|---|---|---|
| 1 | Basic HO procedure | — | — | static diagram |
| 2 | Distribution of HO-related reporting events (LTE, 5G) | `fig_overall.py` | small | **works** |
| 3 | Event overhead breakdown | `fig_events.py` | small | **works** |
| 4 | Richness of HO configuration parameters | `fig_diversity.py` | small | **works** |
| 5 | Richness comparison, R(2024)−R(2022) | `fig_diversity.py` | small | **works** |
| 6 | RSRP/RSRQ distributions | `fig_rsrp.py` | medium | **works** |
| 7 | Normalized triggered events | — | — | not generated (intentionally excluded) |
| 8 | Aggressiveness of an event to be triggered (a–e) | `fig_aggressiveness.py` | small | **works** (A1, A2, A3, A5, B1; A6 not in the paper) |
| 9 | Concentration of HOs across configurations (a–f) | `fig_concentration.py` | small | **works** |
| 10 | Fraction of A3 ping-pong HOs (a, b) | `fig_pingpong.py` | full | **works** |
| 11 | A3 dominant combinations and RSRP | `parse_sigmetrics_merged.py` | full | not ported |
| 12 | A5 dominant combinations, performance, ping-pong | `fig_pingpong.py` | full | panel (c) only; (a) is a table, (b) not ported |
| 13 | % of LTE–5G ping-pong HOs (a, b) | `fig_pingpong.py` | full | panel (a) only; (b) not ported |
| 14 | B1 dominant combinations and performance | `parse_sigmetrics_merged.py` | full | not ported |
| 15 | A2 dominant combinations and performance | `parse_sigmetrics_merged.py` | full | not ported |
| 16 | RSRP and throughput correlation | `parse_ho_new_merged.py` | full | not ported |
| 17 | Measurement route and cellular coverage | route: none found; coverage: `parse_sigmetrics_merged.py` | full | static / not ported |
| 18 | Pre/post throughput at varying time granularity | `parse_sigmetrics_merged.py` | full | not ported |

Ported scripts live in `figures/` and run from the trimmed bundle. The rest
are still the original pipeline scripts: they carry hardcoded paths, have not
been adapted, and are not part of this deposit.

**Scope.** The figures marked above as not generated or not ported are
intentionally skipped, not failures. The release comes in two parts: the raw
measurement data, for use by the community, and the figure scripts, which
reproduce the paper's major results. Nothing in `figures/` attempts the
remaining figures, so none of them can fail.

## Derived input

`prepare/make_event_tables.py` reduces the 6.7 GB `dump_all_imcs_mod_merged.pkl`
to a 0.5 KB event table, so Figs 2 and 3 do not need the full tier.
`make_processed_bundle.py --tier small` runs it automatically when the dump
is reachable.

## Verification

Regenerated §5.2 shares match the paper exactly:

| 5G event share | AT&T | T-Mobile | Verizon |
|---|---|---|---|
| A1 (paper: 12 / 45 / 23) | 11.9% | 45.0% | 22.7% |
| A2 (paper: 21 / 14 / ~10) | 21.2% | 13.9% | 10.3% |
| A6 (paper: 4 / 11 / 27) | 3.9% | 11.2% | 26.7% |

Regenerated PDFs are ~35% larger than the in-paper files; that is matplotlib
font embedding, not a content difference.

Last verified, Python 3.10 / numpy 2.2.2 / pandas 2.3.1:

| Tier | Result |
|---|---|
| small (53 MB, 9 files) | 16 written, 5 skipped, 0 failed |
| medium (1.3 GB, 27 files) | 17 written, 4 skipped, 0 failed |
| full (20 GB, 34 files) | 21 written, 0 skipped, 0 failed |

The skips are expected: they name the tier-2 input they are missing and the
remaining modules still run.
