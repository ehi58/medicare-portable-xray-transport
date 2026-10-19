"""The three analyses and their controls, as plain functions over the snapshot.

Every function takes the snapshot DataFrame (see ``fetch.py``) and returns
plain numbers or small frames, so the notebook can show the working and the
tests can run the same code on synthetic data.

Vocabulary used throughout:

* a *line* is one ``Tot_Srvcs`` unit on a transport code. R0070 and R0075 are
  billed once per patient per day, so a line is one patient visit.
* a *biller* is one rendering NPI. A company can bill under several.
* a *pair* is one biller in one setting (facility ``F`` or non-facility ``O``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SOLO, SHARED, SETUP = "R0070", "R0075", "Q0092"
TRANSPORT = (SOLO, SHARED)

# The proration rule pays an R0075 line the R0070 fee divided by the number of
# patients at the stop, with the divisor capped at six. So the ratio of a
# biller's average R0075 allowed amount to its R0070 amount must lie in
# [1/6, 1/2]. The tolerance absorbs rounding in CMS's published averages.
RATIO_LOW, RATIO_HIGH, RATIO_TOL_LOW, RATIO_TOL_HIGH = 1 / 6, 1 / 2, 0.01, 0.02


def lines(df: pd.DataFrame, code: str, setting: str | None = None) -> int:
    sub = df[df.hcpcs == code]
    if setting is not None:
        sub = sub[sub.setting == setting]
    return int(sub.services.sum())


# ── controls ────────────────────────────────────────────────────────────────


@dataclass
class Control:
    name: str
    expected: str
    measured: str
    passed: bool


def controls(df: pd.DataFrame) -> list[Control]:
    """Checks run before any finding is computed.

    The expected values are the ones recorded when the file was first pulled
    on 2026-09-15. If CMS revises the file, these fail first and say so.
    """
    t70, t75, tq = lines(df, SOLO), lines(df, SHARED), lines(df, SETUP)
    transport = df[df.hcpcs.isin(TRANSPORT)]
    bd = {c: df[df.hcpcs == c].beneficiary_days.sum() for c in TRANSPORT}
    known = df[
        (df.hcpcs == SOLO)
        & (df.setting == "O")
        & (df.services == 994)
        & (df.beneficiaries == 758)
    ]
    out = [
        Control("rows in the pull", "875", f"{len(df)}", len(df) == 875),
        Control(
            "transport + set-up lines",
            "2,414,549",
            f"{t70 + t75 + tq:,}",
            t70 + t75 + tq == 2_414_549,
        ),
        Control(
            "a known row from the first pull is present (R0070, non-facility, 758 beneficiaries, 994 lines)",
            "found",
            "found" if len(known) == 1 else f"{len(known)} matches",
            len(known) == 1,
        ),
        Control(
            "smallest beneficiary count in any row (CMS suppresses cells under 11)",
            "11",
            f"{int(df.beneficiaries.min())}",
            int(df.beneficiaries.min()) == 11,
        ),
        Control(
            "R0070 lines per beneficiary-day (one transport line per patient per day)",
            "≈ 1.00",
            f"{t70 / bd[SOLO]:.3f}",
            abs(t70 / bd[SOLO] - 1) < 0.01,
        ),
        Control(
            "R0075 lines per beneficiary-day",
            "≈ 1.00",
            f"{t75 / bd[SHARED]:.3f}",
            abs(t75 / bd[SHARED] - 1) < 0.01,
        ),
        Control(
            "billers on a transport code = union of the two codes' billers",
            "287",
            f"{transport.biller.nunique()}",
            transport.biller.nunique() == 287,
        ),
    ]
    return out


# ── analysis 1: solo trips versus shared stops ──────────────────────────────


def solo_share(df: pd.DataFrame) -> dict:
    t70, t75 = lines(df, SOLO), lines(df, SHARED)
    by_setting = {}
    for s in ("O", "F"):
        a, b = lines(df, SOLO, s), lines(df, SHARED, s)
        by_setting[s] = {
            "solo": a,
            "shared": b,
            "solo_share": a / (a + b),
            "share_of_all_lines": (a + b) / (t70 + t75),
        }
    pairs = biller_pairs(df)
    both = pairs.dropna(subset=["solo_lines", "shared_lines"])
    per_pair = both.solo_lines / (both.solo_lines + both.shared_lines)
    # Per biller, every setting together, a biller with no R0075 row counted
    # as 100% solo. That is the population a "median biller" refers to.
    b = per_biller_codes(df)
    return {
        "solo_lines": t70,
        "shared_lines": t75,
        "solo_share": t70 / (t70 + t75),
        "by_setting": by_setting,
        "pairs_with_both": len(both),
        "pairs_solo_only": int(pairs.shared_lines.isna().sum()),
        "pairs_shared_only": int(pairs.solo_lines.isna().sum()),
        "pair_solo_share_median": float(np.quantile(per_pair, 0.5)),
        "pair_solo_share_q1": float(np.quantile(per_pair, 0.25)),
        "pair_solo_share_q3": float(np.quantile(per_pair, 0.75)),
        "billers": len(b),
        "billers_no_shared_line": int((b.shared_lines == 0).sum()),
        "biller_solo_share_median": float(np.quantile(b.solo_share, 0.5)),
        "biller_solo_share_q1": float(np.quantile(b.solo_share, 0.25)),
    }


def per_biller_codes(df: pd.DataFrame) -> pd.DataFrame:
    """Solo and shared lines per biller, every setting together; a missing code is 0."""
    t = df[df.hcpcs.isin(TRANSPORT)]
    w = t.pivot_table(index="biller", columns="hcpcs", values="services", aggfunc="sum", fill_value=0)
    w = w.reindex(columns=list(TRANSPORT), fill_value=0).rename(columns={SOLO: "solo_lines", SHARED: "shared_lines"})
    w["lines"] = w.solo_lines + w.shared_lines
    w["solo_share"] = w.solo_lines / w.lines
    return w.sort_values("lines", ascending=False).reset_index()


def solo_share_by_size(df: pd.DataFrame) -> pd.DataFrame:
    """Pooled solo share of each biller decile, billers ranked by transport lines."""
    b = per_biller_codes(df)
    size = int(np.ceil(len(b) / 10))
    rows = []
    for d in range(10):
        s = b.iloc[d * size : (d + 1) * size]
        if s.empty:
            continue
        rows.append({"decile": d + 1, "billers": len(s), "solo_share": s.solo_lines.sum() / s.lines.sum()})
    return pd.DataFrame(rows)


def biller_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """One row per biller and setting, with both codes' lines and allowed amounts."""
    t = df[df.hcpcs.isin(TRANSPORT)]
    wide = t.pivot_table(
        index=["biller", "setting"],
        columns="hcpcs",
        values=["services", "avg_allowed"],
        aggfunc="first",
    )
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    wide = wide.rename(
        columns={
            f"services_{SOLO}": "solo_lines",
            f"services_{SHARED}": "shared_lines",
            f"avg_allowed_{SOLO}": "solo_allowed",
            f"avg_allowed_{SHARED}": "shared_allowed",
        }
    )
    return wide.reset_index()


# ── analysis 2: implied patients per shared stop ────────────────────────────


def implied_stop_size(solo_allowed: float, shared_allowed: float) -> float:
    """Mean patients per shared stop implied by the proration rule.

    For one biller in one setting, let F be the R0070 allowed amount and n_i the
    size of the stop behind shared line i (T lines over S stops). Each R0075
    line is allowed F / n_i, so its average is (1/T)·Σ F/n_i. The n lines of a
    stop each contribute 1/n, so Σ 1/n_i = S and the average is F·S/T. Hence
    F / average = T/S, the mean number of patients per shared stop.

    It is exact under three conditions: every stop has six patients or fewer
    (larger stops price as six, so the estimate is then a floor); both codes
    are priced on the same fee basis; and every patient behind a divisor is in
    this file. If the divisor counts patients of every payer, a Medicare line
    at a stop of n contributes 1/n while only the Medicare patients appear, and
    the ratio becomes the Medicare-line-weighted harmonic mean of the TOTAL
    stop size rather than the mean number of Medicare patients per stop.
    """
    return solo_allowed / shared_allowed


def stop_sizes(df: pd.DataFrame) -> dict:
    pairs = biller_pairs(df).dropna(subset=["solo_lines", "shared_lines"]).copy()
    pairs["ratio"] = pairs.shared_allowed / pairs.solo_allowed
    pairs["implied"] = implied_stop_size(pairs.solo_allowed, pairs.shared_allowed)
    ok = (pairs.ratio >= RATIO_LOW - RATIO_TOL_LOW) & (pairs.ratio <= RATIO_HIGH + RATIO_TOL_HIGH)
    used, excluded = pairs[ok], pairs[~ok]

    def weighted(sub: pd.DataFrame) -> float:
        # Pool allowed dollars: Σ F·w / Σ avg75·w, with w the pair's shared lines.
        return float((sub.solo_allowed * sub.shared_lines).sum() / (sub.shared_allowed * sub.shared_lines).sum())

    covered = used.shared_lines.sum()
    bands = []
    for lo, hi in [(1.9, 2.5), (2.5, 3.5), (3.5, 4.5), (4.5, 5.5), (5.5, 7.0)]:
        b = used[(used.implied >= lo) & (used.implied < hi)]
        bands.append({"band": f"{lo}–{hi}", "pairs": len(b), "share_of_shared_lines": b.shared_lines.sum() / covered})
    by_setting = {
        s: {
            "pairs": int((used.setting == s).sum()),
            "median": float(np.quantile(used[used.setting == s].implied, 0.5)),
            "weighted": weighted(used[used.setting == s]),
        }
        for s in ("O", "F")
    }
    return {
        "pairs": pairs,
        "used": used,
        "n_pairs": len(pairs),
        "n_used": len(used),
        "excluded_ratios": sorted(round(r, 3) for r in excluded.ratio),
        "median": float(np.quantile(used.implied, 0.5)),
        "q1": float(np.quantile(used.implied, 0.25)),
        "q3": float(np.quantile(used.implied, 0.75)),
        "min": float(used.implied.min()),
        "max": float(used.implied.max()),
        "weighted": weighted(used),
        "covered_share": float(covered / lines(df, SHARED)),
        "at_floor": int((used.implied >= 5.5).sum()),
        "bands": pd.DataFrame(bands),
        "by_setting": by_setting,
    }


def merge_sparse_bins(values, edges: list[float], min_count: int = 3) -> list[float]:
    """Histogram edges with no bin holding between 1 and ``min_count - 1`` values.

    Walks the fixed edges left to right and closes a bin only once it holds at
    least ``min_count`` values, so a sparse bin is merged into its neighbours.
    A sparse remainder at the right end joins the last closed bin. A bin of a
    handful of pairs would let a reader pick out one biller's value.
    """
    counts, _ = np.histogram(values, bins=edges)
    out, run = [edges[0]], 0
    for i, n in enumerate(counts):
        run += int(n)
        if run >= min_count:
            out.append(edges[i + 1])
            run = 0
    if out[-1] != edges[-1]:
        if run == 0 or len(out) == 1:
            out.append(edges[-1])
        else:
            out[-1] = edges[-1]
    return out


def solo_share_of_trips(df: pd.DataFrame, patients_per_shared_stop: float) -> float:
    """Visits are not trips: a shared stop is one trip to a location for several visits.

    "Trip" is the code descriptors' unit: R0070 and R0075 are billed per trip
    to a facility or location. One van run can chain several such trips.
    """
    t70, t75 = lines(df, SOLO), lines(df, SHARED)
    return t70 / (t70 + t75 / patients_per_shared_stop)


# ── analysis 3: concentration of transport billing ──────────────────────────


def per_biller(df: pd.DataFrame) -> pd.DataFrame:
    t = df[df.hcpcs.isin(TRANSPORT)].assign(dollars=lambda d: d.services * d.avg_allowed)
    return (
        t.groupby("biller")
        .agg(lines=("services", "sum"), dollars=("dollars", "sum"))
        .sort_values("lines", ascending=False)
        .reset_index()
    )


def gini(values: np.ndarray) -> float:
    v = np.sort(np.asarray(values, dtype=float))
    n = len(v)
    cum = np.cumsum(v)
    return float(1 - 2 * (cum.sum() / (n * cum[-1])) + 1 / n)


def concentration(df: pd.DataFrame) -> dict:
    b = per_biller(df)
    n, tl, td = len(b), b.lines.sum(), b.dollars.sum()
    by_dollars = b.sort_values("dollars", ascending=False)
    size = int(np.ceil(n / 10))
    deciles = []
    for d in range(10):
        s = b.iloc[d * size : (d + 1) * size]
        if s.empty:
            continue
        deciles.append(
            {
                "decile": d + 1,
                "billers": len(s),
                "share_of_lines": s.lines.sum() / tl,
                "share_of_dollars": s.dollars.sum() / td,
                # The smallest biller's lines bound the decile from below. The
                # largest is not reported: in the first decile it is the single
                # largest biller's count.
                "lines_low": int(s.lines.min()),
            }
        )
    small = b[b.lines < 1000]
    return {
        "per_biller": b,
        "billers": n,
        "lines": int(tl),
        "dollars": float(td),
        "top10_lines": b.lines.head(10).sum() / tl,
        "top10_dollars": by_dollars.dollars.head(10).sum() / td,
        "top25_lines": b.lines.head(25).sum() / tl,
        "top50_lines": b.lines.head(50).sum() / tl,
        "median_lines": float(np.quantile(b.lines, 0.5)),
        "median_dollars": float(np.quantile(b.dollars, 0.5)),
        "q1_lines": float(np.quantile(b.lines, 0.25)),
        "q3_lines": float(np.quantile(b.lines, 0.75)),
        "under_1000": len(small),
        "under_1000_share_of_lines": small.lines.sum() / tl,
        "over_10000": int((b.lines >= 10_000).sum()),
        "gini": gini(b.lines.to_numpy()),
        "deciles": pd.DataFrame(deciles),
    }
