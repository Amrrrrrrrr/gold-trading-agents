"""
Agent Sentiment / News.
Récupère les titres d'actualité récents mentionnant l'or via NewsAPI
(offre gratuite : 100 requêtes/jour) et calcule un score de sentiment
simple basé sur un lexique de mots-clés.

Limite connue : c'est une analyse lexicale simple, pas un vrai modèle NLP.
Suffisant pour une v1, améliorable plus tard avec un modèle de sentiment dédié.
"""
import requests
import config

NEWS_URL = "https://newsapi.org/v2/everything"

POSITIVE_WORDS = [
    "rall", "surg", "gain", "ris", "climb", "safe haven", "haven demand",
    "record high", "boost", "soar", "hausse", "flambée", "soutien", "refuge",
]
NEGATIVE_WORDS = [
    "fall", "drop", "declin", "sell-off", "selloff", "plung", "slump", "tumbl",
    "baisse", "chute", "recul", "pression",
]


def fetch_gold_headlines(page_size: int = 20) -> list:
    params = {
        "q": "gold price OR XAUUSD OR \"or (métal)\"",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": page_size,
        "apiKey": config.NEWS_API_KEY,
    }
    response = requests.get(NEWS_URL, params=params, timeout=15)
    data = response.json()
    if data.get("status") != "ok":
        raise RuntimeError(f"Erreur NewsAPI: {data}")
    return [article["title"] for article in data.get("articles", []) if article.get("title")]


def analyze(headlines: list) -> dict:
    reasons = []
    warnings = []

    if not headlines:
        warnings.append("Aucune actualité récente trouvée sur l'or")
        return {"score": 0.0, "reasons": reasons, "warnings": warnings}

    positive_count = 0
    negative_count = 0

    for title in headlines:
        title_lower = title.lower()
        if any(word in title_lower for word in POSITIVE_WORDS):
            positive_count += 1
        if any(word in title_lower for word in NEGATIVE_WORDS):
            negative_count += 1

    total_signals = positive_count + negative_count
    if total_signals == 0:
        reasons.append("Ton des news neutre, pas de signal clair")
        return {"score": 0.0, "reasons": reasons, "warnings": warnings}

    score = (positive_count - negative_count) / max(len(headlines), 1)
    score = max(-1.0, min(1.0, score * 2))  # amplifié pour être exploitable

    reasons.append(
        f"Sentiment news : {positive_count} titres positifs vs {negative_count} négatifs "
        f"sur {len(headlines)} analysés"
    )

    return {"score": score, "reasons": reasons, "warnings": warnings}
