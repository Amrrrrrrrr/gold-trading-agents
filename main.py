"""
Point d'entrée principal.
Sur GitHub Actions, ce script est déclenché toutes les heures par un workflow
cron : il tourne UNE FOIS puis s'arrête (pas de boucle infinie ici).
"""
from datetime import datetime, timezone

import config
from agents import data_agent, technical_agent, macro_agent, sentiment_agent, decision_agent, calendar_agent, risk_agent
import telegram_bot
import logger
import market_hours


def run_cycle():
    now = datetime.now(timezone.utc)

    if not market_hours.is_market_open(now):
        print(f"[{now}] Marché fermé (week-end), cycle ignoré.")
        return

    print(f"[{now}] Cycle démarré...")

    # 1. Données
    gold_df = data_agent.get_gold_data(interval="1h", outputsize=100)
    dxy_df = data_agent.get_dxy_data(interval="1h", outputsize=20)

    # 2. Analyses
    technical_result = technical_agent.analyze(gold_df)
    macro_result = macro_agent.analyze(dxy_df)

    try:
        calendar_result = calendar_agent.analyze()
    except Exception as e:
        print(f"Avertissement : agent calendrier indisponible ({e})")
        calendar_result = {"reasons": [], "warnings": ["Agent calendrier indisponible ce cycle"],
                            "imminent_event": None, "recent_event": None}

    try:
        headlines = sentiment_agent.fetch_gold_headlines()
        sentiment_result = sentiment_agent.analyze(headlines)
    except Exception as e:
        print(f"Avertissement : agent sentiment indisponible ({e})")
        sentiment_result = {"score": 0.0, "reasons": [], "warnings": ["Agent news indisponible ce cycle"]}

    # 3. Décision finale (avec sécurité calendrier intégrée)
    decision = decision_agent.aggregate(technical_result, macro_result, sentiment_result, calendar_result)

    # 3b. Taille de position suggérée (si LONG/SHORT)
    eur_usd_rate = float(dxy_df["close"].iloc[-1]) if len(dxy_df) else 1.0
    position_info = risk_agent.compute_position_size(decision, eur_usd_rate=eur_usd_rate)
    decision["position_info"] = position_info

    # 4. Notification + log pour suivi de performance
    telegram_bot.notify_decision(decision)
    logger.log_decision(decision)
    print(f"[{datetime.now()}] Décision envoyée : {decision['direction']} "
          f"(confiance {decision['confidence']*100:.0f}%)")


if __name__ == "__main__":
    run_cycle()
