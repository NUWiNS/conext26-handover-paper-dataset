"""Assemble the trimmed `processed/` bundle for the figure scripts.

Copies only the pickles the paper's figures need, out of the full working
tree, into the layout figures/config.py expects. Run from the machine that
holds the analysis tree.

    python prepare/make_processed_bundle.py --src /home/moinakgh/csv_ho \
        --out /path/to/processed --tier small
    python prepare/make_processed_bundle.py --src ... --out ... --tier all --dry-run

Tiers are cumulative:
    small   events + aggressiveness   (~53 MB)  -> Figs 3, 7, 8, 9
    medium  + richness + RSRP         (~1.2 GB) -> Figs 4, 5, 6
    full    + handover + throughput   (~19 GB)  -> Figs 2, 10-16, 18
"""
import argparse
import shutil
import sys
from pathlib import Path

# tier -> list of (destination subdir, source path relative to --src)
BUNDLE = {
    "small": [
        ("events", "new_parse/all/main_op_all_events_interface_list_1.pkl"),
        ("events", "new_parse/all/main_op_all_events_interface_list_2.pkl"),
        ("events", "new_parse/all/main_op_all_events_interface_list_3.pkl"),
        ("events", "new_parse/all/main_op_all_events_interface_list_2024.pkl"),
        ("aggressiveness", "ho_params_cache.pkl"),
        # NOTE: lives on the shared mount, not under --src; see --extra below
        # Figs 4 and 5 (fig_diversity) need only these two 22 KB files plus
        # op_metric_selected_dict.pkl, which is already in this tier, so they
        # belong here rather than behind a 1.25 GB medium download.
        ("diversity", "yearwise_diversity_pkls/overall_2022.pkl"),
        ("diversity", "yearwise_diversity_pkls/overall_2024.pkl"),
    ],
    "medium": [
        ("rsrp", "new_parse/rsrp_freq_dict_1.pkl"),
        ("rsrp", "new_parse/rsrp_freq_dict_2.pkl"),
        ("rsrp", "new_parse/rsrp_freq_dict_3.pkl"),
        ("rsrp", "new_parse/rsrp_freq_dict_2024.pkl"),
        ("diversity", "city_data_processed.pkl"),
        ("diversity", "city_data_processed_2022.pkl"),
        ("diversity", "city_data_processed_2024.pkl"),
        ("diversity", "timezone_data_processed.pkl"),
        ("diversity", "timezone_data_processed_2022.pkl"),
        ("diversity", "timezone_data_processed_2024.pkl"),
        ("diversity", "yearwise_diversity_pkls/fiveg_band_2022.pkl"),
        ("diversity", "yearwise_diversity_pkls/fiveg_band_2024.pkl"),
        ("diversity", "yearwise_diversity_pkls/fiveg_nsa_sa_2022.pkl"),
        ("diversity", "yearwise_diversity_pkls/fiveg_nsa_sa_2024.pkl"),
        # these four share a basename, so each gets an explicit destination name
        ("diversity", "merged_pickles/processed_pickles/measurement_report_data.pkl",
         "measurement_report_data_trip1.pkl"),
        ("diversity", "driving_trip_2/merged_pickles/processed_pickles/measurement_report_data.pkl",
         "measurement_report_data_trip2.pkl"),
        ("diversity", "driving_trip_3/merged_pickles/processed_pickles/measurement_report_data.pkl",
         "measurement_report_data_trip3.pkl"),
        ("diversity", "driving_trip_lax_bos_2024/merged_pickles/processed_pickles/measurement_report_data.pkl",
         "measurement_report_data_trip4.pkl"),
    ],
    "full": [
        ("handover", "new_parse/handover/main_op_ho_info_list_1.pkl"),
        ("handover", "new_parse/handover/main_op_ho_info_list_2.pkl"),
        ("handover", "new_parse/handover/main_op_ho_info_list_3.pkl"),
        ("handover", "new_parse/handover/main_op_ho_info_list_2024.pkl"),
        ("handover", "new_parse/handover/inter_mr_arrival_filtered_data.pkl"),
        ("handover", "ping_pong_data.pkl"),
        ("handover", "dump_all_imcs_mod_merged.pkl"),
    ],
}
ORDER = ["small", "medium", "full"]

# files that do not live under --src
EXTRA = [
    ("aggressiveness", "op_metric_selected_dict.pkl",
     "/mnt/nuwinsshared/moinak/reporting_data_more/op_metric_selected_dict.pkl"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="root of the analysis tree")
    ap.add_argument("--out", required=True, help="processed/ bundle to create")
    ap.add_argument("--tier", choices=ORDER + ["all"], default="small")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    src, out = Path(a.src).resolve(), Path(a.out).resolve()

    tiers = ORDER if a.tier == "all" else ORDER[:ORDER.index(a.tier) + 1]
    items = []
    for t in tiers:
        for entry in BUNDLE[t]:
            dest, rel = entry[0], entry[1]
            name = entry[2] if len(entry) > 2 else Path(rel).name
            items.append((dest, src / rel, name))
    if "small" in tiers:
        items += [(d, Path(p), n) for d, n, p in EXTRA]

    total = missing = 0
    for dest, path, name in items:
        if not path.exists():
            print(f"  [MISSING] {path}")
            missing += 1
            continue
        size = path.stat().st_size
        total += size
        target = out / dest / name
        print(f"  {'[dry] ' if a.dry_run else ''}{size/1048576:9.1f} MB  "
              f"{dest}/{name}")
        if not a.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)

    # The small tier also needs the derived event table. It is 0.5 KB but is
    # computed from the 6.7 GB HO dump, so derive it here rather than make
    # reviewers download that file just to plot two bar charts.
    if "small" in tiers and not a.dry_run:
        dump = src / "dump_all_imcs_mod_merged.pkl"
        target = out / "events" / "ho_event_counts.pkl"
        if target.exists():
            print(f"\n  events/ho_event_counts.pkl already present, keeping it")
        elif dump.exists():
            print(f"\n  deriving events/ho_event_counts.pkl from {dump.name} ...")
            import subprocess
            r = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("make_event_tables.py")),
                 "--ho-dump", str(dump), "--out", str(target)],
                capture_output=True, text=True)
            print("    " + (r.stdout.strip().splitlines() or ["(no output)"])[0]
                  if r.returncode == 0 else f"    FAILED: {r.stderr.strip()[:200]}")
        else:
            print(f"\n  WARNING: {dump} not found; run prepare/make_event_tables.py"
                  f"\n  separately to produce events/ho_event_counts.pkl")

    print(f"\n  tiers: {', '.join(tiers)}")
    print(f"  {len(items)-missing} files, {total/1073741824:.2f} GB"
          + (" (dry run, nothing copied)" if a.dry_run else f" -> {out}"))
    if missing:
        print(f"  {missing} missing; adjust --src or the BUNDLE table")
        sys.exit(1)


if __name__ == "__main__":
    main()
