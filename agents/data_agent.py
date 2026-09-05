"""
Agent Données Marché.
Récupère les données OHLCV récentes pour XAU/USD (et DXY pour le contexte macro)
via l'API Twelve Data (offre gratuite : 800 requêtes/jour, largement suffisant
pour un check horaire).
"""
import requests
import pandas as pd
import config

BASE_URL = "https://api.twelvedata.com/time_series"


def fetch_ohlcv(symbol: str, interval: str = "1h", outputsize: int = 100) -> pd.DataFrame:
    """
    Récupère les bougies OHLCV pour un symbole donné.
    Retourne un DataFrame trié du plus ancien au plus récent.
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": config.TWELVE_DATA_API_KEY,
    }
    response = requests.get(BASE_URL, params=params, timeout=15)
    data = response.json()

    if "values" not in data:
        raise RuntimeError(f"Erreur API Twelve Data pour {symbol}: {data}")

    df = pd.DataFrame(data["values"])
    df = df.rename(columns={"datetime": "date"})
    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def get_gold_data(interval: str = "1h", outputsize: int = 100) -> pd.DataFrame:
    return fetch_ohlcv(config.SYMBOL, interval=interval, outputsize=outputsize)


def get_dxy_data(interval: str = "1h", outputsize: int = 100) -> pd.DataFrame:
    return fetch_ohlcv(config.DXY_SYMBOL, interval=interval, outputsize=outputsize)


if __name__ == "__main__":
    # Test rapide en isolation
    df = get_gold_data(outputsize=10)
    print(df.tail())
