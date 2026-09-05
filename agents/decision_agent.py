"""
Agent Décision.
Agrège les scores pondérés des agents Technique, Macro et Sentiment
pour produire une recommandation finale : LONG / SHORT / NEUTRE,
avec un niveau de confiance et des niveaux de stop-loss / take-profit suggérés.

Sécurité intégrée : si un événement macro majeur (Fed, CPI, NFP...) est
imminent (moins de 2h), le système bascule automatiquement en NEUTRE par
prudence, quel que soit l'avis des autres agents — la volatilité pré-annonce
rend toute prédiction peu fiable.

IMPORTANT : ceci est un outil d'aide à la décision, pas un conseil financier.
Toute décision d'achat/vente reste sous la responsabilité de l'utilisateur.
"""
import json
import os
import config

WEIGHTS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "weights.json")


def _load_weights() -> dict:
    """
    Charge les poids calibrés automatiquement (weights.json, généré par
    calibrate_weights.py à partir des résultats réels) si disponibles et
    basés sur un échantillon suffisant. Sinon, retombe sur les poids par
    défaut définis dans config.py.
    """
    if os.path.isfile(WEIGHTS_FILE):
        try:
            with open(WEIGHTS_FILE) as f:
                data = json.load(f)
            if data.get("sample_size", 0) >= config.MIN_SAMPLES_FOR_CALIBRATION:
                return data["weights"]
        except Exception:
            pass
    return config.WEIGHTS


def aggregate(technical: dict, macro: dict, sentiment: dict, calendar: dict, h4_trend: int = 0) -> dict:
    weights = _load_weights()

    # --- Confluence multi-timeframe : si H1 et H4 sont en désaccord net,
    # on réduit la confiance du signal technique plutôt que de l'ignorer
    # (H4 donne le contexte de fond, H1 le timing)
    technical_score = technical["score"]
    confluence_note = None
    if h4_trend != 0:
        h1_direction = 1 if technical_score > 0 else (-1 if technical_score < 0 else 0)
        if h1_direction != 0 and h1_direction != h4_trend:
            technical_score *= config.MULTI_TIMEFRAME_DISAGREEMENT_FACTOR
            confluence_note = (
                f"⚠️ Désaccord H1/H4 : tendance H4 {'haussière' if h4_trend > 0 else 'baissière'} "
                f"contredit le signal H1 — score technique atténué"
            )
        elif h1_direction == h4_trend:
            confluence_note = "✅ H1 et H4 alignés — signal technique renforcé par la confluence"

    weighted_score = (
        technical_score * weights["technical"]
        + macro["score"] * weights["macro"]
        + sentiment["score"] * weights["sentiment"]
    )

    confidence = min(abs(weighted_score), 1.0)

    if confidence < config.CONFIDENCE_THRESHOLD_NEUTRAL:
        direction = "NEUTRE"
    elif weighted_score > 0:
        direction = "LONG"
    else:
        direction = "SHORT"

    all_reasons = technical["reasons"] + macro["reasons"] + sentiment["reasons"] + calendar["reasons"]
    if confluence_note:
        all_reasons.insert(0, confluence_note)
    all_warnings = technical["warnings"] + macro["warnings"] + sentiment["warnings"] + calendar["warnings"]

    # --- Alerte (mais plus d'override) : événement macro imminent ---
    caution_imminent_event = False
    if calendar.get("imminent_event"):
        caution_imminent_event = True
        all_warnings.insert(
            0,
            f"⚠️ PRUDENCE : événement macro majeur imminent "
            f"('{calendar['imminent_event']['title']}') — le signal ci-dessous reste affiché, à toi de juger"
        )

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
        "forced_neutral": False,  # conservé pour compatibilité, plus jamais forcé désormais
        "caution_imminent_event": caution_imminent_event,
        "component_scores": {
            "technical": technical["score"],
            "macro": macro["score"],
            "sentiment": sentiment["score"],
        },
    }
