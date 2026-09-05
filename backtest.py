"""
Backtesting sur données historiques.
Simule le fonctionnement du système sur plusieurs mois de données passées de
l'or, SANS regarder dans le futur (à chaque instant simulé, seules les
données jusqu'à ce moment-là sont utilisées).

LIMITE IMPORTANTE : ce backtest ne couvre que les agents Technique et Macro.
Les agents Sentiment (news) et Calendrier ne peuvent pas être testés
rétroactivement sans un accès payant à des archives de news/calendrier — ce
backtest est donc une validation partielle, pas une garantie de performance
complète du système final (qui inclut aussi le sentiment et le calendrier).

Lancé manuellement via GitHub Actions (workflow_dispatch), pas sur un cron :
c'est un outil de validation ponctuel, pas un cycle récurrent.
"""
from datetime import datetime, timezone

import pandas as pd

import config
from agents import data_agent, technical_agent, macro_agent
import telegram_bot

LOOKAHEAD_BARS = config.OUTCOME_EVALUATION_HOURS  # en barres horaires
MIN_MOVE_PCT = config.OUTCOME_MIN_MOVE_PCT

# Poids relatifs technique/macro, renormalisés pour ignorer sentiment/calendrier
# (non disponibles en backtest)
_TOTAL = config.WEIGHTS["technical"] + config.WEIGHTS["macro"]
W_TECH = config.WEIGHTS["technical"] / _TOTAL
W_MACRO = config.WEIGHTS["macro"] / _TOTAL

MIN_LOOKBACK = max(config.SMA_LONG, config.RSI_PERIOD, config.ATR_PERIOD) + 5


def run_backtest(gold_df: pd.DataFrame, dxy_df: pd.DataFrame,
                  confidence_threshold: float = None, cooldown_hours: float = 0) -> dict:
    if confidence_threshold is None:
        confidence_threshold = config.CONFIDENCE_THRESHOLD_NEUTRAL

    trades = []
    last_trade_time = None

    for i in range(MIN_LOOKBACK, len(gold_df) - LOOKAHEAD_BARS):
        window = gold_df.iloc[: i + 1]
        current_time = window["date"].iloc[-1]

        # Aligner la fenêtre EUR/USD sur le même instant (pas de fuite du futur)
        dxy_window = dxy_df[dxy_df["date"] <= current_time].tail(20)
        if len(dxy_window) < 6:
            continue

        tech = technical_agent.analyze(window)
        macro = macro_agent.analyze(dxy_window)

        weighted_score = tech["score"] * W_TECH + macro["score"] * W_MACRO
        confidence = abs(weighted_score)

        if confidence < confidence_threshold:
            continue  # NEUTRE : pas de trade simulé

        if last_trade_time is not None and cooldown_hours > 0:
            hours_since_last = (current_time - last_trade_time).total_seconds() / 3600
            if hours_since_last < cooldown_hours:
                continue  # en cooldown : on ignore ce signal, même s'il est valide

        direction = "LONG" if weighted_score > 0 else "SHORT"
        entry_price = window["close"].iloc[-1]
        exit_price = gold_df["close"].iloc[i + LOOKAHEAD_BARS]

        pct_move = ((exit_price - entry_price) / entry_price) * 100
        pnl_pct = pct_move if direction == "LONG" else -pct_move

        won = None
        if abs(pct_move) >= MIN_MOVE_PCT:
            won = pnl_pct > 0

        trades.append({
            "time": current_time,
            "direction": direction,
            "confidence": confidence,
            "entry": entry_price,
            "exit": exit_price,
            "pnl_pct": pnl_pct,
            "won": won,
        })
        last_trade_time = current_time

    return summarize(trades)


def summarize(trades: list) -> dict:
    if not trades:
        return {"total_trades": 0}

    decisive = [t for t in trades if t["won"] is not None]
    wins = [t for t in decisive if t["won"]]

    cumulative_pnl = sum(t["pnl_pct"] for t in trades)
    win_rate = (len(wins) / len(decisive) * 100) if decisive else 0.0

    # Calcul simple de drawdown max sur la courbe cumulative
    equity_curve = []
    running = 0.0
    for t in trades:
        running += t["pnl_pct"]
        equity_curve.append(running)

    peak = float("-inf")
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        drawdown = peak - value
        max_drawdown = max(max_drawdown, drawdown)

    return {
        "total_trades": len(trades),
        "decisive_trades": len(decisive),
        "win_rate_pct": round(win_rate, 1),
        "cumulative_pnl_pct": round(cumulative_pnl, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "avg_pnl_per_trade_pct": round(cumulative_pnl / len(trades), 3) if trades else 0.0,
    }


def format_report(results: dict, period_desc: str) -> str:
    if results["total_trades"] == 0:
        return f"📉 BACKTEST — {period_desc}\n\nAucun trade déclenché (toujours resté en NEUTRE)."

    return (
        f"📉 BACKTEST — {period_desc}\n\n"
        f"⚠️ Technique + Macro uniquement (sentiment/calendrier non testables rétroactivement)\n\n"
        f"• Trades simulés : {results['total_trades']}\n"
        f"• Trades évaluables : {results['decisive_trades']}\n"
        f"• Taux de réussite : {results['win_rate_pct']}%\n"
        f"• P&L cumulé : {results['cumulative_pnl_pct']:+.2f}%\n"
        f"• Drawdown max : -{results['max_drawdown_pct']:.2f}%\n"
        f"• P&L moyen/trade : {results['avg_pnl_per_trade_pct']:+.3f}%"
    )


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

    period_days = (gold_df["date"].iloc[-1] - gold_df["date"].iloc[MIN_LOOKBACK]).days or 1
    period_desc = f"{gold_df['date'].iloc[MIN_LOOKBACK].date()} à {gold_df['date'].iloc[-1].date()}"

    # Sweep : seuils plus exigeants que le défaut actuel (0.15) + cooldowns variés
    thresholds_to_test = [0.15, 0.30, 0.45, 0.60]
    cooldowns_to_test = [0, 6, 12, 24]

    sweep_results = []
    for threshold in thresholds_to_test:
        for cooldown in cooldowns_to_test:
            results = run_backtest(gold_df, dxy_df, confidence_threshold=threshold, cooldown_hours=cooldown)
            if results["total_trades"] > 0:
                results["trades_per_day"] = results["total_trades"] / period_days
            sweep_results.append(((threshold, cooldown), results))
            print(f"seuil={threshold} cooldown={cooldown}h -> {results}")

    report = format_sweep_report(sweep_results, period_desc)
    print(report)
    telegram_bot.send_message(report)
