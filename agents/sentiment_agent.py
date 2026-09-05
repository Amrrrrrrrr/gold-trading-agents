"""
Agent Sentiment / News — version renforcée.
Interroge plusieurs axes (or, Fed/taux, dollar/inflation) pour ne pas rater
les news qui font bouger l'or indirectement via la politique monétaire.

Le score est maintenant pondéré par la DENSITÉ de signal détecté :
un ratio positif/négatif franc sur seulement 2 titres pèse moins qu'un
ratio aussi franc sur 15 titres. Ça évite qu'un signal statistiquement
faible ait un impact disproportionné sur la décision finale.
"""
import requests
import config

NEWS_URL = "https://newsapi.org/v2/everything"

# Plusieurs angles de recherche : l'or est influencé indirectement par
# la politique monétaire et le dollar, pas seulement par les news qui le
# mentionnent explicitement.
SEARCH_QUERIES = [
    "gold price XAUUSD",
    "Federal Reserve interest rate",
    "US inflation CPI dollar",
]

POSITIVE_WORDS = [
    "rall", "surg", "gain", "ris", "climb", "safe haven", "haven demand",
    "record high", "boost", "soar", "dovish", "cut rates",
    "hausse", "flambée", "soutien", "refuge",
]
NEGATIVE_WORDS = [
    "fall", "drop", "declin", "sell-off", "selloff", "plung", "slump", "tumbl",
    "hawkish", "rate hike", "raise rates", "strong dollar",
    "baisse", "chute", "recul", "pression",
]

# Nombre minimum de signaux détectés pour atteindre la confiance maximale.
# En dessous, le score est proportionnellement réduit (coverage factor).
MIN_SIGNALS_FOR_FULL_CONFIDENCE = 10


def fetch_gold_headlines(page_size: int = 30) -> list:
    """Interroge plusieurs requêtes et dédoublonne les titres obtenus."""
    all_titles = set()

    for query in SEARCH_QUERIES:
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": page_size,
            "apiKey": config.NEWS_API_KEY,
        }
        try:
            response = requests.get(NEWS_URL, params=params, timeout=15)
            data = response.json()
            if data.get("status") != "ok":
                continue
            for article in data.get("articles", []):
                if article.get("title"):
                    all_titles.add(article["title"])
        except Exception:
            continue  # une requête ratée ne doit pas bloquer les autres

    return list(all_titles)


def analyze(headlines: list) -> dict:
    reasons = []
    warnings = []

    if not headlines:
        warnings.append("Aucune actualité récente trouvée (or / Fed / dollar)")
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
        reasons.append(f"Ton neutre sur {len(headlines)} titres analysés (or/Fed/dollar), pas de signal clair")
        return {"score": 0.0, "reasons": reasons, "warnings": warnings}

    # Direction du signal (entre -1 et 1)
    raw_score = (positive_count - negative_count) / total_signals

    # Facteur de couverture : réduit l'impact si peu de signaux détectés,
    # pour éviter qu'un ratio extrême sur 2 titres pèse comme un vrai consensus
    coverage = min(total_signals / MIN_SIGNALS_FOR_FULL_CONFIDENCE, 1.0)

    score = raw_score * coverage

    reasons.append(
        f"Sentiment (or/Fed/dollar) : {positive_count} signaux positifs vs "
        f"{negative_count} négatifs, sur {len(headlines)} titres uniques analysés "
        f"(couverture {coverage*100:.0f}%)"
    )

    if coverage < 0.5:
        warnings.append("Peu de signaux détectés dans les news : sentiment peu fiable ce cycle")

    return {"score": score, "reasons": reasons, "warnings": warnings}
