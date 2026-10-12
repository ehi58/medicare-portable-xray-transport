"""One chart per finding. Each function returns the figure and, given a path, saves it."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

INK = "#1f2933"
MUTED = "#7b8794"
SOLO_C = "#2a6f97"
SHARED_C = "#a9cce3"
ACCENT = "#c0392b"

plt.rcParams.update(
    {
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "figure.dpi": 110,
    }
)

SOURCE = "Source: CMS Medicare Physician & Other Practitioners by Provider and Service, CY2024 (fee-for-service Part B)."


def _finish(fig, path: str | Path | None):
    fig.text(0.01, 0.01, SOURCE, fontsize=7.5, color=MUTED, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    if path is not None:
        fig.savefig(path, dpi=150, bbox_inches="tight")
    return fig


def solo_vs_shared(solo_lines: int, shared_lines: int, trip_solo_share: float, path=None):
    """Finding 1: the split counted as patient visits and as van trips."""
    visit_solo = solo_lines / (solo_lines + shared_lines)
    rows = [("Van trips (derived)", trip_solo_share), ("Patient visits", visit_solo)]
    fig, ax = plt.subplots(figsize=(8, 2.8))
    for i, (label, s) in enumerate(rows):
        ax.barh(i, s, color=SOLO_C, height=0.55)
        ax.barh(i, 1 - s, left=s, color=SHARED_C, height=0.55)
        ax.text(s / 2, i, f"{s:.0%} one patient", ha="center", va="center", color="white", fontweight="bold")
        if 1 - s >= 0.25:
            ax.text(s + (1 - s) / 2, i, f"{1 - s:.0%} shared stop", ha="center", va="center", color=INK)
        else:
            ax.text(1.01, i, f"{1 - s:.0%} shared stop", ha="left", va="center", color=INK)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows])
    ax.set_xlim(0, 1.2)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.set_title(
        "Most portable x-ray transport is a van sent to one patient",
        loc="left",
        fontsize=12,
        color=INK,
    )
    return _finish(fig, path)


def stop_size_distribution(used: pd.DataFrame, median: float, weighted: float, path=None):
    """Finding 2: implied patients per shared stop across biller-setting pairs."""
    fig, ax = plt.subplots(figsize=(8, 3.6))
    bins = [x / 10 for x in range(18, 62, 2)]
    ax.hist(used.implied, bins=bins, color=SOLO_C, edgecolor="white")
    ax.axvline(median, color=INK, linestyle="--", linewidth=1, label=f"median biller-setting pair: {median:.2f}")
    ax.axvline(weighted, color=ACCENT, linestyle="-", linewidth=1.2, label=f"weighted by shared-stop visits: {weighted:.2f}")
    ax.legend(loc="upper center", bbox_to_anchor=(0.62, 0.95), frameon=False, fontsize=9)
    top = ax.get_ylim()[1]
    ax.axvspan(6, 6.2, color=MUTED, alpha=0.25)
    ax.text(5.95, top * 0.5, "rule caps\nthe divisor at 6", ha="right", color=MUTED, fontsize=8)
    ax.set_xlim(1.8, 6.2)
    ax.set_xlabel("Implied mean patients per shared stop (one biller in one setting)")
    ax.set_ylabel("Biller-setting pairs")
    ax.set_title(f"A shared stop is usually two or three patients ({len(used)} pairs)", loc="left", fontsize=12, color=INK)
    return _finish(fig, path)


def concentration_deciles(deciles: pd.DataFrame, path=None):
    """Finding 3: share of transport lines by biller decile (largest first).

    Deciles, not a Lorenz curve: a Lorenz curve's last step is the single
    largest biller's share, which this project does not publish.
    """
    fig, ax = plt.subplots(figsize=(8, 3.6))
    x = deciles.decile.astype(str)
    ax.bar(x, deciles.share_of_lines, color=[SOLO_C] + [SHARED_C] * (len(deciles) - 1))
    for xi, v in zip(x, deciles.share_of_lines):
        ax.text(xi, v + 0.01, f"{v:.1%}" if v >= 0.01 else f"{v:.2%}", ha="center", fontsize=8, color=INK)
    ax.set_ylim(0, max(deciles.share_of_lines) * 1.15)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Biller decile by transport lines (1 = largest tenth)")
    ax.set_title(
        f"The largest tenth of billers ({int(deciles.billers.iloc[0])}) bill {deciles.share_of_lines.iloc[0]:.0%} of transport visits",
        loc="left",
        fontsize=12,
        color=INK,
    )
    return _finish(fig, path)
