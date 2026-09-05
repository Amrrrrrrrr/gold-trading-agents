"""
Backtesting sur données historiques (version walk-forward + coûts réels).

Deux améliorations par rapport à la v1 :
1. Coût de spread déduit de chaque trade (config.SPREAD_COST_USD), pour un
   P&L réaliste plutôt qu'un chiffre optimiste sans friction.
2. Validation walk-forward : au lieu d'un seul test sur toute la période
   (risque de sur-ajustement caché), on découpe l'historique en blocs
   mensuels et on rapporte la performance bloc par bloc. Un système robuste
   doit rester globalement cohérent d'un mois à l'autre, pas juste bon en
   moyenne sur l'ensemble.

LIMITE IMPORTANTE : ce backtest ne couvre que les agents Technique et Macro
(H1 uniquement, sans confluence H4, sans confirmation différée, sans filtre
de session). Le sentiment et le calendrier ne sont pas testables
rétroactivement sans archives payantes. C'est une validation partielle.

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


def simulate_trades(scored_df: pd.DataFrame, confidence_threshold: float, cooldown_hours: float = 0) -> list:
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
        gross_pnl_pct = pct_move if direction == "LONG" else -pct_move

        # Coût de spread réaliste, converti en % du prix d'entrée
        spread_pct = (config.SPREAD_COST_USD / entry_price) * 100
        net_pnl_pct = gross_pnl_pct - spread_pct

        won = None
        if abs(pct_move) >= MIN_MOVE_PCT:
            won = net_pnl_pct > 0

        trades.append({
            "time": pd.Timestamp(current_time),
            "direction": direction,
            "pnl_pct": net_pnl_pct,
            "won": won,
        })
        last_trade_time = current_time

    return trades


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


def walk_forward_report(trades: list) -> str:
    """Regroupe les trades par mois calendaire pour vérifier la stabilité."""
    if not trades:
        return "Aucun trade à analyser en walk-forward."

    df = pd.DataFrame(trades)
    df["month"] = df["time"].dt.to_period("M")

    lines = ["📆 WALK-FORWARD (mois par mois, coûts inclus) :"]
    for month, group in df.groupby("month"):
        month_trades = group.to_dict("records")
        stats = summarize(month_trades)
        if stats["total_trades"] == 0:
            continue
        lines.append(
            f"• {month} : {stats['total_trades']} trades, "
            f"{stats['win_rate_pct']}% réussite, P&L net {stats['cumulative_pnl_pct']:+.2f}%"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print("Récupération des données historiques...")
    gold_df = data_agent.get_gold_data(interval="1h", outputsize=5000)
    dxy_df = data_agent.get_dxy_data(interval="1h", outputsize=5000)
    print(f"{len(gold_df)} bougies or, {len(dxy_df)} bougies EUR/USD récupérées.")

    scored_df = precompute_scores(gold_df, dxy_df)

    # Configuration actuellement en production (seuil 0.45, cooldown 24h)
    trades = simulate_trades(scored_df, confidence_threshold=config.CONFIDENCE_THRESHOLD_NEUTRAL,
                              cooldown_hours=config.TRADE_COOLDOWN_HOURS)
    overall_stats = summarize(trades)

    period_desc = f"{gold_df['date'].iloc[MIN_LOOKBACK].date()} à {gold_df['date'].iloc[-1].date()}"

    report_lines = [
        f"📉 BACKTEST (coûts inclus, spread ~{config.SPREAD_COST_USD}$/trade) — {period_desc}",
        f"Config actuelle : seuil {config.CONFIDENCE_THRESHOLD_NEUTRAL}, cooldown {config.TRADE_COOLDOWN_HOURS}h",
        "⚠️ Technique + Macro uniquement (H1, sans H4/confirmation/session/sentiment/calendrier)",
        "",
    ]

    if overall_stats["total_trades"] == 0:
        report_lines.append("Aucun trade déclenché avec cette configuration sur la période testée.")
    else:
        report_lines += [
            f"• Trades : {overall_stats['total_trades']} sur {(gold_df['date'].iloc[-1] - gold_df['date'].iloc[MIN_LOOKBACK]).days} jours",
            f"• Réussite : {overall_stats['win_rate_pct']}%",
            f"• P&L net cumulé : {overall_stats['cumulative_pnl_pct']:+.2f}%",
            f"• Drawdown max : -{overall_stats['max_drawdown_pct']:.2f}%",
            f"• P&L net moyen/trade : {overall_stats['avg_pnl_per_trade_pct']:+.3f}%",
            "",
            walk_forward_report(trades),
        ]

    report = "\n".join(report_lines)
    print(report)
    telegram_bot.send_message(report)
