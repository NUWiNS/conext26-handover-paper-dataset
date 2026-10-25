# Figure manifest

Mapping from each figure in the camera-ready paper to the script that
produces it and the data it needs. Run everything with:

    pip install -r requirements.txt
    cd figures
    python make_figures.py --data /path/to/processed --out ../figures_out

`make_figures.py` runs each module independently: figures whose inputs are
absent are reported as **skipped**, the rest still run. So the small tier
alone produces a useful subset.

## Data tiers

| Tier | Directory | Size | Needed for |
|------|-----------|------|------------|
| small | `processed/events/` | ~3.5 MB | §4 event figures |
| small | `processed/aggressiveness/` | ~49 MB | §5.2, §5.3 figures |
| medium | `processed/rsrp/`, `processed/diversity/` | ~1.2 GB | §5.1 richness, RSRP distributions |
| full | `processed/handover/` | ~19 GB | §6 per-HO performance figures |
| raw | separate deposit | ~200 GB | re-running the parsing pipeline |

## Implemented

These regenerate today from the small tier.

| Paper figure | Script | Inputs |
|---|---|---|
| `all_events_break_tech_mod_normalized.pdf` | `fig_events.py` | `events/main_op_all_events_interface_list_*.pkl`, `events/ho_event_counts.pkl` |
| `ho_event_overhead_pct_by_event.pdf` | `fig_events.py` | same |
| `aggressiveness_{A1,A2,A3,A5,B1}.pdf` | `fig_aggressiveness.py` | `aggressiveness/op_metric_selected_dict.pkl`, `aggressiveness/ho_params_cache.pkl` |
| `ho_contribution_per_config_{A3,A5}_{LTE,5G}.pdf`, `..._B1_5G.pdf`, `..._A2_5G.pdf` | `fig_concentration.py` | same |

`prepare/make_event_tables.py` derives `events/ho_event_counts.pkl`
(0.5 KB) from the 6.7 GB `dump_all_imcs_mod_merged.pkl` in the full tier,
so reviewers do not need that file to reproduce the §4 figures.

## Not yet ported

Still produced only by the original pipeline scripts in the raw bundle.

| Paper figure | Original script | Tier |
|---|---|---|
| `richness_overall.pdf`, `richness_comp_2022_2024.pdf` | `parse_sigmetrics_diversity_merged.py` | medium |
| `rsrp_rsrq_subplots.pdf` | `parse_overall_rsrp.py` | medium |
| `all_events_overall_vs_ho_{LTE,5G}.pdf`, `coverage_comp_combined.pdf` | `parse_sigmetrics_merged.py` | full |
| `a3/a5/b1_ping_pong_*_15s.pdf` (5 figures) | `parse_sigmetrics_merged.py` | full |
| `fiveg_{a3,a5}_rsrp_comp.pdf`, `fiveg_lte_a2_rsrp_comp.pdf`, `lte_fiveg_b1_rsrp_comp.pdf` | `parse_sigmetrics_merged.py` | full |
| `xput_diff_time_granularity_{AT&T,T-Mobile,Verizon}.pdf` | `parse_sigmetrics_merged.py` | full |
| `xput_rsrp_diff_mix_mod.pdf` | `parse_ho_new_merged.py` | full |
| `route_all.png` | no generating script found; ship as a static asset | — |
| `ho_diagram_crop.pdf` | hand-drawn schematic; static asset | — |

## Verification

The regenerated §4 shares match the values quoted in the paper exactly:

| 5G event share | AT&T | T-Mobile | Verizon |
|---|---|---|---|
| A1 | 11.9% | 45.0% | 22.7% |
| A2 | 21.2% | 13.9% | 10.3% |
| A6 | 3.9% | 11.2% | 26.7% |

Regenerated PDFs differ from the in-paper files by ~35% in byte size; this
is matplotlib font embedding, not a content difference.
