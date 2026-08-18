"""Snapshot generator: serialize backtest results to output/dashboard.json."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from nifty_gap.config import Config, PROJECT_ROOT
from nifty_gap.reporting import metrics
from nifty_gap.web.state import (
    compute_live_positions,
    compute_next_trade_preview,
    run_full_backtest,
)

OUTPUT_DIR = PROJECT_ROOT / "output"


def _clean(obj):
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, (pd.Timestamp,)):
        return obj.strftime("%Y-%m-%d")
    return obj


def _config_dict(cfg: Config, df: pd.DataFrame) -> dict:
    return {
        "iv_flat": cfg.iv_flat,
        "lot_size": cfg.lot_size,
        "ladder_floor_pcts": list(cfg.ladder_floor_pcts),
        "ladder_stop_pcts": list(cfg.ladder_stop_pcts),
        "ladder_rollover": cfg.ladder_rollover,
        "excluded_pairs": sorted(cfg.excluded_pairs),
        "pair_universe": sorted(df["weekday_pair"].dropna().unique().tolist()),
    }


def _trades_dicts(trades, trades_df) -> list[dict]:
    out = []
    for i, t in enumerate(trades):
        row = trades_df.iloc[i].to_dict()
        row["legs"] = [_clean(leg) for leg in (t.legs or ())]
        for key, val in row.items():
            if isinstance(val, pd.Timestamp):
                row[key] = val.strftime("%Y-%m-%d")
        out.append(_clean(row))
    return out


def _equity_curve(equity: pd.DataFrame) -> list[dict]:
    return [
        {"date": d.strftime("%Y-%m-%d"), "equity": float(eq)}
        for d, eq in zip(equity["Date"], equity["equity"])
    ]


def build_snapshot(
    cfg: Config | None = None, brokerage_per_trade: float = 0.0, slippage_pct: float = 0.0
) -> dict:
    cfg = cfg or Config()
    result = run_full_backtest(cfg, brokerage_per_trade, slippage_pct)
    return _snapshot_from_result(cfg, result)


def _snapshot_from_result(cfg: Config, result: dict) -> dict:
    df = result["df"]
    spot = float(df["Close"].iloc[-1])
    last_trading_date = df["Date"].max().strftime("%Y-%m-%d")

    return {
        "generated_at": metrics.provenance()["generated_at"],
        "last_trading_date": last_trading_date,
        "git_sha": metrics.provenance()["git_sha"],
        "config": _config_dict(cfg, df),
        "trade_stats": _clean(result["trade_stats"]),
        "equity_stats": _clean(result["equity_stats"]),
        "trades": _trades_dicts(result["trades"], result["trades_df"]),
        "equity_curve": _equity_curve(result["equity"]),
        "probability_table": _clean(
            result["table"][["weekday_pair", "n", "p_up", "ci_low", "ci_high", "side", "tradeable"]]
            .to_dict("records")
        ),
        "oos_data": _clean(metrics.oos_summary(result["oos_data"])),
        "benchmark_equity": _equity_curve(result["equity_hold"]),
        "live_positions": compute_live_positions(result["trades"], spot, cfg),
        "next_trade_preview": compute_next_trade_preview(df, result["table"], spot, cfg),
    }


def build_snapshot_and_charts(
    cfg: Config | None = None, brokerage_per_trade: float = 0.0, slippage_pct: float = 0.0
) -> dict:
    """Build snapshot and regenerate report PNGs from a single backtest run."""
    cfg = cfg or Config()
    result = run_full_backtest(cfg, brokerage_per_trade, slippage_pct)
    snap = _snapshot_from_result(cfg, result)
    render_report_pngs(cfg, brokerage_per_trade, slippage_pct, result=result)
    return snap


def render_report_pngs(
    cfg: Config | None = None,
    brokerage_per_trade: float = 0.0,
    slippage_pct: float = 0.0,
    result: dict | None = None,
) -> list:
    """Regenerate the five matplotlib report charts into OUTPUT_DIR."""
    from nifty_gap.visualization.charts import render_all

    if result is None:
        result = run_full_backtest(cfg or Config(), brokerage_per_trade, slippage_pct)
    return render_all(
        result["table"],
        result["trades_df"],
        result["equity"],
        result["equity_hold"],
        result["oos_data"],
        OUTPUT_DIR,
    )


def generate_snapshot(
    cfg: Config | None = None,
    out_path: str | Path | None = None,
    brokerage_per_trade: float = 0.0,
    slippage_pct: float = 0.0,
    render_pngs: bool = True,
) -> dict:
    builder = build_snapshot_and_charts if render_pngs else build_snapshot
    snapshot = builder(cfg, brokerage_per_trade, slippage_pct)
    out = Path(out_path) if out_path else OUTPUT_DIR / "dashboard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return snapshot


def main() -> None:
    snap = generate_snapshot()
    print(f"dashboard.json written: {len(snap['trades'])} trades, {snap['last_trading_date']}")


if __name__ == "__main__":
    main()