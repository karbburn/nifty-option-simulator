"""The five chart deliverables, saved as PNGs."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from nifty_gap.reporting.metrics import REASON_ORDER

_LOW_SAMPLE = 30
_SIDE_COLORS = {"CE": "#2e7d32", "PE": "#c62828"}


def _save(fig, path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)


def probability_chart(table: pd.DataFrame, path) -> None:
    t = table.sort_values("weekday_pair")
    pairs = t["weekday_pair"]
    x = range(len(pairs))
    colors = [_SIDE_COLORS[s] for s in t["side"]]
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, (p, c) in enumerate(zip(t["p_up"], colors)):
        hatch = "//" if t["n"].iloc[i] < _LOW_SAMPLE else None
        ax.bar(i, p, color=c, alpha=0.72, width=0.55, hatch=hatch)
    ax.errorbar(
        list(x),
        t["p_up"],
        yerr=[t["p_up"] - t["ci_low"], t["ci_high"] - t["p_up"]],
        fmt="none",
        ecolor="black",
        capsize=3,
    )
    ax.axhline(0.5, color="grey", linestyle="--", linewidth=1)
    ax.text(len(pairs) - 0.4, 0.5, "50%", color="grey", ha="right", va="center")
    for i, (n, p) in enumerate(zip(t["n"], t["p_up"])):
        ax.text(i, p + 0.02, f"n={int(n)}", ha="center", fontsize=8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(pairs, rotation=20, ha="right")
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("P(gap up)")
    ax.set_title("Weekday-pair gap probability with 95% Wilson CI")
    _save(fig, path)


def exit_reasons_chart(trades: pd.DataFrame, path) -> None:
    counts = trades["exit_reason"].value_counts()
    avg = trades.groupby("exit_reason")["pnl"].mean()
    labels = [r for r in REASON_ORDER if r in counts.index]
    if not labels:
        labels = list(counts.index)
    fig, ax = plt.subplots(figsize=(9, 5))
    if not labels:
        ax.text(0.5, 0.5, "No trades to display", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        ax.set_title("Exit reason distribution with average P&L per reason")
        _save(fig, path)
        return
    counts_ax = ax
    counts_ax.bar(labels, [counts[r] for r in labels], color="#455a64", alpha=0.85)
    for i, r in enumerate(labels):
        counts_ax.text(i, counts[r] + 1, f"avg ₹{avg[r]:,.0f}", ha="center", fontsize=8)
        counts_ax.text(i, counts[r] / 2, f"{counts[r]}", ha="center", color="white", fontsize=9)
    counts_ax.set_ylabel("Number of trades")
    counts_ax.set_ylim(0, counts.max() * 1.15)
    counts_ax.set_xticklabels(labels, rotation=20, ha="right")
    counts_ax.set_title("Exit reason distribution with average P&L per reason")
    _save(fig, path)


def _pair_cumulative_equity(trades: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    t = trades.copy()
    t["exit_date"] = pd.to_datetime(t["exit_date"])
    pivot = t.pivot_table(index="exit_date", columns="pair", values="pnl", aggfunc="sum", fill_value=0).sort_index().cumsum()
    pivot = pivot.reindex(dates, method="ffill").fillna(0.0)
    return pivot


def equity_chart(equity: pd.DataFrame, trades: pd.DataFrame, path) -> None:
    eq = equity.set_index("Date")["equity"]
    peak = eq.cummax()
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    ax.plot(eq.index, eq.values, color="#1565c0", linewidth=1.6, label="strategy")
    ax.fill_between(eq.index, eq.values, peak.values, where=eq.values <= peak.values, color="#c62828", alpha=0.18, label="drawdown")
    ax.axhline(0, color="grey", linewidth=0.8)
    ax.legend(loc="best", fontsize=8)
    ax.set_ylabel("Portfolio equity (₹)")
    ax.set_title("Mark-to-market portfolio equity with max-drawdown shading")

    pivot = _pair_cumulative_equity(trades, eq.index)
    for pair in pivot.columns:
        ax2.plot(pivot.index, pivot[pair].values, label=pair, linewidth=1.2)
    ax2.axhline(0, color="grey", linewidth=0.8)
    ax2.legend(loc="best", fontsize=8)
    ax2.set_ylabel("Cumulative realized P&L (₹)")
    ax2.set_xlabel("Date")
    ax2.set_title("Per-pair cumulative realized P&L")
    _save(fig, path)


def benchmark_chart(equity_ladder: pd.DataFrame, equity_hold: pd.DataFrame, path) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    el = equity_ladder.set_index("Date")["equity"]
    eh = equity_hold.set_index("Date")["equity"]
    ax.plot(el.index, el.values, color="#1565c0", linewidth=1.6, label="ladder")
    ax.plot(eh.index, eh.values, color="#757575", linewidth=1.4, linestyle="--", label="hold-to-expiry (benchmark)")
    ax.axhline(0, color="grey", linewidth=0.8)
    ax.legend(loc="best", fontsize=9)
    ax.set_ylabel("Portfolio equity (₹)")
    ax.set_xlabel("Date")
    ax.set_title("Ladder strategy vs no-ladder benchmark (same entry universe)")
    _save(fig, path)


def oos_chart(oos: pd.DataFrame, path) -> None:
    o = oos.sort_values("weekday_pair")
    x = range(len(o))
    width = 0.38
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar([i - width / 2 for i in x], o["p_up"], width, color="#1976d2", alpha=0.8, label="table (IS p_up)")
    ax.errorbar([i - width / 2 for i in x], o["p_up"], yerr=[o["p_up"] - o["ci_low"], o["ci_high"] - o["p_up"]], fmt="none", ecolor="black", capsize=3)
    ax.bar([i + width / 2 for i in x], o["realized_p_up"], width, color="#f9a825", alpha=0.8, label="realized (OOS)")
    ax.errorbar(
        [i + width / 2 for i in x],
        o["realized_p_up"],
        yerr=[o["realized_p_up"] - o["realized_ci_low"], o["realized_ci_high"] - o["realized_p_up"]],
        fmt="none",
        ecolor="black",
        capsize=3,
    )
    ax.axhline(0.5, color="grey", linestyle="--", linewidth=1)
    ax.set_xticks(list(x))
    ax.set_xticklabels(o["weekday_pair"], rotation=20, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Gap-up probability")
    ax.set_title("IS table probability vs realized OOS win rate (Wilson CIs)")
    ax.legend(loc="best", fontsize=9)
    _save(fig, path)


def render_all(table: pd.DataFrame, trades: pd.DataFrame, equity: pd.DataFrame,
               equity_hold: pd.DataFrame, oos: pd.DataFrame, out_dir) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = [
        out / "probability.png",
        out / "exit_reasons.png",
        out / "equity.png",
        out / "benchmark.png",
        out / "oos.png",
    ]
    probability_chart(table, paths[0])
    exit_reasons_chart(trades, paths[1])
    equity_chart(equity, trades, paths[2])
    benchmark_chart(equity, equity_hold, paths[3])
    oos_chart(oos, paths[4])
    return paths