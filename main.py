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
import confirmation


def run_cycle():
    now = datetime.now(timezone.utc)

    if not market_hours.is_market_open(now):
        print(f"[{now}] Marché fermé (week-end), cycle ignoré.")
        return

    print(f"[{now}] Cycle démarré...")

    # 1. Données (H1 pour l'analyse principale, H4 pour la confluence de tendance)
    gold_df = data_agent.get_gold_data(interval="1h", outputsize=100)
    dxy_df = data_agent.get_dxy_data(interval="1h", outputsize=20)

    try:
        gold_h4_df = data_agent.fetch_ohlcv(config.SYMBOL, interval="4h", outputsize=60)
        h4_trend = technical_agent.get_trend_direction(gold_h4_df)
    except Exception as e:
        print(f"Avertissement : données H4 indisponibles ({e})")
        h4_trend = 0

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

    # 3. Décision finale (avec confluence H4 + sécurité calendrier intégrée)
    decision = decision_agent.aggregate(technical_result, macro_result, sentiment_result, calendar_result, h4_trend=h4_trend)

    # 3a. Filtre de session : signal hors Londres/NY = moins fiable, on prévient
    if not market_hours.is_active_session(now) and decision["direction"] in ("LONG", "SHORT"):
        decision["warnings"].insert(
            0,
            "🌙 Hors session Londres/New York : liquidité plus faible, signal moins fiable"
        )
    elif market_hours.is_prime_session(now) and decision["direction"] in ("LONG", "SHORT"):
        decision["reasons"].insert(0, "✅ Session de chevauchement Londres/NY : meilleure liquidité de la journée")

    # 3b. Confirmation différée : le signal doit se maintenir un cycle de plus
    confirmation_result = confirmation.check_confirmation(decision["direction"], now)
    decision["is_confirmed"] = True
    if decision["direction"] in ("LONG", "SHORT"):
        if confirmation_result["is_new_pending"]:
            decision["is_confirmed"] = False
            decision["warnings"].insert(
                0,
                "🔍 Signal en cours de confirmation : besoin d'un cycle supplémentaire avec le même sens avant validation complète"
            )
        elif confirmation_result["confirmed"]:
            decision["reasons"].insert(0, "✅ Signal confirmé sur deux cycles consécutifs")

    # 3c. Cooldown : on avertit mais on ne cache plus le signal réel
    if decision["direction"] in ("LONG", "SHORT"):
        last_directional_time = logger.get_last_directional_time()
        if last_directional_time is not None:
            hours_since_last = (now - last_directional_time).total_seconds() / 3600
            if hours_since_last < config.TRADE_COOLDOWN_HOURS:
                decision["warnings"].insert(
                    0,
                    f"⏱️ COOLDOWN ACTIF : dernier signal directionnel il y a {hours_since_last:.1f}h "
                    f"(recommandé : {config.TRADE_COOLDOWN_HOURS}h entre deux trades) — à toi de juger"
                )

    # 3d. Taille de position suggérée (si LONG/SHORT)
    eur_usd_rate = float(dxy_df["close"].iloc[-1]) if len(dxy_df) else 1.0
    position_info = risk_agent.compute_position_size(decision, eur_usd_rate=eur_usd_rate)
    decision["position_info"] = position_info

    # 4. Notification + log pour suivi de performance
    telegram_bot.notify_decision(decision)
    logger.log_decision(decision)
    print(f"[{datetime.now()}] Décision envoyée : {decision['direction']} "
          f"(confiance {decision['confidence']*100:.0f}%, confirmé={decision['is_confirmed']})")


if __name__ == "__main__":
    run_cycle()
