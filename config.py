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

# --- Pondération des agents dans la décision finale ---
# La somme doit faire 1.0
WEIGHTS = {
    "technical": 0.40,
    "macro": 0.30,
    "sentiment": 0.30,
}

# --- Seuils de décision ---
CONFIDENCE_THRESHOLD_STRONG = 0.65   # au-dessus : signal jugé "fort"
CONFIDENCE_THRESHOLD_NEUTRAL = 0.15  # en dessous de cet écart : NEUTRE

# --- Gestion du risque (suggestions, pas des ordres automatiques) ---
ATR_MULTIPLIER_SL = 1.5   # stop-loss = prix +/- (ATR * ce multiplicateur)
ATR_MULTIPLIER_TP = 2.5   # take-profit = prix +/- (ATR * ce multiplicateur)
