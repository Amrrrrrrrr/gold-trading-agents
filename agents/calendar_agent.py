"""
Agent Calendrier Économique.
Récupère le calendrier économique hebdomadaire via le flux public et gratuit
de ForexFactory (utilisé largement par la communauté des traders algo,
aucune clé API nécessaire) : https://nfs.faireconomy.media/ff_calendar_thisweek.json

Filtre les événements à fort impact sur le dollar / l'or : décisions de taux
Fed, CPI, NFP (emploi), PCE, GDP, discours de membres de la Fed.
"""
import requests
from datetime import datetime, timedelta, timezone

CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Mots-clés identifiant les événements à fort impact sur l'or via le dollar
HIGH_IMPACT_KEYWORDS = [
    "fed", "fomc", "interest rate", "rate decision", "powell",
    "cpi", "inflation", "core cpi",
    "non-farm", "nonfarm", "nfp", "employment change", "unemployment",
    "gdp", "pce", "retail sales", "jobless claims",
]


def fetch_calendar() -> list:
    """Récupère le calendrier brut de la semaine en cours."""
    response = requests.get(CALENDAR_URL, timeout=15)
    response.raise_for_status()
    return response.json()


def _parse_event_time(event: dict):
    """Le flux expose la date sous 'date' (ISO) selon les versions du flux."""
    date_str = event.get("date") or event.get("datetime")
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_relevant_usd_events(events: list) -> list:
    """Filtre : devise USD + impact élevé + mot-clé pertinent pour l'or."""
    relevant = []
    for event in events:
        country = (event.get("country") or event.get("currency") or "").upper()
        impact = (event.get("impact") or "").lower()
        title = (event.get("title") or event.get("event") or "").lower()

        if country != "USD":
            continue
        if impact not in ("high", "3", "red"):
            continue
        if not any(keyword in title for keyword in HIGH_IMPACT_KEYWORDS):
            continue

        relevant.append(event)
    return relevant


def analyze(now: datetime = None) -> dict:
    """
    Retourne :
    - reasons / warnings : phrases explicatives
    - imminent_event : dict de l'événement si un événement à fort impact est
      prévu dans les 2 prochaines heures (déclenche la prudence dans la décision)
    - recent_event : dict si un événement à fort impact vient de sortir
      (dans les 3 dernières heures)
    """
    if now is None:
        now = datetime.now(timezone.utc)

    reasons = []
    warnings = []
    imminent_event = None
    recent_event = None

    try:
        raw_events = fetch_calendar()
    except Exception as e:
        warnings.append(f"Calendrier économique indisponible ce cycle ({e})")
        return {
            "reasons": reasons,
            "warnings": warnings,
            "imminent_event": None,
            "recent_event": None,
        }

    relevant_events = get_relevant_usd_events(raw_events)

    for event in relevant_events:
        event_time = _parse_event_time(event)
        if event_time is None:
            continue
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        delta = event_time - now
        title = event.get("title") or event.get("event")

        # Événement dans les 2 prochaines heures
        if timedelta(0) <= delta <= timedelta(hours=2):
            imminent_event = {"title": title, "time": event_time.isoformat()}
            warnings.append(
                f"Événement macro majeur imminent : '{title}' dans "
                f"{int(delta.total_seconds() // 60)} min — prudence recommandée"
            )

        # Événement sorti dans les 3 dernières heures
        elif timedelta(hours=-3) <= delta < timedelta(0):
            recent_event = {"title": title, "time": event_time.isoformat()}
            reasons.append(
                f"Événement macro récent : '{title}' publié il y a "
                f"{int(-delta.total_seconds() // 60)} min"
            )

    if not relevant_events:
        reasons.append("Aucun événement macro à fort impact cette semaine (ou déjà passé)")

    return {
        "reasons": reasons,
        "warnings": warnings,
        "imminent_event": imminent_event,
        "recent_event": recent_event,
    }
