"""
Backtesting sur données historiques (version optimisée, vectorisée).
Simule le fonctionnement du système sur plusieurs mois de données passées de
l'or, SANS regarder dans le futur (tous les indicateurs sont calculés avec
des fenêtres glissantes qui ne regardent que le passé, donc les recalculer
une seule fois sur toute la série est strictement équivalent à les recalculer
à chaque instant t sur les données jusqu'à t — mais beaucoup plus rapide).

LIMITE IMPORTANTE : ce backtest ne couvre que les agents Technique et Macro.
Les agents Sentiment (news) et Calendrier ne peuvent pas être testés
rétroactivement sans un accès payant à des archives de news/calendrier — ce
backtest est donc une validation partielle, pas une garantie de performance
complète du système final (qui inclut aussi le sentiment et le calendrier).

Lancé manuellement via GitHub Actions (workflow_dispatch), pas sur un cron.
"""
import numpy as np
import pandas as pd

import config
from agents import data_agent, technical_agent
import telegram_bot

LOOKAHEAD_BARS = config.OUTCOME_EVALUATION_HOURS
MIN_MOVE_PCT = config.OUTCOME_MIN_MOVE_PCT

_TOTAL = config.WEIGHTS["technical"] + config.WEIGHTS["macro"]
W_TECH = config.WEIGHTS["technical"] / _TOTAL
W_MACRO = config.WEIGHTS["macro"] / _TOTAL

MIN_LOOKBACK = max(config.SMA_LONG, config.RSI_PERIOD, config.ATR_PERIOD) + 5


def _clip_series(s: pd.Series, lo=-1.0, hi=1.0) -> pd.Series:
    return s.clip(lower=lo, upper=hi)


def precompute_scores(gold_df: pd.DataFrame, dxy_df: pd.DataFrame) -> pd.DataFrame:
    """Calcule une fois pour toute la série les scores technique et macro."""
    df = gold_df.copy()
    df["sma_short"] = technical_agent.compute_sma(df["close"], config.SMA_SHORT)
    df["sma_long"] = technical_agent.compute_sma(df["close"], config.SMA_LONG)
    df["rsi"] = technical_agent.compute_rsi(df["close"], config.RSI_PERIOD)
    df["atr"] = technical_agent.compute_atr(df, config.ATR_PERIOD)

    gap_pct = ((df["sma_short"] - df["sma_long"]) / df["sma_long"]) * 100
    trend_component = _clip_series(gap_pct / technical_agent.TREND_MAX_GAP_PCT) * technical_agent.TREND_WEIGHT
    momentum_component = _clip_series((df["rsi"] - 50) / 50) * technical_agent.MOMENTUM_WEIGHT
    df["technical_score"] = (trend_component + momentum_component).clip(-1, 1)

    # Macro : pct change EUR/USD sur 6 périodes, aligné sur le timestamp gold le plus proche (passé)
    dxy = dxy_df[["date", "close"]].rename(columns={"close": "eur_usd_close"}).sort_values("date")
    dxy["eur_usd_pct_change_6"] = dxy["eur_usd_close"].pct_change(6) * 100

    df = df.sort_values("date")
    merged = pd.merge_asof(df, dxy[["date", "eur_usd_pct_change_6"]], on="date", direction="backward")

    macro_score = np.where(
        merged["eur_usd_pct_change_6"] > 0.15, 0.6,
        np.where(merged["eur_usd_pct_change_6"] < -0.15, -0.6, 0.0)
    )
    merged["macro_score"] = macro_score

    return merged


def run_backtest(scored_df: pd.DataFrame, confidence_threshold: float, cooldown_hours: float = 0) -> dict:
    weighted_score = scored_df["technical_score"] * W_TECH + scored_df["macro_score"] * W_MACRO
    confidence = weighted_score.abs()

    n = len(scored_df)
    trades = []
    last_trade_time = None

    dates = scored_df["date"].values
    closes = scored_df["close"].values
    conf_vals = confidence.values
    score_vals = weighted_score.values

    for i in range(MIN_LOOKBACK, n - LOOKAHEAD_BARS):
        if conf_vals[i] < confidence_threshold:
            continue

        current_time = dates[i]

        if last_trade_time is not None and cooldown_hours > 0:
            hours_since_last = (current_time - last_trade_time) / np.timedelta64(1, "h")
            if hours_since_last < cooldown_hours:
                continue

        direction = "LONG" if score_vals[i] > 0 else "SHORT"
        entry_price = closes[i]
        exit_price = closes[i + LOOKAHEAD_BARS]

        pct_move = ((exit_price - entry_price) / entry_price) * 100
        pnl_pct = pct_move if direction == "LONG" else -pct_move

        won = None
        if abs(pct_move) >= MIN_MOVE_PCT:
            won = pnl_pct > 0

        trades.append({"pnl_pct": pnl_pct, "won": won})
        last_trade_time = current_time

    return summarize(trades)


def summarize(trades: list) -> dict:
    if not trades:
        return {"total_trades": 0}

    decisive = [t for t in trades if t["won"] is not None]
    wins = [t for t in decisive if t["won"]]

    cumulative_pnl = sum(t["pnl_pct"] for t in trades)
    win_rate = (len(wins) / len(decisive) * 100) if decisive else 0.0

    equity_curve = []
    running = 0.0
    for t in trades:
        running += t["pnl_pct"]
        equity_curve.append(running)

    peak = float("-inf")
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        max_drawdown = max(max_drawdown, peak - value)

    return {
        "total_trades": len(trades),
        "decisive_trades": len(decisive),
        "win_rate_pct": round(win_rate, 1),
        "cumulative_pnl_pct": round(cumulative_pnl, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "avg_pnl_per_trade_pct": round(cumulative_pnl / len(trades), 3) if trades else 0.0,
    }


def format_sweep_report(sweep_results: list, period_desc: str) -> str:
    lines = [
        f"📉 BACKTEST SWEEP — {period_desc}",
        "⚠️ Technique + Macro uniquement (sentiment/calendrier non testables rétroactivement)",
        "",
        "Seuil | Cooldown | Trades | Réussite | P&L moy/trade",
    ]
    for params, results in sweep_results:
        threshold, cooldown = params
        if results["total_trades"] == 0:
            lines.append(f"{threshold:.2f} | {cooldown}h | 0 trades | — | —")
            continue
        lines.append(
            f"{threshold:.2f} | {cooldown}h | {results['total_trades']} "
            f"({results.get('trades_per_day', 0):.1f}/j) | {results['win_rate_pct']}% | "
            f"{results['avg_pnl_per_trade_pct']:+.3f}%"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print("Récupération des données historiques...")
    gold_df = data_agent.get_gold_data(interval="1h", outputsize=5000)
    dxy_df = data_agent.get_dxy_data(interval="1h", outputsize=5000)
    print(f"{len(gold_df)} bougies or, {len(dxy_df)} bougies EUR/USD récupérées.")

    scored_df = precompute_scores(gold_df, dxy_df)

    period_days = (gold_df["date"].iloc[-1] - gold_df["date"].iloc[MIN_LOOKBACK]).days or 1
    period_desc = f"{gold_df['date'].iloc[MIN_LOOKBACK].date()} à {gold_df['date'].iloc[-1].date()}"

    thresholds_to_test = [0.15, 0.30, 0.45, 0.60]
    cooldowns_to_test = [0, 6, 12, 24]

    sweep_results = []
    for threshold in thresholds_to_test:
        for cooldown in cooldowns_to_test:
            results = run_backtest(scored_df, confidence_threshold=threshold, cooldown_hours=cooldown)
            if results["total_trades"] > 0:
                results["trades_per_day"] = results["total_trades"] / period_days
            sweep_results.append(((threshold, cooldown), results))
            print(f"seuil={threshold} cooldown={cooldown}h -> {results}")

    report = format_sweep_report(sweep_results, period_desc)
    print(report)
    telegram_bot.send_message(report)
