"""
Configuration centrale du projet.
Toutes les clés sont lues depuis les variables d'environnement (.env).
Ne jamais mettre de vraies clés directement dans ce fichier.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# --- Marché suivi ---
SYMBOL = "XAU/USD"          # Or contre dollar
DXY_SYMBOL = "EUR/USD"      # Proxy de force du dollar (DXY non dispo en plan gratuit Twelve Data)

# --- Fréquence ---
CHECK_INTERVAL_SECONDS = 60 * 60  # toutes les heures

# --- Paramètres techniques ---
SMA_SHORT = 20
SMA_LONG = 50
RSI_PERIOD = 14
ATR_PERIOD = 14

# --- Confluence multi-timeframe (H1 + H4) ---
# Facteur appliqué au score technique H1 si la tendance H4 est contraire
# (0.4 = on garde 40% de la force du signal, on ne l'annule pas totalement)
MULTI_TIMEFRAME_DISAGREEMENT_FACTOR = 0.4

# --- Pondération des agents dans la décision finale ---
# La somme doit faire 1.0
WEIGHTS = {
    "technical": 0.35,
    "macro": 0.35,
    "sentiment": 0.30,
}

# --- Seuils de décision ---
CONFIDENCE_THRESHOLD_STRONG = 0.65   # au-dessus : signal jugé "fort"
CONFIDENCE_THRESHOLD_NEUTRAL = 0.45  # en dessous de cet écart : NEUTRE (calibré via backtest)

# Délai minimum entre deux décisions directionnelles (LONG/SHORT), pour éviter
# la sur-réaction et le bruit — calibré via backtest (meilleur ratio réussite/fréquence)
TRADE_COOLDOWN_HOURS = 24

# --- Auto-calibration ---
# Nombre minimum de décisions évaluées avant de faire confiance aux poids
# auto-calibrés plutôt qu'aux poids par défaut ci-dessus
MIN_SAMPLES_FOR_CALIBRATION = 30

# Fenêtre après une décision pour juger si le marché lui a donné raison (heures)
OUTCOME_EVALUATION_HOURS = 4

# Mouvement de prix minimum (%) pour considérer que le marché a "confirmé"
# une direction plutôt que d'être resté plat
OUTCOME_MIN_MOVE_PCT = 0.10

# Coût de spread estimé pour un aller-retour sur XAUUSD (en dollars, à ajuster
# selon le spread réel affiché sur XTB — varie selon le compte/l'heure)
SPREAD_COST_USD = 0.30

# --- Gestion du risque (suggestions, pas des ordres automatiques) ---
ATR_MULTIPLIER_SL = 1.5   # stop-loss = prix +/- (ATR * ce multiplicateur)
ATR_MULTIPLIER_TP = 2.5   # take-profit = prix +/- (ATR * ce multiplicateur)

# Capital et risque par trade — À AJUSTER avec ton montant exact sur XTB
ACCOUNT_BALANCE_EUR = 500.0
RISK_PER_TRADE_PCT = 0.02  # 2% du capital max risqué par trade
