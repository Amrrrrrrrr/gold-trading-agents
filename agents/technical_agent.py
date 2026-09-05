"""
Agent Analyse Technique — version continue.
Calcule des indicateurs classiques (SMA, RSI, ATR) sur les données de prix de
l'or et en déduit un score directionnel entre -1 (baissier fort) et +1
(haussier fort).

Contrairement à une v1 à paliers fixes (ex: "RSI > 50 -> +0.15" peu importe
si RSI = 51 ou 69), le score est ici continu : un écart de tendance ou un
RSI plus extrême pèse proportionnellement plus lourd dans la décision finale.
"""
import pandas as pd
import config

# Poids internes des deux composantes (somme = 1.0, le score final agent
# reste dans [-1, 1] avant d'être pondéré par WEIGHTS["technical"] globalement)
TREND_WEIGHT = 0.6
MOMENTUM_WEIGHT = 0.4

# Écart (%) entre moyennes mobiles au-delà duquel on considère la tendance
# comme "pleinement forte" (score de tendance saturé à +/-1 sur sa composante)
TREND_MAX_GAP_PCT = 1.0


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


def _clip(value: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def analyze(df: pd.DataFrame) -> dict:
    """
    Retourne un dict avec :
    - score : float entre -1 et 1 (continu)
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

    # --- Tendance (écart relatif entre moyennes mobiles, continu) ---
    if pd.notna(last["sma_short"]) and pd.notna(last["sma_long"]):
        gap_pct = ((last["sma_short"] - last["sma_long"]) / last["sma_long"]) * 100
        trend_component = _clip(gap_pct / TREND_MAX_GAP_PCT) * TREND_WEIGHT
        score += trend_component

        direction_word = "haussière" if gap_pct > 0 else "baissière"
        strength_word = "forte" if abs(gap_pct) >= TREND_MAX_GAP_PCT else "modérée" if abs(gap_pct) >= TREND_MAX_GAP_PCT / 3 else "faible"
        reasons.append(
            f"Tendance {direction_word} {strength_word} : écart de {gap_pct:+.2f}% entre "
            f"moyenne courte ({last['sma_short']:.2f}) et longue ({last['sma_long']:.2f})"
        )

    # --- Momentum (RSI, distance continue à 50) ---
    if pd.notna(last["rsi"]):
        rsi_val = last["rsi"]
        momentum_component = _clip((rsi_val - 50) / 50) * MOMENTUM_WEIGHT
        score += momentum_component

        if rsi_val > 70:
            warnings.append(f"RSI à {rsi_val:.0f} : zone de surachat, risque de repli")
        elif rsi_val < 30:
            warnings.append(f"RSI à {rsi_val:.0f} : zone de survente, risque de rebond")
        else:
            direction_word = "haussier" if rsi_val > 50 else "baissier"
            reasons.append(f"RSI à {rsi_val:.0f} : momentum {direction_word}, intensité proportionnelle à l'écart avec 50")

    # --- Volatilité (ATR) pour prudence ---
    if pd.notna(last["atr"]):
        atr_pct = (last["atr"] / last["close"]) * 100
        if atr_pct > 1.5:
            warnings.append(f"Volatilité élevée (ATR = {atr_pct:.2f}% du prix)")

    score = _clip(score)

    return {
        "score": score,
        "reasons": reasons,
        "warnings": warnings,
        "last_price": float(last["close"]),
        "atr": float(last["atr"]) if pd.notna(last["atr"]) else None,
    }
