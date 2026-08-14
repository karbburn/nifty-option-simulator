"""Backtest engine: signals -> priced trades -> portfolio MTM; benchmark and OOS modes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from nifty_gap.config import Config
from nifty_gap.options.black_scholes import black_scholes
from nifty_gap.options.calendar import next_expiry
from nifty_gap.options.rate import get_risk_free_rate
from nifty_gap.options.strikes import nearest_strike
from nifty_gap.signals.probability_table import build_probability_table, wilson_interval
from nifty_gap.trade.ladder import LadderExit, simulate

MODES = frozenset({"ladder", "hold"})


@dataclass(frozen=True)
class Trade:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    pair: str
    side: str
    strike: float
    entry_close: float
    expiry: pd.Timestamp
    entry_premium: float
    exit_premium: float
    exit_reason: str
    days_held: int
    pnl: float


def build_signals(df: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    tradeable = set(table.loc[table["tradeable"], "weekday_pair"])
    side_of = dict(zip(table["weekday_pair"], table["side"]))
    recs = []
    dates = df["Date"].tolist()
    closes = df["Close"].tolist()
    pairs = df["weekday_pair"].tolist()
    for i in range(1, len(df)):
        pair = pairs[i]
        if pd.isna(pair) or pair not in tradeable:
            continue
        recs.append(
            {
                "entry_date": dates[i - 1],
                "entry_close": float(closes[i - 1]),
                "pair": str(pair),
                "side": side_of[pair],
            }
        )
    return pd.DataFrame(recs, columns=["entry_date", "entry_close", "pair", "side"])


def _mark(closes: pd.Series, day, strike, side, expiry: pd.Timestamp, cfg: Config) -> float:
    spot = float(closes.loc[day])
    tte = max((expiry - day).days, 0) / 365.0
    rate = get_risk_free_rate(cfg.rate_default)
    return black_scholes(spot, strike, tte, cfg.iv_flat, rate, side)


def price_trade(df: pd.DataFrame, signal, cfg: Config, mode: str = "ladder") -> Trade:
    if mode not in MODES:
        raise ValueError(f"unsupported mode: {mode!r}")
    entry_date = pd.Timestamp(signal["entry_date"]).normalize()
    entry_close = float(signal["entry_close"])
    pair = str(signal["pair"])
    side = str(signal["side"])

    strike = nearest_strike(entry_close, cfg.strike_interval, cfg.strike_tie_rule)
    expiry = pd.Timestamp(next_expiry(entry_date.date(), cfg.expiry_weekday)).normalize()
    rate = get_risk_free_rate(cfg.rate_default)
    t0 = max((expiry - entry_date).days, 1) / 365.0
    entry_premium = black_scholes(entry_close, strike, t0, cfg.iv_flat, rate, side)

    closes = df.set_index("Date")["Close"]
    obs_days = [d for d in df["Date"] if entry_date < d <= expiry]
    triggers = [d for d in obs_days if d < expiry]

    premiums = [entry_premium] + [
        _mark(closes, d, strike, side, expiry, cfg) for d in triggers
    ]

    if mode == "hold":
        exit_reason = "expiry"
        exit_index = len(premiums) - 1
    else:
        ladder: LadderExit = simulate(
            premiums,
            entry_premium,
            sl_pct=cfg.ladder_sl_pct,
            floor_pcts=cfg.ladder_floor_pcts,
            target_pct=cfg.ladder_target_pct,
            fill_mode=cfg.ladder_fill_mode,
        )
        exit_reason = ladder.exit_reason
        exit_index = ladder.exit_index

    if exit_reason == "expiry":
        if obs_days:
            exit_premium = _mark(closes, obs_days[-1], strike, side, expiry, cfg)
            exit_date = obs_days[-1]
        else:
            exit_premium = entry_premium
            exit_date = entry_date
    else:
        exit_premium = premiums[exit_index]
        exit_date = triggers[exit_index - 1] if exit_index >= 1 else entry_date

    days_held = max((exit_date - entry_date).days, 0)
    pnl = (exit_premium - entry_premium) * cfg.lot_size
    return Trade(
        entry_date=entry_date,
        exit_date=exit_date,
        pair=pair,
        side=side,
        strike=float(strike),
        entry_close=entry_close,
        expiry=expiry,
        entry_premium=entry_premium,
        exit_premium=exit_premium,
        exit_reason=exit_reason,
        days_held=days_held,
        pnl=pnl,
    )


def run_backtest(df: pd.DataFrame, table: pd.DataFrame, cfg: Config, mode: str = "ladder") -> list[Trade]:
    signals = build_signals(df, table)
    return [price_trade(df, sig, cfg, mode) for _, sig in signals.iterrows()]


def trades_frame(trades: list[Trade]) -> pd.DataFrame:
    return pd.DataFrame([asdict(t) for t in trades])


def daily_mtm(df: pd.DataFrame, trades: list[Trade], cfg: Config) -> pd.DataFrame:
    closes = df.set_index("Date")["Close"]
    rate = get_risk_free_rate(cfg.rate_default)
    rows = []
    for day in df["Date"]:
        realized = sum(t.pnl for t in trades if t.exit_date <= day)
        unrealized = 0.0
        for t in trades:
            if t.exit_date <= day or t.entry_date > day:
                continue
            if t.entry_date <= day < t.exit_date:
                spot = float(closes.loc[day])
                tte = max((t.expiry - day).days, 0) / 365.0
                mark = black_scholes(spot, t.strike, tte, cfg.iv_flat, rate, t.side)
                unrealized += (mark - t.entry_premium) * cfg.lot_size
        rows.append({"Date": day, "equity": realized + unrealized})
    return pd.DataFrame(rows, columns=["Date", "equity"])


def oos_diagnostic(df: pd.DataFrame, cfg: Config) -> dict:
    d0, d1 = df["Date"].min(), df["Date"].max()
    split = d0 + (d1 - d0) / 2
    first = df[df["Date"] <= split]
    second = df[df["Date"] > split]
    table = build_probability_table(first, cfg.min_pair_sample, cfg.z_score)
    g = second.dropna(subset=["weekday_pair"]).groupby("weekday_pair")["gap_up"]
    realized = g.agg(["size", "mean"]).rename(columns={"size": "n_oos", "mean": "realized_p_up"}).reset_index()
    olow, ohigh = wilson_interval(realized["realized_p_up"] * realized["n_oos"], realized["n_oos"], cfg.z_score)
    realized["realized_ci_low"] = olow
    realized["realized_ci_high"] = ohigh
    oos = table[["weekday_pair", "n", "p_up", "ci_low", "ci_high", "side"]].merge(realized, on="weekday_pair", how="left")
    return {"split_date": split, "table": table, "oos": oos}


def export_results(trades: list[Trade], equity: pd.DataFrame, params: dict, out_dir) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    trades_frame(trades).to_csv(out / "trades.csv", index=False)
    equity.to_csv(out / "equity.csv", index=False)
    (out / "params.json").write_text(json.dumps(params, indent=2, default=str), encoding="utf-8")


def ladder_log_gate(trades: list[Trade]) -> dict:
    counts: dict[str, int] = {}
    for t in trades:
        counts[t.exit_reason] = counts.get(t.exit_reason, 0) + 1
    avg_days = sum(t.days_held for t in trades) / len(trades) if trades else 0.0
    max_days = max((t.days_held for t in trades), default=0)
    return {
        "exit_reason_counts": counts,
        "avg_days_held": avg_days,
        "max_days_held": max_days,
        "expected_scheme": avg_days <= 3.0,
    }