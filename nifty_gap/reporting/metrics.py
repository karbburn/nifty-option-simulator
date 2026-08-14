"""Phase 8: metrics per plan §5.6, computed from trade/equity frames."""

from __future__ import annotations

import datetime as dt
import json
import math
import subprocess
from pathlib import Path

import pandas as pd

ANNUALIZATION = 252
REASON_ORDER = ["SL", "floor_3", "floor_5", "floor_10", "target_15", "expiry"]


def trade_stats(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {
            "n_trades": 0,
            "total_pnl": 0.0,
            "win_rate": float("nan"),
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": float("nan"),
            "exit_reasons": [],
        }
    pnl = trades["pnl"]
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    gross_win = float(wins.sum()) if wins.size else 0.0
    gross_loss = float(abs(losses.sum())) if losses.size else 0.0
    if gross_loss > 0:
        profit_factor = gross_win / gross_loss
    elif gross_win > 0:
        profit_factor = math.inf
    else:
        profit_factor = float("nan")

    reasons = []
    for reason, grp in trades.groupby("exit_reason", sort=False)["pnl"]:
        if reason not in REASON_ORDER:
            continue
        reasons.append(
            {
                "exit_reason": reason,
                "count": int(grp.size),
                "pct": float(grp.size / len(trades) * 100),
                "avg_pnl": float(grp.mean()),
            }
        )
    return {
        "n_trades": int(len(trades)),
        "total_pnl": float(pnl.sum()),
        "win_rate": float((pnl > 0).mean()),
        "avg_win": float(wins.mean()) if wins.size else 0.0,
        "avg_loss": float(losses.mean()) if losses.size else 0.0,
        "profit_factor": profit_factor,
        "exit_reasons": reasons,
    }


def equity_stats(equity: pd.DataFrame) -> dict:
    if equity.empty:
        return {"n_days": 0, "final_equity": 0.0, "max_drawdown": 0.0, "sharpe": float("nan")}
    eq = equity["equity"].astype(float)
    n = len(eq)
    final = float(eq.iloc[-1])
    peak = eq.cummax()
    drawdown = peak - eq
    max_dd = float(drawdown.max())
    dd_pct = (peak - eq) / peak.where(peak > 0)
    max_dd_pct = float(dd_pct.max()) if dd_pct.notna().any() else 0.0

    returns = eq.diff().dropna()
    if returns.size > 1 and returns.std(ddof=1) > 0:
        sharpe = float(returns.mean() / returns.std(ddof=1) * math.sqrt(ANNUALIZATION))
    else:
        sharpe = float("nan")
    return {
        "n_days": n,
        "final_equity": final,
        "max_drawdown": max_dd,
        "max_drawdown_pct": max_dd_pct,
        "sharpe_annualized": sharpe,
        "annualization": ANNUALIZATION,
        "sharpe_note": "mean/std of daily-dollar equity changes × √252 (portfolio MTM; ties/flat count as zero)",
    }


def pair_stats(trades: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    t = trades.copy()
    t["win"] = (t["pnl"] > 0).astype(int)
    agg = t.groupby("pair").agg(traded=("pnl", "size"), wins=("win", "sum"), total_pnl=("pnl", "sum")).reset_index()
    agg["win_rate"] = agg["wins"] / agg["traded"]
    out = table[["weekday_pair", "n", "p_up", "ci_low", "ci_high", "side", "tradeable"]].merge(
        agg, left_on="weekday_pair", right_on="pair", how="left"
    ).drop(columns="pair")
    out["traded"] = out["traded"].fillna(0).astype(int)
    out["wins"] = out["wins"].fillna(0).astype(int)
    out["win_rate"] = out["win_rate"].fillna(float("nan"))
    out["total_pnl"] = out["total_pnl"].fillna(0.0)
    return out


def oos_summary(oos: pd.DataFrame) -> list[dict]:
    return [
        {
            "weekday_pair": r.weekday_pair,
            "side": r.side,
            "n_in": int(r.n),
            "p_up": float(r.p_up),
            "ci_low": float(r.ci_low),
            "ci_high": float(r.ci_high),
            "n_oos": int(r.n_oos) if pd.notna(r.n_oos) else 0,
            "realized_p_up": float(r.realized_p_up) if pd.notna(r.realized_p_up) else float("nan"),
            "realized_ci_low": float(r.realized_ci_low) if pd.notna(r.realized_ci_low) else float("nan"),
            "realized_ci_high": float(r.realized_ci_high) if pd.notna(r.realized_ci_high) else float("nan"),
        }
        for _, r in oos.iterrows()
    ]


def provenance() -> dict:
    sha = "unknown"
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10
        )
        if proc.returncode == 0:
            sha = proc.stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": sha,
    }


def export_json(obj: dict, path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")