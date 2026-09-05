"""
Agent Gestion du Risque.
Calcule la taille de position suggérée (en lots XAUUSD) selon :
- Le capital du compte (config.ACCOUNT_BALANCE_EUR)
- Le % de risque max par trade (config.RISK_PER_TRADE_PCT)
- La distance jusqu'au stop-loss (déterminée par l'ATR, via l'agent technique)

Convention standard XAUUSD : 1 lot = 100 onces troy (à vérifier sur la fiche
produit XTB exacte, cette convention est très largement répandue mais peut
varier légèrement selon le broker).

IMPORTANT : c'est une suggestion de calcul, pas une garantie. Vérifie toujours
la taille affichée dans XTB avant de valider un ordre.
"""
import math
import config

CONTRACT_SIZE_OZ = 100  # 1 lot standard XAUUSD = 100 onces troy
MIN_LOT_STEP = 0.01


def compute_position_size(decision: dict, eur_usd_rate: float = 1.0) -> dict:
    """
    Retourne un dict avec :
    - lot_size : taille suggérée, arrondie au pas minimum (0.01)
    - risk_amount_eur : montant réellement risqué en euros
    - notional_value_usd : valeur totale de la position exposée
    - warning : message si la taille calculée est en dessous du lot minimum
    """
    if decision["direction"] not in ("LONG", "SHORT"):
        return None

    entry = decision.get("entry")
    stop_loss = decision.get("stop_loss")

    if entry is None or stop_loss is None:
        return None

    stop_distance_usd = abs(entry - stop_loss)
    if stop_distance_usd <= 0:
        return None

    risk_amount_eur = config.ACCOUNT_BALANCE_EUR * config.RISK_PER_TRADE_PCT
    risk_amount_usd = risk_amount_eur * eur_usd_rate

    raw_lot_size = risk_amount_usd / (stop_distance_usd * CONTRACT_SIZE_OZ)
    lot_size = math.floor(raw_lot_size / MIN_LOT_STEP) * MIN_LOT_STEP

    warning = None
    if lot_size < MIN_LOT_STEP:
        warning = (
            f"Taille calculée ({raw_lot_size:.4f} lot) en dessous du minimum "
            f"({MIN_LOT_STEP} lot) — le stop est trop large pour ton niveau de risque actuel"
        )
        lot_size = MIN_LOT_STEP  # on affiche quand même le minimum possible, à titre indicatif

    notional_value_usd = lot_size * CONTRACT_SIZE_OZ * entry

    return {
        "lot_size": round(lot_size, 2),
        "risk_amount_eur": round(risk_amount_eur, 2),
        "notional_value_usd": round(notional_value_usd, 2),
        "warning": warning,
    }
