"""
Logger de décisions.
Enregistre chaque cycle dans logs/decisions.csv pour permettre, plus tard,
de comparer les décisions prises aux mouvements réels du marché et calculer
un vrai taux de réussite (au lieu de juger "à l'oeil").
"""
import csv
import os
from datetime import datetime, timezone

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_PATH = os.path.join(LOG_DIR, "decisions.csv")

FIELDNAMES = [
    "timestamp_utc",
    "direction",
    "confidence",
    "weighted_score",
    "entry",
    "stop_loss",
    "take_profit",
    "forced_neutral",
    "reasons",
    "warnings",
]


def log_decision(decision: dict) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    file_exists = os.path.isfile(LOG_PATH)

    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "direction": decision["direction"],
        "confidence": round(decision["confidence"], 4),
        "weighted_score": round(decision["weighted_score"], 4),
        "entry": decision["entry"],
        "stop_loss": decision["stop_loss"],
        "take_profit": decision["take_profit"],
        "forced_neutral": decision.get("forced_neutral", False),
        "reasons": " | ".join(decision["reasons"]),
        "warnings": " | ".join(decision["warnings"]),
    }

    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
