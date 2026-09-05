"""
Agent Analyse Technique.
Calcule des indicateurs classiques (SMA, RSI, ATR) sur les données de prix de l'or
et en déduit un score directionnel entre -1 (baissier fort) et +1 (haussier fort),
accompagné d'explications lisibles.
"""
import pandas as pd
import config


def compute_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-9)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=period).mean()


def analyze(df: pd.DataFrame) -> dict:
    """
    Retourne un dict avec :
    - score : float entre -1 et 1
    - reasons : liste de phrases explicatives
    - warnings : signaux contraires ou points de prudence
    - last_price, atr (utiles pour le calcul de SL/TP)
    """
    df = df.copy()
    df["sma_short"] = compute_sma(df["close"], config.SMA_SHORT)
    df["sma_long"] = compute_sma(df["close"], config.SMA_LONG)
    df["rsi"] = compute_rsi(df["close"], config.RSI_PERIOD)
    df["atr"] = compute_atr(df, config.ATR_PERIOD)

    last = df.iloc[-1]
    reasons = []
    warnings = []
    score = 0.0

    # --- Tendance (croisement de moyennes mobiles) ---
    if pd.notna(last["sma_short"]) and pd.notna(last["sma_long"]):
        if last["sma_short"] > last["sma_long"]:
            score += 0.4
            reasons.append(
                f"Tendance haussière : moyenne courte ({last['sma_short']:.2f}) "
                f"au-dessus de la moyenne longue ({last['sma_long']:.2f})"
            )
        else:
            score -= 0.4
            reasons.append(
                f"Tendance baissière : moyenne courte ({last['sma_short']:.2f}) "
                f"sous la moyenne longue ({last['sma_long']:.2f})"
            )

    # --- Momentum (RSI) ---
    if pd.notna(last["rsi"]):
        rsi_val = last["rsi"]
        if rsi_val > 70:
            score -= 0.3
            warnings.append(f"RSI à {rsi_val:.0f} : zone de surachat, risque de repli")
        elif rsi_val < 30:
            score += 0.3
            warnings.append(f"RSI à {rsi_val:.0f} : zone de survente, risque de rebond")
        elif rsi_val > 50:
            score += 0.15
            reasons.append(f"RSI à {rsi_val:.0f} : momentum haussier modéré")
        else:
            score -= 0.15
            reasons.append(f"RSI à {rsi_val:.0f} : momentum baissier modéré")

    # --- Volatilité (ATR) pour prudence ---
    if pd.notna(last["atr"]):
        atr_pct = (last["atr"] / last["close"]) * 100
        if atr_pct > 1.5:
            warnings.append(f"Volatilité élevée (ATR = {atr_pct:.2f}% du prix)")

    score = max(-1.0, min(1.0, score))

    return {
        "score": score,
        "reasons": reasons,
        "warnings": warnings,
        "last_price": float(last["close"]),
        "atr": float(last["atr"]) if pd.notna(last["atr"]) else None,
    }
