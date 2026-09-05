"""
Auto-calibration des poids.
Analyse les décisions évaluées (evaluate_outcomes.py) pour mesurer le taux
de réussite de CHAQUE agent individuellement (pas juste la décision finale) :
est-ce que le signe du score de l'agent technique correspondait à la
direction réelle du marché ? Et pour macro ? Et pour sentiment ?

Les agents les plus fiables historiquement reçoivent un poids plus élevé.
Nécessite un minimum d'échantillons (config.MIN_SAMPLES_FOR_CALIBRATION)
avant de faire confiance aux résultats calculés — sinon on garde les poids
par défaut, pour éviter de sur-ajuster sur trop peu de données.
"""
import csv
import json
import os

import config

LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "decisions.csv")
WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "weights.json")

COMPONENTS = ["technical", "macro", "sentiment"]


def calibrate():
    if not os.path.isfile(LOG_PATH):
        print("Aucun log trouvé, calibration impossible.")
        return

    with open(LOG_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # On ne garde que les lignes évaluées avec un résultat exploitable
    evaluated = [
        r for r in rows
        if r.get("outcome_direction_correct") in ("True", "False")
    ]

    sample_size = len(evaluated)

    if sample_size < config.MIN_SAMPLES_FOR_CALIBRATION:
        print(
            f"Seulement {sample_size} décisions évaluables "
            f"(minimum requis : {config.MIN_SAMPLES_FOR_CALIBRATION}). "
            f"Poids par défaut conservés."
        )
        # On écrit quand même le sample_size pour que decision_agent sache
        # où on en est, mais avec les poids par défaut
        _write_weights(config.WEIGHTS, sample_size)
        return

    hit_counts = {c: 0 for c in COMPONENTS}
    total_counts = {c: 0 for c in COMPONENTS}

    for row in evaluated:
        actual_correct_direction = row["outcome_direction_correct"] == "True"
        # Si la décision finale était correcte, le mouvement réel allait dans
        # le sens de weighted_score positif si LONG, négatif si SHORT.
        real_move_was_up = (
            (row["direction"] == "LONG" and actual_correct_direction)
            or (row["direction"] == "SHORT" and not actual_correct_direction)
        )

        for component in COMPONENTS:
            score = float(row.get(f"{component}_score", 0) or 0)
            if abs(score) < 0.05:
                continue  # agent quasi neutre sur ce cycle, pas de pari fait
            total_counts[component] += 1
            component_predicted_up = score > 0
            if component_predicted_up == real_move_was_up:
                hit_counts[component] += 1

    hit_rates = {}
    for c in COMPONENTS:
        if total_counts[c] > 0:
            hit_rates[c] = hit_counts[c] / total_counts[c]
        else:
            hit_rates[c] = 0.5  # aucune donnée : neutre

    # Normaliser les hit rates en poids qui somment à 1.0
    total_rate = sum(hit_rates.values())
    if total_rate == 0:
        new_weights = config.WEIGHTS
    else:
        new_weights = {c: hit_rates[c] / total_rate for c in COMPONENTS}

    _write_weights(new_weights, sample_size, hit_rates)

    print(f"Calibration effectuée sur {sample_size} décisions évaluées.")
    for c in COMPONENTS:
        print(f"  {c}: taux de réussite {hit_rates[c]*100:.0f}% -> poids {new_weights[c]:.2f}")


def _write_weights(weights: dict, sample_size: int, hit_rates: dict = None):
    data = {
        "weights": weights,
        "sample_size": sample_size,
        "hit_rates": hit_rates or {},
    }
    with open(WEIGHTS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    calibrate()
