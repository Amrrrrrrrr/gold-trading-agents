"""
Agent Décision.
Agrège les scores pondérés des agents Technique, Macro et Sentiment
pour produire une recommandation finale : LONG / SHORT / NEUTRE,
avec un niveau de confiance et des niveaux de stop-loss / take-profit suggérés.

IMPORTANT : ceci est un outil d'aide à la décision, pas un conseil financier.
Toute décision d'achat/vente reste sous la responsabilité de l'utilisateur.
"""
import config


def aggregate(technical: dict, macro: dict, sentiment: dict) -> dict:
    weighted_score = (
        technical["score"] * config.WEIGHTS["technical"]
        + macro["score"] * config.WEIGHTS["macro"]
        + sentiment["score"] * config.WEIGHTS["sentiment"]
    )

    confidence = min(abs(weighted_score), 1.0)

    if confidence < config.CONFIDENCE_THRESHOLD_NEUTRAL:
        direction = "NEUTRE"
    elif weighted_score > 0:
        direction = "LONG"
    else:
        direction = "SHORT"

    all_reasons = technical["reasons"] + macro["reasons"] + sentiment["reasons"]
    all_warnings = technical["warnings"] + macro["warnings"] + sentiment["warnings"]

    # --- Niveaux suggérés (basés sur l'ATR, pas des ordres automatiques) ---
    entry = technical.get("last_price")
    atr = technical.get("atr")
    stop_loss = None
    take_profit = None

    if entry is not None and atr is not None:
        if direction == "LONG":
            stop_loss = entry - atr * config.ATR_MULTIPLIER_SL
            take_profit = entry + atr * config.ATR_MULTIPLIER_TP
        elif direction == "SHORT":
            stop_loss = entry + atr * config.ATR_MULTIPLIER_SL
            take_profit = entry - atr * config.ATR_MULTIPLIER_TP

    return {
        "direction": direction,
        "confidence": confidence,
        "weighted_score": weighted_score,
        "reasons": all_reasons,
        "warnings": all_warnings,
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
    }
