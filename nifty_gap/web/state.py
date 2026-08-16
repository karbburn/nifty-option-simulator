"""Dashboard data layer: wraps existing backtest modules into web-friendly dicts."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

import pandas as pd

from nifty_gap.backtest.engine import (
    Trade,
    daily_mtm,
    oos_diagnostic,
    run_backtest,
    trades_frame,
)
from nifty_gap.config import Config, PROJECT_ROOT
from nifty_gap.data.loader import load_dataframe
from nifty_gap.options.black_scholes import black_scholes
from nifty_gap.options.calendar import next_expiry
from nifty_gap.options.rate import get_risk_free_rate
from nifty_gap.options.strikes import nearest_strike
from nifty_gap.reporting import metrics
from nifty_gap.signals.probability_table import build_probability_table

HISTORY_PATH = PROJECT_ROOT / "data" / "nifty50_history.csv"


def load_history_df() -> pd.DataFrame:
    return load_dataframe(HISTORY_PATH)


def _rate(cfg: Config) -> float:
    return get_risk_free_rate(cfg.rate_default)


def run_full_backtest(cfg: Config | None = None) -> dict:
    cfg = cfg or Config()
    df = load_history_df()
    table = build_probability_table(df, cfg.min_pair_sample, cfg.z_score, cfg.excluded_pairs)
    trades = run_backtest(df, table, cfg, "ladder")
    hold_trades = run_backtest(df, table, cfg, "hold")
    equity = daily_mtm(df, trades, cfg)
    equity_hold = daily_mtm(df, hold_trades, cfg)
    oos = oos_diagnostic(df, cfg)
    trades_df = trades_frame(trades)
    return {
        "df": df,
        "trades": trades,
        "trades_df": trades_df,
        "table": table,
        "equity": equity,
        "equity_hold": equity_hold,
        "oos_data": oos["oos"],
        "trade_stats": metrics.trade_stats(trades_df),
        "equity_stats": metrics.equity_stats(equity),
    }


def compute_premium_series(df: pd.DataFrame, trade: Trade, cfg: Config | None = None) -> list[dict]:
    cfg = cfg or Config()
    closes = df.set_index("Date")["Close"]
    rate = _rate(cfg)
    rows = []
    for day in df["Date"]:
        if day < trade.entry_date or day > trade.exit_date:
            continue
        premium = 0.0
        for leg in trade.legs or (asdict(trade),):
            leg_exit = pd.Timestamp(leg["exit_date"])
            leg_entry = pd.Timestamp(leg["entry_date"])
            if leg_exit < day or leg_entry > day:
                continue
            tte = max((pd.Timestamp(leg["expiry"]) - day).days, 0) / 365.0
            premium += black_scholes(float(closes.loc[day]), leg["strike"], tte, cfg.iv_flat, rate, trade.side)
        rows.append({"date": day.strftime("%Y-%m-%d"), "premium": round(premium, 2)})
    return rows


def compute_live_positions(
    trades: list[Trade], spot: float, cfg: Config | None = None, today: date | None = None
) -> list[dict]:
    cfg = cfg or Config()
    today = today or date.today()
    rate = _rate(cfg)
    positions = {}
    for t in trades:
        if t.expiry.date() <= today:
            continue
        cur = positions.get(t.pair)
        if cur is None or t.entry_date > cur.entry_date:
            positions[t.pair] = t
    out = []
    for t in positions.values():
        live_premium = black_scholes(
            spot, t.strike, max((t.expiry.date() - today).days, 0) / 365.0, cfg.iv_flat, rate, t.side
        )
        out.append(
            {
                "pair": t.pair,
                "side": t.side,
                "strike": t.strike,
                "entry_date": t.entry_date.strftime("%Y-%m-%d"),
                "entry_premium": round(t.entry_premium, 2),
                "live_premium": round(live_premium, 2),
                "live_pnl": round((live_premium - t.entry_premium) * cfg.lot_size, 2),
                "pct_move": round((live_premium / t.entry_premium - 1) * 100, 2) if t.entry_premium else 0.0,
                "banked_floor": None,
                "days_to_expiry": (t.expiry.date() - today).days,
            }
        )
    return out


def compute_next_trade_preview(
    df: pd.DataFrame, table: pd.DataFrame, spot: float, cfg: Config | None = None, today: date | None = None
) -> dict:
    cfg = cfg or Config()
    today = pd.Timestamp(today or date.today())
    future = df[df["Date"] > today]
    if future.empty:
        return {}
    nxt = future.iloc[0]
    pair = str(nxt["weekday_pair"])
    row = table[table["weekday_pair"] == pair]
    if row.empty or not bool(row.iloc[0]["tradeable"]):
        return {"pair": pair, "note": "Next pair not tradeable"}
    side = str(row.iloc[0]["side"])
    strike = nearest_strike(spot, cfg.strike_interval, cfg.strike_tie_rule)
    tte = max((pd.Timestamp(next_expiry(nxt["Date"].date(), cfg.expiry_weekday)) - nxt["Date"]).days, 1) / 365.0
    entry_premium = black_scholes(spot, strike, tte, cfg.iv_flat, _rate(cfg), side)
    return {
        "pair": pair,
        "side": side,
        "strike": strike,
        "entry_premium": round(entry_premium, 2),
        "tte_days": round(tte * 365),
        "note": "Fires on next close if signal confirms",
    }