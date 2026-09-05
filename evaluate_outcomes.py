"""
Évaluation des résultats passés.
Pour chaque décision loggée il y a plus de OUTCOME_EVALUATION_HOURS et pas
encore évaluée : récupère le prix actuel de l'or et détermine si le marché
a confirmé la direction prédite. Écrit le résultat dans decisions.csv.

Ce script est le prérequis de l'auto-calibration : sans savoir qui avait
raison, impossible d'ajuster intelligemment les poids des agents.
"""
import csv
import os
from datetime import datetime, timezone

import config
from agents import data_agent

LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "decisions.csv")


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def evaluate_pending_decisions():
    if not os.path.isfile(LOG_PATH):
        print("Aucun log de décisions trouvé, rien à évaluer.")
        return

    with open(LOG_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("Log vide, rien à évaluer.")
        return

    now = datetime.now(timezone.utc)

    # On récupère une seule fois l'historique récent du prix pour éviter
    # de multiplier les appels API (quota gratuit limité)
    gold_df = data_agent.get_gold_data(interval="1h", outputsize=200)

    updated_count = 0

    for row in rows:
        if row.get("outcome_evaluated_at"):
            continue  # déjà évalué

        if row["direction"] not in ("LONG", "SHORT"):
            # Pas de sens à évaluer un NEUTRE : il n'y a pas de direction à confirmer
            row["outcome_evaluated_at"] = now.isoformat()
            row["outcome_direction_correct"] = ""
            updated_count += 1
            continue

        decision_time = _parse_dt(row["timestamp_utc"])
        hours_elapsed = (now - decision_time).total_seconds() / 3600

        if hours_elapsed < config.OUTCOME_EVALUATION_HOURS:
            continue  # pas encore assez de recul

        # Chercher le prix le plus proche de (decision_time + OUTCOME_EVALUATION_HOURS)
        target_time = decision_time.replace(tzinfo=None)
        gold_df["time_diff"] = (gold_df["date"] - target_time).abs()
        closest_row = gold_df.loc[gold_df["time_diff"].idxmin()]

        outcome_price = float(closest_row["close"])
        entry_price = float(row["entry"])

        pct_move = ((outcome_price - entry_price) / entry_price) * 100

        if abs(pct_move) < config.OUTCOME_MIN_MOVE_PCT:
            correct = ""  # mouvement trop faible pour juger, on ignore ce cas
        elif row["direction"] == "LONG":
            correct = "True" if pct_move > 0 else "False"
        else:  # SHORT
            correct = "True" if pct_move < 0 else "False"

        row["outcome_price"] = round(outcome_price, 2)
        row["outcome_evaluated_at"] = now.isoformat()
        row["outcome_direction_correct"] = correct
        updated_count += 1

    if updated_count == 0:
        print("Rien de nouveau à évaluer ce cycle.")
        return

    with open(LOG_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"{updated_count} décision(s) évaluée(s).")


if __name__ == "__main__":
    evaluate_pending_decisions()
