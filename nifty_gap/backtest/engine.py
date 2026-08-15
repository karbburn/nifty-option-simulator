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
    rolls: int = 0
    legs: tuple = ()


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

    closes = df.set_index("Date")["Close"]
    rate = get_risk_free_rate(cfg.rate_default)
    floor_pcts = cfg.ladder_floor_pcts

    legs: list[dict] = []
    cur_date = entry_date
    cur_close = entry_close
    cur_expiry = pd.Timestamp(next_expiry(entry_date.date(), cfg.expiry_weekday)).normalize()
    while True:
        strike = nearest_strike(cur_close, cfg.strike_interval, cfg.strike_tie_rule)
        t0 = max((cur_expiry - cur_date).days, 1) / 365.0
        entry_premium = black_scholes(cur_close, strike, t0, cfg.iv_flat, rate, side)

        obs_days = [d for d in df["Date"] if cur_date < d <= cur_expiry]
        triggers = [d for d in obs_days if d < cur_expiry]
        premiums = [entry_premium] + [
            _mark(closes, d, strike, side, cur_expiry, cfg) for d in triggers
        ]

        if mode == "hold":
            exit_reason = "expiry"
            exit_index = len(premiums) - 1
        else:
            ladder: LadderExit = simulate(
                premiums,
                entry_premium,
                floor_pcts=floor_pcts,
                stop_pcts=cfg.ladder_stop_pcts,
                fill_mode=cfg.ladder_fill_mode,
            )
            exit_reason = ladder.exit_reason
            exit_index = ladder.exit_index

        if exit_reason == "expiry":
            if obs_days:
                exit_premium = _mark(closes, obs_days[-1], strike, side, cur_expiry, cfg)
                exit_date = obs_days[-1]
            else:
                exit_premium = entry_premium
                exit_date = cur_date
        else:
            exit_premium = premiums[exit_index]
            exit_date = triggers[exit_index - 1] if exit_index >= 1 else cur_date

        legs.append(
            {
                "entry_date": cur_date,
                "exit_date": exit_date,
                "expiry": cur_expiry,
                "strike": strike,
                "entry_premium": entry_premium,
                "exit_premium": exit_premium,
                "exit_reason": exit_reason,
                "pnl": (exit_premium - entry_premium) * cfg.lot_size,
            }
        )

        if exit_reason != "expiry" or mode == "hold" or not cfg.ladder_rollover:
            break

        nxt = pd.Timestamp(next_expiry(cur_expiry.date(), cfg.expiry_weekday)).normalize()
        if not any(exit_date < d <= nxt for d in df["Date"]):
            break
        cur_date = exit_date
        cur_close = float(closes.loc[cur_date])
        cur_expiry = nxt

    first, last = legs[0], legs[-1]
    return Trade(
        entry_date=entry_date,
        exit_date=last["exit_date"],
        pair=pair,
        side=side,
        strike=first["strike"],
        entry_close=entry_close,
        expiry=last["expiry"],
        entry_premium=first["entry_premium"],
        exit_premium=last["exit_premium"],
        exit_reason=last["exit_reason"],
        days_held=max((last["exit_date"] - entry_date).days, 0),
        pnl=sum(leg["pnl"] for leg in legs),
        rolls=len(legs) - 1,
        legs=tuple(legs),
    )


def run_backtest(df: pd.DataFrame, table: pd.DataFrame, cfg: Config, mode: str = "ladder") -> list[Trade]:
    signals = build_signals(df, table)
    return [price_trade(df, sig, cfg, mode) for _, sig in signals.iterrows()]


def trades_frame(trades: list[Trade]) -> pd.DataFrame:
    return pd.DataFrame([asdict(t) for t in trades]).drop(columns=["legs"])


def daily_mtm(df: pd.DataFrame, trades: list[Trade], cfg: Config) -> pd.DataFrame:
    closes = df.set_index("Date")["Close"]
    rate = get_risk_free_rate(cfg.rate_default)
    rows = []
    for day in df["Date"]:
        realized = 0.0
        unrealized = 0.0
        for t in trades:
            legs = t.legs or (
                {
                    "entry_date": t.entry_date,
                    "exit_date": t.exit_date,
                    "expiry": t.expiry,
                    "strike": t.strike,
                    "entry_premium": t.entry_premium,
                    "exit_premium": t.exit_premium,
                },
            )
            for leg in legs:
                if leg["exit_date"] <= day:
                    realized += (leg["exit_premium"] - leg["entry_premium"]) * cfg.lot_size
                    continue
                if leg["entry_date"] > day:
                    continue
                spot = float(closes.loc[day])
                tte = max((leg["expiry"] - day).days, 0) / 365.0
                mark = black_scholes(spot, leg["strike"], tte, cfg.iv_flat, rate, t.side)
                unrealized += (mark - leg["entry_premium"]) * cfg.lot_size
        rows.append({"Date": day, "equity": realized + unrealized})
    return pd.DataFrame(rows, columns=["Date", "equity"])


def oos_diagnostic(df: pd.DataFrame, cfg: Config) -> dict:
    d0, d1 = df["Date"].min(), df["Date"].max()
    split = d0 + (d1 - d0) / 2
    first = df[df["Date"] <= split]
    second = df[df["Date"] > split]
    table = build_probability_table(first, cfg.min_pair_sample, cfg.z_score, cfg.excluded_pairs)
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
        "expected_scheme": any(r != "expiry" for r in counts),
    }