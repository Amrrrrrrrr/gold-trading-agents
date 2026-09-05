"""
Agent Macro.
Combine deux sources :
1. Tendance récente d'EUR/USD comme proxy de la force du dollar (le DXY
   officiel n'est pas disponible sur le plan gratuit Twelve Data). L'or est
   fortement anti-corrélé au dollar : si EUR/USD monte, le dollar s'affaiblit,
   ce qui est généralement favorable à l'or — et inversement.
2. Le contexte du calendrier économique (événement macro récent) fourni par
   calendar_agent, intégré ici comme contexte informatif (pas de score
   directionnel dessus, car on ne connaît pas encore la réaction du marché
   sans backtesting — seulement la présence de l'événement).
"""
import pandas as pd


def analyze(dxy_df: pd.DataFrame) -> dict:
    df = dxy_df.copy()
    reasons = []
    warnings = []
    score = 0.0

    if len(df) < 6:
        warnings.append("Pas assez de données EUR/USD pour une analyse macro fiable")
        return {"score": 0.0, "reasons": reasons, "warnings": warnings}

    last_close = df["close"].iloc[-1]
    close_6h_ago = df["close"].iloc[-6]
    pct_change = ((last_close - close_6h_ago) / close_6h_ago) * 100

    if pct_change > 0.15:
        score += 0.6
        reasons.append(
            f"EUR/USD en hausse de {pct_change:.2f}% sur 6h (dollar affaibli) — favorable à l'or"
        )
    elif pct_change < -0.15:
        score -= 0.6
        reasons.append(
            f"EUR/USD en baisse de {abs(pct_change):.2f}% sur 6h (dollar renforcé) — défavorable à l'or"
        )
    else:
        reasons.append(f"EUR/USD stable ({pct_change:+.2f}% sur 6h) — pas de signal macro fort")

    score = max(-1.0, min(1.0, score))
    return {"score": score, "reasons": reasons, "warnings": warnings}
