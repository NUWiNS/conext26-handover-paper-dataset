"""Sections 5.2 and 5.3 -- configuration aggressiveness and operational concentration.

Ported from the analysis pipeline with all paths parameterised through config.py.
Produces aggressiveness_{A1,A2,A3,A5,A6,B1}.pdf and
ho_contribution_per_config_{event}_{LTE,5G}.pdf.  The paper uses A1, A2, A3, A5
and B1 of the former, and A3/A5 (LTE and 5G) plus B1 and A2 (5G) of the latter.

Inputs (processed tier):
    aggressiveness/op_metric_selected_dict.pkl   ~49 MB
    aggressiveness/ho_params_cache.pkl           ~28 KB
"""
# -*- coding: utf-8 -*-
"""
Two-part analysis:

  1) Aggressiveness:  For every (operator, event, trigger_quantity), classify each
     configured sample as aggressive / moderate / conservative according to whether
     its threshold (or offset) and TTT make the event easy or hard to fire.

  2) Triggered vs HO:  For events that drive actual handovers (A3 / A5 intra-RAT,
     B1 LTE->5G, A2 5G->LTE), compare the all-triggered configs (op_metric_selected
     pickle) with the HO-only configs (get_ho_parameters cache). Quantify
     'unnecessary firing' — i.e. configs that show up in the all-triggered set but
     are absent from (or rare in) the HO subset.

Data sources:
    <processed>/aggressiveness/op_metric_selected_dict.pkl
        -> lte_op_metric_selected_dict, fiveg_op_metric_selected_dict
    <processed>/aggressiveness/ho_params_cache.pkl   (cached output of get_ho_parameters)

Outputs (in <figures_out>/):
    aggressiveness.csv
    aggressiveness_by_event.pdf
"""
import os
import math
import pickle as pkl
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from collections import Counter

import config
PKL_OP_METRIC = str(config.data('aggressiveness', 'op_metric_selected_dict.pkl'))
PKL_HO_CACHE  = str(config.data('aggressiveness', 'ho_params_cache.pkl'))
OUT_DIR       = str(config.FIG_OUT) + '/'
os.makedirs(OUT_DIR, exist_ok=True)

OPS    = ['AT&T', 'T-Mobile', 'Verizon']
OP_COLORS = {
    'AT&T':     'deepskyblue',
    'T-Mobile': 'purple',
    'Verizon':  'red',
}

# ─── Aggressiveness rules ────────────────────────────────────────────────────
# Three-band classification from engineering signal-quality bands.
# Cutoffs are absolute (not per-operator) — they describe physical link
# quality, so operators are directly comparable.
#
# RSRP cutoffs (dBm) — derived from widely-cited signal-quality bands
#   (Excellent >= -89, Good -90..-104, Fair -105..-114, Poor -115..-124).
# RSRQ cutoffs (dB)  — supplied by user (engineering judgement, no public CDF).
# A3 offset cutoffs come from sourced 2-4 dB recommendation.
# TTT cutoffs come from the 3GPP TTT ladder.

# A1 / A5-thr2 / B1 RSRP (LOW thr is aggressive: easy for signal to exceed)
RSRP_LOW_AGG    = -115.0    # aggressive: cutoff sits in "Poor" band
RSRP_LOW_CONS   = -90.0     # conservative: cutoff sits in "Excellent/Good"

# A2 / A5-thr1 RSRP (HIGH thr is aggressive: signal easily falls below)
RSRP_HIGH_AGG   = -105.0    # aggressive: cutoff at Good/Fair boundary
RSRP_HIGH_CONS  = -120.0    # conservative: cutoff deep in Poor

# B1 RSRP (inter-RAT) — slightly different bands per published guidance
RSRP_B1_AGG     = -110.0
RSRP_B1_CONS    = -95.0

# A3 offset (in dB). Smaller offset = aggressive.
A3_OFFSET_RSRP_AGG   = 2.0   # sourced "2 dB = aggressive"
A3_OFFSET_RSRP_CONS  = 5.0
A3_OFFSET_RSRQ_AGG   = 1.0   # user-supplied
A3_OFFSET_RSRQ_CONS  = 2.5

# A6 offset (in dB). Shifted relative to A3 to reflect SCell-change cost slack:
# SCell change has no service impact, so operators can tolerate larger offsets
# without being "over-conservative".
A6_OFFSET_RSRP_AGG   = 3.0
A6_OFFSET_RSRP_CONS  = 8.0
A6_OFFSET_RSRQ_AGG   = 2.0
A6_OFFSET_RSRQ_CONS  = 4.0

# A1 / A5-thr2 / B1 RSRQ (LOW thr aggressive)  [user-supplied bands]
RSRQ_A1_AGG          = -15.0
RSRQ_A1_CONS         = -12.0
RSRQ_B1_AGG          = -18.0
RSRQ_B1_CONS         = -12.0
RSRQ_A5_THR2_AGG     = -16.0
RSRQ_A5_THR2_CONS    = -12.0

# A2 / A5-thr1 RSRQ (HIGH thr aggressive)  [user-supplied bands]
RSRQ_A2_AGG          = -13.0
RSRQ_A2_CONS         = -16.0
RSRQ_A5_THR1_AGG     = -12.0
RSRQ_A5_THR1_CONS    = -17.0

# TTT (ms)
TTT_AGG_MAX     = 200.0
TTT_CONS_MIN    = 640.0

# Drop an RSRQ row if it's too sparse in absolute terms OR if the RSRP companion
# for the same (op, event) is much larger (RSRQ is a minority trigger).
# Cutoffs relaxed to retain AT&T A5 (N=3,376, ratio 11.9×) and
# Verizon A5 (N=1,303, ratio 12.7×) while still dropping the very-sparse rows.
RSRQ_MIN_ABS_N        = 800    # absolute minimum sample count to keep
RSRQ_MAX_RSRP_RATIO   = 15.0   # drop if N_rsrp / N_rsrq > this


def _band(value, agg_pred, cons_pred):
    if agg_pred(value):
        return 'aggressive'
    if cons_pred(value):
        return 'conservative'
    return 'moderate'


# --- per-event metric classifiers (engineering-band cutoffs) ---
# A1 (serv > thr): LOW thr = aggressive
def cls_a1_rsrp(t):
    return _band(t, lambda x: x <= RSRP_LOW_AGG, lambda x: x >= RSRP_LOW_CONS)
def cls_a1_rsrq(t):
    return _band(t, lambda x: x <= RSRQ_A1_AGG, lambda x: x >= RSRQ_A1_CONS)

# A2 (serv < thr): HIGH thr = aggressive
def cls_a2_rsrp(t):
    return _band(t, lambda x: x >= RSRP_HIGH_AGG, lambda x: x <= RSRP_HIGH_CONS)
def cls_a2_rsrq(t):
    return _band(t, lambda x: x >= RSRQ_A2_AGG, lambda x: x <= RSRQ_A2_CONS)

# A3 (neigh − serv > off): SMALL offset = aggressive
def cls_a3_rsrp(o):
    return _band(o, lambda x: x <= A3_OFFSET_RSRP_AGG, lambda x: x >= A3_OFFSET_RSRP_CONS)
def cls_a3_rsrq(o):
    return _band(o, lambda x: x <= A3_OFFSET_RSRQ_AGG, lambda x: x >= A3_OFFSET_RSRQ_CONS)

# A6 (neigh − SCell > off): same direction as A3, shifted band
def cls_a6_rsrp(o):
    return _band(o, lambda x: x <= A6_OFFSET_RSRP_AGG, lambda x: x >= A6_OFFSET_RSRP_CONS)
def cls_a6_rsrq(o):
    return _band(o, lambda x: x <= A6_OFFSET_RSRQ_AGG, lambda x: x >= A6_OFFSET_RSRQ_CONS)

# A5 thr1 (serv < thr1): HIGH thr1 = aggressive
def cls_a5_thr1_rsrp(t):
    return _band(t, lambda x: x >= RSRP_HIGH_AGG, lambda x: x <= RSRP_HIGH_CONS)
def cls_a5_thr1_rsrq(t):
    return _band(t, lambda x: x >= RSRQ_A5_THR1_AGG, lambda x: x <= RSRQ_A5_THR1_CONS)

# A5 thr2 (neigh > thr2): LOW thr2 = aggressive
def cls_a5_thr2_rsrp(t):
    return _band(t, lambda x: x <= RSRP_LOW_AGG, lambda x: x >= RSRP_LOW_CONS)
def cls_a5_thr2_rsrq(t):
    return _band(t, lambda x: x <= RSRQ_A5_THR2_AGG, lambda x: x >= RSRQ_A5_THR2_CONS)

# B1 (neigh > thr): LOW thr = aggressive
def cls_b1_rsrp(t):
    return _band(t, lambda x: x <= RSRP_B1_AGG, lambda x: x >= RSRP_B1_CONS)
def cls_b1_rsrq(t):
    return _band(t, lambda x: x <= RSRQ_B1_AGG, lambda x: x >= RSRQ_B1_CONS)

# TTT
def cls_ttt(t):
    return _band(t, lambda x: x <= TTT_AGG_MAX, lambda x: x >= TTT_CONS_MIN)


def classify_metric(event, tq, combo):
    """Three-band classification for the metric (threshold/offset) component only."""
    if event == 'A1':
        return cls_a1_rsrp(combo[0]) if tq == 'rsrp' else cls_a1_rsrq(combo[0])
    if event == 'A2':
        return cls_a2_rsrp(combo[0]) if tq == 'rsrp' else cls_a2_rsrq(combo[0])
    if event == 'A3':
        return cls_a3_rsrp(combo[0]) if tq == 'rsrp' else cls_a3_rsrq(combo[0])
    if event == 'A6':
        return cls_a6_rsrp(combo[0]) if tq == 'rsrp' else cls_a6_rsrq(combo[0])
    if event == 'A5':
        thr1, thr2 = combo
        if tq == 'rsrp':
            c1 = cls_a5_thr1_rsrp(thr1)
            c2 = cls_a5_thr2_rsrp(thr2)
        else:
            c1 = cls_a5_thr1_rsrq(thr1)
            c2 = cls_a5_thr2_rsrq(thr2)
        rank = {'aggressive': 2, 'moderate': 1, 'conservative': 0}
        return min((c1, c2), key=lambda c: rank[c])   # weaker side wins
    if event == 'B1':
        return cls_b1_rsrp(combo[0]) if tq == 'rsrp' else cls_b1_rsrq(combo[0])
    return 'moderate'


def classify_a5_parts(tq, combo):
    """The two A5 thresholds classified separately, for the M1/M2 bars."""
    thr1, thr2 = combo
    if tq == 'rsrp':
        return cls_a5_thr1_rsrp(thr1), cls_a5_thr2_rsrp(thr2)
    return cls_a5_thr1_rsrq(thr1), cls_a5_thr2_rsrq(thr2)


def classify(event, tq, radio, op, combo, ttt):
    """Combined overall classification for one (combo, ttt) sample."""
    metric_cls = classify_metric(event, tq, combo)
    ttt_cls    = cls_ttt(ttt)
    if metric_cls == 'aggressive'   and ttt_cls == 'aggressive':   return 'aggressive'
    if metric_cls == 'conservative' and ttt_cls == 'conservative': return 'conservative'
    return 'moderate'


# ─── Load triggered (op_metric) and reuse the same combo-builder ────────────
with open(PKL_OP_METRIC, 'rb') as f:
    lte_dict, fiveg_dict = pkl.load(f)


# ─── Pre-load HO cache + build per-cell absolute-count lookup ───────────────
# So the aggressiveness loop can enrich each cell with HO-only configs
# (configs that produced HOs but never appeared in op_metric).
with open(PKL_HO_CACHE, 'rb') as f:
    _ho_cache_early = pkl.load(f)


def _norm_cache_key_early(k, kind):
    if kind == 'pair':
        (combo_pair, ttt) = k
        return ((float(combo_pair[0]), float(combo_pair[1])), float(ttt))
    (val, ttt) = k
    return ((float(val),), float(ttt))


_HO_SRC = [
    # (cache_key, radio, event, combo_kind, trigger_quantity)
    ('a3_lte_intra',       'LTE', 'A3', 'scalar', 'rsrp'),
    ('a5_lte_intra',       'LTE', 'A5', 'pair',   'rsrp'),
    ('a3_lte_intra_rsrq',  'LTE', 'A3', 'scalar', 'rsrq'),
    ('a5_lte_intra_rsrq',  'LTE', 'A5', 'pair',   'rsrq'),
    ('a3_5g_intra',        '5G',  'A3', 'scalar', 'rsrp'),
    ('a5_5g_intra',        '5G',  'A5', 'pair',   'rsrp'),
    ('b1_lte_to_5g',       '5G',  'B1', 'scalar', 'rsrp'),
    ('a2_5g_to_lte',       '5G',  'A2', 'scalar', 'rsrp'),
]
# ho_count_for_cell[(radio, ev, op, tq)] = {normalized_(combo,ttt)_key: abs_HO_count}
ho_count_for_cell = {}
for _ck, _r, _e, _kind, _tq in _HO_SRC:
    _per_op = _ho_cache_early.get(_ck + '_count', {})
    for _op in ('AT&T', 'T-Mobile', 'Verizon'):
        _lookup = {}
        for _k, _c in _per_op.get(_op, {}).items():
            _nk = _norm_cache_key_early(_k, _kind)
            _lookup[_nk] = _lookup.get(_nk, 0) + _c
        ho_count_for_cell[(_r, _e, _op, _tq)] = _lookup

a = 1

def _classify_tq_by_threshold(t):
    if t is None: return None
    if t < -30:   return 'rsrp'
    if t > -20:   return 'rsrq'
    return None


def _safe_get(md, key, n):
    return md.get(key, [None] * n)


def build_tuples(metric_dict, event, tq_filter=None, radio=None):
    md = metric_dict.get(event, {})
    ttt = md.get('time_to_trigger', [])
    n = len(ttt)
    if n == 0:
        return []
    hyst = _safe_get(md, 'hysteresis', n)

    use_threshold_classifier = (radio == 'LTE' and event in ('A1', 'A2', 'A5', 'B1'))
    if use_threshold_classifier:
        thr_for_class = _safe_get(
            md, 'threshold_neighbor' if event == 'B1' else 'threshold', n
        )
        sample_tq = [_classify_tq_by_threshold(thr_for_class[i]) for i in range(n)]
    else:
        sample_tq = _safe_get(md, 'trigger_quantity', n)

    if tq_filter is None:
        indices = [i for i in range(n) if sample_tq[i] is not None]
    else:
        indices = [i for i in range(n) if sample_tq[i] == tq_filter]
    if not indices:
        return []

    out = []
    if event == 'A1':
        thr = _safe_get(md, 'threshold', n)
        for i in indices:
            if thr[i] is not None and hyst[i] is not None and ttt[i] is not None:
                out.append(((thr[i] + hyst[i],), ttt[i]))
    elif event == 'A2':
        thr = _safe_get(md, 'threshold', n)
        for i in indices:
            if thr[i] is not None and hyst[i] is not None and ttt[i] is not None:
                out.append(((thr[i] - hyst[i],), ttt[i]))
    elif event == 'A3' or event == 'A6':
        off = _safe_get(md, 'offset', n)
        for i in indices:
            if off[i] is not None and hyst[i] is not None and ttt[i] is not None:
                out.append(((off[i] + hyst[i],), ttt[i]))
    elif event == 'A5':
        thr  = _safe_get(md, 'threshold',          n)
        thrn = _safe_get(md, 'threshold_neighbor', n)
        for i in indices:
            if (thr[i] is not None and thrn[i] is not None
                    and hyst[i] is not None and ttt[i] is not None):
                out.append(((thr[i] - hyst[i], thrn[i] + hyst[i]), ttt[i]))
    elif event == 'B1':
        thr = _safe_get(md, 'threshold_neighbor', n)
        for i in indices:
            if thr[i] is not None and hyst[i] is not None and ttt[i] is not None:
                out.append(((thr[i] + hyst[i],), ttt[i]))
    return out


# ─── PART 1 : Aggressiveness ─────────────────────────────────────────────────
# Per (radio, tq, op, event): count aggressive / moderate / conservative samples.

EVENTS = ['A1', 'A2', 'A3', 'A5', 'A6', 'B1']
RADIO_TQ = [
    ('LTE', 'rsrp', lte_dict),
    ('LTE', 'rsrq', lte_dict),
    ('5G',  'rsrp', fiveg_dict),
]

agg_counts   = {}   # combined classification
metric_counts = {}  # metric-only classification
# A5 carries two thresholds (serving < thr1, neighbour > thr2) and the paper
# shows them as separate M1/M2 bars rather than collapsing them. Only the
# combined view is used for every other event.
m1_counts = {}
m2_counts = {}
ttt_counts    = {}  # TTT-only classification
agg_total    = {}
ho_only_added = {}   # (radio, tq, op, ev) -> {'configs': N, 'weight': total_HO_count}
for radio, tq, src in RADIO_TQ:
    for op in OPS:
        op_dict = src.get(op, {})
        for ev in EVENTS:
            tuples = build_tuples(op_dict, ev, tq_filter=tq, radio=radio)
            b   = {'aggressive': 0, 'moderate': 0, 'conservative': 0}
            mb  = {'aggressive': 0, 'moderate': 0, 'conservative': 0}
            tb  = {'aggressive': 0, 'moderate': 0, 'conservative': 0}
            p1  = {'aggressive': 0, 'moderate': 0, 'conservative': 0}
            p2  = {'aggressive': 0, 'moderate': 0, 'conservative': 0}
            for combo, ttt in tuples:
                m_cls = classify_metric(ev, tq, combo)
                t_cls = cls_ttt(ttt)
                mb[m_cls] += 1
                tb[t_cls] += 1
                if ev == 'A5':
                    c1, c2 = classify_a5_parts(tq, combo)
                    p1[c1] += 1
                    p2[c2] += 1
                if m_cls == 'aggressive'   and t_cls == 'aggressive':   b['aggressive']   += 1
                elif m_cls == 'conservative' and t_cls == 'conservative': b['conservative'] += 1
                else: b['moderate'] += 1
            n_from_trig = len(tuples)

            # Enrich with HO-only configs for whichever tq has an HO-cache entry.
            # Each HO-only config contributes weight = its absolute HO count.
            ho_only_n_cfg = 0
            ho_only_weight = 0
            ho_lookup = ho_count_for_cell.get((radio, ev, op, tq), {})
            if ho_lookup:
                trig_keys = {(tuple(float(v) for v in c), float(t)) for c, t in tuples}
                for ho_key, n_ho in ho_lookup.items():
                    if ho_key in trig_keys or n_ho <= 0:
                        continue
                    combo, ttt = ho_key
                    m_cls = classify_metric(ev, tq, combo)
                    t_cls = cls_ttt(ttt)
                    mb[m_cls] += n_ho
                    tb[t_cls] += n_ho
                    if ev == 'A5':
                        c1, c2 = classify_a5_parts(tq, combo)
                        p1[c1] += n_ho
                        p2[c2] += n_ho
                    if m_cls == 'aggressive'   and t_cls == 'aggressive':   b['aggressive']   += n_ho
                    elif m_cls == 'conservative' and t_cls == 'conservative': b['conservative'] += n_ho
                    else: b['moderate'] += n_ho
                    ho_only_n_cfg  += 1
                    ho_only_weight += n_ho

            agg_counts[(radio, tq, op, ev)]    = b
            metric_counts[(radio, tq, op, ev)] = mb
            ttt_counts[(radio, tq, op, ev)]    = tb
            if ev == 'A5':
                m1_counts[(radio, tq, op, ev)] = p1
                m2_counts[(radio, tq, op, ev)] = p2
            agg_total[(radio, tq, op, ev)]     = n_from_trig + ho_only_weight
            ho_only_added[(radio, tq, op, ev)] = {
                'configs': ho_only_n_cfg, 'weight': ho_only_weight,
                'n_from_trig': n_from_trig,
            }


# ── Drop RSRQ rows that are sparse or dwarfed by RSRP for the same (op, ev) ─
dropped_rsrq = []   # (radio, op, ev, n_rsrq, n_rsrp, reason)
for (radio, tq, op, ev) in list(agg_total.keys()):
    if tq != 'rsrq':
        continue
    n_rsrq = agg_total[(radio, tq, op, ev)]
    n_rsrp = agg_total.get((radio, 'rsrp', op, ev), 0)
    reasons = []
    if n_rsrq < RSRQ_MIN_ABS_N:
        reasons.append(f'N={n_rsrq:,}<{RSRQ_MIN_ABS_N:,}')
    if n_rsrq > 0 and n_rsrp / n_rsrq > RSRQ_MAX_RSRP_RATIO:
        reasons.append(f'rsrp/rsrq={n_rsrp / n_rsrq:.1f}x>{RSRQ_MAX_RSRP_RATIO}')
    if reasons:
        dropped_rsrq.append((radio, op, ev, n_rsrq, n_rsrp, '; '.join(reasons)))
        del agg_counts[(radio, tq, op, ev)]
        del agg_total[(radio, tq, op, ev)]
        metric_counts.pop((radio, tq, op, ev), None)
        ttt_counts.pop((radio, tq, op, ev), None)
        m1_counts.pop((radio, tq, op, ev), None)
        m2_counts.pop((radio, tq, op, ev), None)

if dropped_rsrq:
    print('Dropped RSRQ rows (sparse or dwarfed by RSRP):')
    print('-' * 90)
    print(f'{"Radio":<5s} {"Op":<10s} {"Ev":<3s}  {"N_rsrq":>8s}  {"N_rsrp":>8s}   reason(s)')
    for radio, op, ev, n_rsrq, n_rsrp, reason in dropped_rsrq:
        print(f'{radio:<5s} {op:<10s} {ev:<3s}  {n_rsrq:>8,d}  {n_rsrp:>8,d}   {reason}')
    print('-' * 90)
    print()




# ─── Plot: one PDF per event ────────────────────────────────────────────────
CLS_COLOR = {'aggressive': '#d62728', 'moderate': '#ff7f0e', 'conservative': '#2ca02c'}
import matplotlib.patches as mpatches

# Background shading per (radio, tq) group — darker tones for better contrast
GROUP_SHADE = {
    ('LTE', 'rsrp'): '#7daed8',   # medium blue
    ('LTE', 'rsrq'): '#3b78b4',   # deeper blue
    ('5G',  'rsrp'): '#e08a4d',   # darker peach / amber
}
GROUP_LABEL = {
    ('LTE', 'rsrp'): 'LTE\nRSRP',
    ('LTE', 'rsrq'): 'LTE\nRSRQ',
    ('5G',  'rsrp'): '5G\nRSRP',
}
# Plot order: RSRQ first within LTE, then RSRP, then 5G
GROUP_ORDER = [('LTE', 'rsrq'), ('LTE', 'rsrp'), ('5G', 'rsrp')]


def plot_event_aggressiveness(ev):
    # Build the list of operator slots in plot order; skip empty groups
    slots = []               # [(radio, tq, op, n, x_center)]
    group_spans = []         # [(x_start, x_end, (radio, tq))]
    x = 0
    bar_w = 0.30 if ev == 'A5' else 0.32     # three bars share the wider A5 slot
    bar_off = 0.36 if ev == 'A5' else 0.18   # half the M/T (or M1..T) spacing
    gap_between_groups = 0.55

    # A5 is shown on RSRP only: the published figure has LTE RSRP and 5G RSRP
    # panels and no RSRQ panel, and its two thresholds are drawn as separate
    # M1/M2 bars rather than collapsed into one M.
    split_metric = (ev == 'A5')
    group_order = ([g for g in GROUP_ORDER if g[1] == 'rsrp']
                   if split_metric else GROUP_ORDER)

    for radio, tq in group_order:
        ops_here = [op for op in OPS if agg_total.get((radio, tq, op, ev), 0) > 0]
        if not ops_here:
            continue
        x_first = x
        op_step = 1.6 if split_metric else 1.0   # three bars need a wider slot
        for op in ops_here:
            slots.append((radio, tq, op, agg_total[(radio, tq, op, ev)], x))
            x += op_step
        group_spans.append((x_first - 0.5, x - op_step + 0.5, (radio, tq)))
        x += gap_between_groups

    if not slots:
        return

    n_slots = len(slots)
    fig_w = max(2.8, (0.95 if split_metric else 0.55) * n_slots + 0.7)
    fig_h = 2.8
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), constrained_layout=True)

    # Group background shading
    for x_lo, x_hi, key in group_spans:
        ax.axvspan(x_lo, x_hi, color=GROUP_SHADE[key], alpha=0.45, zorder=0)

    # Two stacked bars per operator: metric (solid) + TTT (hatched)
    for (radio, tq, op, n, xp) in slots:
        key = (radio, tq, op, ev)
        if split_metric and key in m1_counts:
            sides = (
                ('M1', xp - bar_off, m1_counts[key],  ''),
                ('M2', xp,           m2_counts[key],  ''),
                ('T',  xp + bar_off, ttt_counts[key], '///'),
            )
        else:
            sides = (
                ('M', xp - bar_off, metric_counts[key], ''),
                ('T', xp + bar_off, ttt_counts[key],    '///'),
            )
        for side, x_pos, counts, hatch in sides:
            bottom = 0.0
            for cls in ('aggressive', 'moderate', 'conservative'):
                pct = 100.0 * counts[cls] / n if n else 0
                ax.bar(x_pos, pct, bar_w, bottom=bottom,
                       color=CLS_COLOR[cls], edgecolor='white',
                       linewidth=0.4, hatch=hatch, zorder=2)
                bottom += pct
            # "M" / "T" tag immediately below the bar
            ax.text(x_pos, -3, side, ha='center', va='top',
                    fontsize=9, color='#222', fontweight='bold')

    # X tick labels (operator name + sample count), placed below the M/T tags
    ax.set_xticks([s[4] for s in slots])
    ax.set_xticklabels([f'{op}\n({n:,})' for (_, _, op, n, _) in slots],
                       fontsize=9, rotation=45, ha='right')
    ax.tick_params(axis='x', pad=15, length=0)
    ax.tick_params(axis='y', labelsize=10)
    ax.set_xlim(-0.55, group_spans[-1][1] + 0.15)
    ax.set_ylim(0, 100)
    ax.set_ylabel('%', fontsize=12)
    ax.grid(axis='y', alpha=0.4, linewidth=0.5)
    ax.set_axisbelow(True)

    # Group header labels above each shaded region
    for x_lo, x_hi, key in group_spans:
        ax.text((x_lo + x_hi) / 2, 103, GROUP_LABEL[key],
                ha='center', va='bottom', fontsize=10, fontweight='bold',
                color='#222')

    # (no per-event legend — class colors / M / T are documented in the paper text)

    out_path = OUT_DIR + f'aggressiveness_{ev}.pdf'
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f'Aggressiveness plot -> {out_path}')


for ev in EVENTS:
    plot_event_aggressiveness(ev)


# ─── Unique-config dict for the "all events triggered" scenario ─────────────
# triggered_configs[(radio, event, op)] = Counter({(combo, ttt): sample_count, ...})
# Covers every event in EVENTS, rsrp-only (matches the rest of the analysis).
# Empty cells are omitted.
def _build_norm_key(combo, ttt):
    return (tuple(float(v) for v in combo), float(ttt))


triggered_configs = {}
for _radio, _src in (('LTE', lte_dict), ('5G', fiveg_dict)):
    for _ev in EVENTS:
        for _op in OPS:
            _tuples = build_tuples(_src.get(_op, {}), _ev, tq_filter='rsrp', radio=_radio)
            _c = Counter()
            for _combo, _ttt in _tuples:
                _c[_build_norm_key(_combo, _ttt)] += 1
            if _c:
                triggered_configs[(_radio, _ev, _op)] = _c


# ─── PART 2 : Triggered (op_metric) vs HO-triggered (cache) ──────────────────
with open(PKL_HO_CACHE, 'rb') as f:
    ho_cache = pkl.load(f)

# Map cache key -> (radio, event, normalized combo type)
# Cache values: {op -> {key: pct}}  where key shape varies:
#   a5_*  : ((thr1, thr2), ttt)
#   a3_*  : (val, ttt)
#   b1    : (val, ttt)
#   a2    : (val, ttt)
HO_SOURCES = [
    # (cache_key,           radio_for_op_metric, op_metric_event, combo_kind, trigger_quantity)
    ('a3_lte_intra',        'LTE', 'A3', 'scalar', 'rsrp'),
    ('a5_lte_intra',        'LTE', 'A5', 'pair',   'rsrp'),
    ('a3_lte_intra_rsrq',   'LTE', 'A3', 'scalar', 'rsrq'),
    ('a5_lte_intra_rsrq',   'LTE', 'A5', 'pair',   'rsrq'),
    ('a3_5g_intra',         '5G',  'A3', 'scalar', 'rsrp'),
    ('a5_5g_intra',         '5G',  'A5', 'pair',   'rsrp'),
    ('b1_lte_to_5g',        '5G',  'B1', 'scalar', 'rsrp'),   # B1 stored under 5G in op_metric
    ('a2_5g_to_lte',        '5G',  'A2', 'scalar', 'rsrp'),   # A2 fires on 5G; LTE A2 removed
]

def _norm_cache_key(k, kind):
    """Normalize a cache key (combo, ttt) into ((combo_tuple), ttt) matching
    our build_tuples output."""
    if kind == 'pair':
        # cache: ((thr1, thr2), ttt)
        (combo_pair, ttt) = k
        return ((float(combo_pair[0]), float(combo_pair[1])), float(ttt))
    else:
        # cache: (val, ttt)
        (val, ttt) = k
        return ((float(val),), float(ttt))


def _norm_triggered_key(combo, ttt):
    return (tuple(float(v) for v in combo), float(ttt))


overlap_summary = {}
per_config_records = {}    # (radio, ev, op) -> list of (key, trig_count, ho_count), sorted desc by ho_count
trig_counter_by_key = {}   # (radio, ev, op) -> Counter of {(combo, ttt): trig_count}
ho_count_by_key     = {}   # (radio, ev, op) -> dict of {(combo, ttt): absolute_ho_count}

# Group HO sources by (radio, ev) so rsrp + rsrq slots for the same event
# collapse into one (combo, ttt) bucket — we lump trigger quantities together.
HO_SRC_BY_RE = {}
for _ck, _r, _e, _kind, _tq in HO_SOURCES:
    HO_SRC_BY_RE.setdefault((_r, _e), []).append((_ck, _kind))

for (radio, ev), srcs in HO_SRC_BY_RE.items():
    src = lte_dict if radio == 'LTE' else fiveg_dict
    for op in OPS:
        # HO distribution: union of pct/count across all tq slots for this (radio, ev)
        ho_counts = {}        # pct-keyed for the overlap stats
        ho_count_lookup = {}  # absolute count per normalized key
        for cache_key, kind in srcs:
            ho_per_op     = ho_cache.get(cache_key, {})
            ho_per_op_cnt = ho_cache.get(cache_key + '_count', {})
            for k, pct in ho_per_op.get(op, {}).items():
                nk = _norm_cache_key(k, kind)
                ho_counts[nk] = ho_counts.get(nk, 0.0) + pct
            for k, cnt in ho_per_op_cnt.get(op, {}).items():
                nk = _norm_cache_key(k, kind)
                ho_count_lookup[nk] = ho_count_lookup.get(nk, 0) + cnt

        # Triggered: take both rsrp and rsrq samples (tq_filter=None lumps them)
        tuples = build_tuples(src.get(op, {}), ev, tq_filter=None, radio=radio)
        trig_counter = Counter()
        for combo, ttt in tuples:
            trig_counter[_norm_triggered_key(combo, ttt)] += 1
        n_trig = sum(trig_counter.values())

        ho_keys   = set(ho_counts)
        trig_keys = set(trig_counter)
        intersect = ho_keys & trig_keys

        ho_total_pct   = sum(ho_counts.values())
        ho_in_trig_pct = sum(v for k, v in ho_counts.items() if k in trig_keys)
        trig_overlap_n   = sum(c for k, c in trig_counter.items() if k in ho_keys)
        trig_overlap_pct = 100 * trig_overlap_n / n_trig if n_trig else 0
        trig_unused_pct  = 100 - trig_overlap_pct

        overlap_summary[(radio, ev, op)] = {
            'ho_keys': len(ho_keys), 'trig_keys': len(trig_keys),
            'shared_keys': len(intersect),
            'ho_in_trig_pct': (100 * ho_in_trig_pct / ho_total_pct) if ho_total_pct else 0,
            'trig_overlap_pct': trig_overlap_pct,
            'trig_unused_pct':  trig_unused_pct,
            'n_trig': n_trig,
        }

        records = [(key, trig_counter[key], ho_count_lookup.get(key, 0))
                   for key in trig_counter]
        records.sort(key=lambda r: (-r[2], -r[1]))
        per_config_records[(radio, ev, op)] = records

        trig_counter_by_key[(radio, ev, op)] = trig_counter
        ho_count_by_key[(radio, ev, op)]     = ho_count_lookup



# Plot: per (radio, event) panel, single bar per operator showing
#   % of overall triggered samples whose (combo, TTT) is present in the HO set.
#   I.e. how dominant the HO-driving configs are within the overall triggered set.
# The triggered-vs-HO overlap plot that lived here is not used in the paper
# and has been removed. The overlap CSV above is kept: it is the underlying
# table, costs nothing extra to write, and the computation feeding it is
# shared with the per-config figures below.


# ─── Per-event per-config HO-contribution plot ───────────────────────────────
# For each (radio, event, op): take the UNION of unique (combo, ttt) keys from
# both the Triggered set AND the HO set. For each key, look up its HO count
# (0 if it never produced an HO). Sort by HO count desc, plot rank vs count.
def _build_per_op_records(key_sets):
    """key_sets: dict op -> (trig_dict, ho_dict). Returns per_op records ready
    for the overlay-kink renderer below."""
    per_op = {}
    for op, (trig, ho) in key_sets.items():
        all_keys = set(trig) | set(ho)
        if not all_keys:
            continue
        records = sorted([(key, ho.get(key, 0)) for key in all_keys],
                         key=lambda r: -r[1])
        ho_counts = [r[1] for r in records]
        total = sum(ho_counts)
        pct_counts = [100.0 * c / total for c in ho_counts] if total else [0.0] * len(ho_counts)
        per_op[op] = {
            'ranks':      np.arange(1, len(records) + 1),
            'counts':     ho_counts,
            'pct_counts': pct_counts,
            'total':      total,
            'unique':     len(records),
        }
    return per_op


def _render_overlay_kink_plot(per_op, out_path):
    """Render the overlay-with-kink plot for a per_op records dict."""
    if not per_op:
        return
    op_color_map = OP_COLORS
    # Draw largest in back, smallest in front so the smaller-operator outlines
    # aren't fully buried under the bigger operator's white fill.
    ops_sorted = sorted(per_op.keys(), key=lambda op: -per_op[op]['total'])
    EDGE_LW = 1.4
    max_rank  = max(d['unique'] for d in per_op.values())
    max_count = max(max(d['counts']) for d in per_op.values()) or 1
    max_pct   = max(max(d['pct_counts']) for d in per_op.values()) or 1.0
    # Cutoff for the kink stays based on absolute counts — measures whether
    # the contribution is meaningful in the raw HO sense, not per-operator %.
    cutoff = max(2, int(max_count * 0.01))
    last_nz = max(
        (max((i + 1 for i, c in enumerate(d['counts']) if c >= cutoff), default=1))
        for d in per_op.values()
    )
    need_kink = max_rank > last_nz + 1

    # Y-axis: % of each operator's total HOs (so every operator's bars sum to 100%).
    # Adaptive ceiling — pick a nice integer step so the tick grid sits at
    # round percentages for whatever range this particular plot needs.
    if max_pct <= 5:
        step = 1
    elif max_pct <= 10:
        step = 2
    elif max_pct <= 25:
        step = 5
    elif max_pct <= 50:
        step = 10
    else:
        step = 25
    y_top = float(math.ceil(max_pct / step) * step)
    y_ticks = list(range(0, int(y_top) + 1, step))
    y_ticklabels = [f'{v}%' for v in y_ticks]

    def _draw(ax, label_legend=True):
        for op in ops_sorted:
            d = per_op[op]
            ax.bar(d['ranks'], d['pct_counts'], width=1.0,
                   facecolor='none',
                   edgecolor=op_color_map[op], linewidth=EDGE_LW,
                   label=op if label_legend else None)

    if need_kink:
        fig, (ax_l, ax_r) = plt.subplots(
            1, 2, figsize=(4.0, 2.6),
            gridspec_kw={'width_ratios': [9, 1.6], 'wspace': 0.18},
            sharey=True)
        _draw(ax_l, label_legend=True)
        _draw(ax_r, label_legend=False)
        ax_l.set_xlim(0.5, last_nz + 0.5)
        ax_r.set_xlim(max_rank - 0.5, max_rank + 0.5)
        ax_l.spines['right'].set_visible(False)
        ax_r.spines['left'].set_visible(False)
        ax_r.tick_params(left=False, labelleft=False)
        if last_nz >= 3:
            ax_l.set_xticks([1, max(1, last_nz // 2), last_nz])
        else:
            ax_l.set_xticks(list(range(1, last_nz + 1)))
        ax_r.set_xticks([max_rank])
        d_mark = 0.6
        kwargs = dict(marker=[(-1, -d_mark), (1, d_mark)], markersize=8,
                      linestyle='none', color='k', mec='k', mew=1, clip_on=False)
        ax_l.plot([1, 1], [0, 1], transform=ax_l.transAxes, **kwargs)
        ax_r.plot([0, 0], [0, 1], transform=ax_r.transAxes, **kwargs)
        ax_l.set_ylim(0, y_top)
        ax_l.set_yticks(y_ticks)
        ax_l.set_yticklabels(y_ticklabels)
        ax_l.set_ylabel('% of Handovers', fontsize=12, fontweight='bold')
        for ax in (ax_l, ax_r):
            ax.grid(axis='y', alpha=0.35, linewidth=0.4)
            ax.set_axisbelow(True)
            ax.tick_params(labelsize=10)
        ax_l.set_xlabel('Configuration ranking',
                        fontsize=12, fontweight='bold', labelpad=6)
        ax_l.legend(loc='upper right', fontsize=10, framealpha=0.92)
        fig.tight_layout()
    else:
        fig, ax = plt.subplots(figsize=(3.6, 2.6), constrained_layout=True)
        _draw(ax, label_legend=True)
        ax.set_xlim(0.5, max_rank + 0.5)
        ax.set_ylim(0, y_top)
        if max_rank >= 3:
            ax.set_xticks([1, max(1, max_rank // 2), max_rank])
        else:
            ax.set_xticks(list(range(1, max_rank + 1)))
        ax.set_yticks(y_ticks)
        ax.set_yticklabels(y_ticklabels)
        ax.set_xlabel('Configuration ranking',
                      fontsize=12, fontweight='bold', labelpad=6)
        ax.set_ylabel('% of Handovers', fontsize=12, fontweight='bold')
        ax.grid(axis='y', alpha=0.35, linewidth=0.4)
        ax.set_axisbelow(True)
        ax.tick_params(labelsize=10)
        ax.legend(loc='upper right', fontsize=10, framealpha=0.92)

    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f'HO-contribution plot -> {out_path}')


def plot_ho_contribution_per_config():
    """One panel per (event, radio) with all 3 operators overlaid."""
    cells = set(trig_counter_by_key) | set(ho_count_by_key)
    ev_radio_pairs = sorted({(ev, r) for (r, ev, _) in cells})
    for ev, radio in ev_radio_pairs:
        key_sets = {op: (trig_counter_by_key.get((radio, ev, op), {}),
                         ho_count_by_key.get((radio, ev, op),     {}))
                    for op in OPS}
        per_op = _build_per_op_records(key_sets)
        _render_overlay_kink_plot(
            per_op,
            OUT_DIR + f'ho_contribution_per_config_{ev}_{radio}.pdf'
        )


def plot_ho_contribution_overall_per_radio():
    """One overall plot per radio: aggregate (combo, ttt) keys ACROSS all
    events for that radio so each entry is uniquely identified by
    (event, combo, ttt). Plots 3 operators overlaid."""
    cells = set(trig_counter_by_key) | set(ho_count_by_key)
    radios_present = sorted({r for (r, _, _) in cells})
    for radio in radios_present:
        events_for_radio = sorted({ev for (r, ev, _) in cells if r == radio})
        key_sets = {}
        for op in OPS:
            trig_combined, ho_combined = {}, {}
            for ev in events_for_radio:
                trig = trig_counter_by_key.get((radio, ev, op), {})
                ho   = ho_count_by_key.get((radio, ev, op),     {})
                for k, c in trig.items():
                    trig_combined[(ev,) + (k,)] = c
                for k, c in ho.items():
                    ho_combined[(ev,) + (k,)] = c
            key_sets[op] = (trig_combined, ho_combined)
        per_op = _build_per_op_records(key_sets)
        _render_overlay_kink_plot(
            per_op,
            OUT_DIR + f'ho_contribution_overall_{radio}.pdf'
        )


plot_ho_contribution_per_config()
plot_ho_contribution_overall_per_radio()


# ─── Printed summaries ───────────────────────────────────────────────────────
print('\nAggressiveness (% of all samples):')
print('-' * 100)
print(f'{"Radio":<5s} {"TQ":<5s} {"Op":<10s} {"Ev":<3s} {"N":>8s}  '
      f'{"Aggr%":>6s}  {"Mod%":>6s}  {"Cons%":>6s}')
print('-' * 100)
for (radio, tq, op, ev), b in agg_counts.items():
    n = agg_total[(radio, tq, op, ev)]
    if n == 0:
        continue
    print(f'{radio:<5s} {tq:<5s} {op:<10s} {ev:<3s} {n:>8,d}  '
          f'{100*b["aggressive"]/n:>5.1f}%  '
          f'{100*b["moderate"]/n:>5.1f}%  '
          f'{100*b["conservative"]/n:>5.1f}%')
print('-' * 100)

print('\nTriggered vs HO overlap (rsrp + rsrq lumped together):')
print('-' * 110)
print(f'{"Radio":<5s} {"Ev":<3s} {"Op":<10s} {"HO uniq":>7s} {"Trig uniq":>9s} {"Shared":>6s}  '
      f'{"HO->trig%":>9s}  {"Trig in HO%":>11s}  {"Unneeded%":>9s}  {"N_trig":>9s}')
print('-' * 110)
for k, s in overlap_summary.items():
    radio, ev, op = k
    print(f'{radio:<5s} {ev:<3s} {op:<10s} {s["ho_keys"]:>7d} {s["trig_keys"]:>9d} '
          f'{s["shared_keys"]:>6d}  {s["ho_in_trig_pct"]:>8.1f}%  '
          f'{s["trig_overlap_pct"]:>10.1f}%  {s["trig_unused_pct"]:>8.1f}%  '
          f'{s["n_trig"]:>9,d}')
print('-' * 110)
print('\nDone.')
