"""
Logger de décisions.
Enregistre chaque cycle dans logs/decisions.csv, y compris le score
individuel de chaque agent (nécessaire pour l'auto-calibration ultérieure
via evaluate_outcomes.py et calibrate_weights.py).
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
    "technical_score",
    "macro_score",
    "sentiment_score",
    "entry",
    "stop_loss",
    "take_profit",
    "forced_neutral",
    "reasons",
    "warnings",
    # Colonnes remplies plus tard par evaluate_outcomes.py :
    "outcome_price",
    "outcome_evaluated_at",
    "outcome_direction_correct",
]


def log_decision(decision: dict) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    file_exists = os.path.isfile(LOG_PATH)

    components = decision.get("component_scores", {})

    row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "direction": decision["direction"],
        "confidence": round(decision["confidence"], 4),
        "weighted_score": round(decision["weighted_score"], 4),
        "technical_score": round(components.get("technical", 0.0), 4),
        "macro_score": round(components.get("macro", 0.0), 4),
        "sentiment_score": round(components.get("sentiment", 0.0), 4),
        "entry": decision["entry"],
        "stop_loss": decision["stop_loss"],
        "take_profit": decision["take_profit"],
        "forced_neutral": decision.get("forced_neutral", False),
        "reasons": " | ".join(decision["reasons"]),
        "warnings": " | ".join(decision["warnings"]),
        "outcome_price": "",
        "outcome_evaluated_at": "",
        "outcome_direction_correct": "",
    }

    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
