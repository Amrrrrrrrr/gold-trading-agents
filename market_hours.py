"""
Détection des heures de marché.
L'or (comme le forex) trade en continu du dimanche soir au vendredi soir
(heure de New York), avec un arrêt le week-end. Les horaires exacts varient
légèrement selon le broker — ceci est une approximation standard du marché.
À vérifier/ajuster selon les horaires précis affichés sur XTB si besoin.
"""
from datetime import datetime, timezone

# Fermeture vendredi à partir de 21h00 UTC, réouverture dimanche à 22h00 UTC
FRIDAY_CLOSE_HOUR_UTC = 21
SUNDAY_OPEN_HOUR_UTC = 22

# Session active Londres/New York : c'est là que l'or a le plus de liquidité
# et de mouvements fiables. En dehors (nuit asiatique), le bruit domine.
ACTIVE_SESSION_START_UTC = 7   # ouverture de Londres
ACTIVE_SESSION_END_UTC = 21    # clôture de New York
PRIME_SESSION_START_UTC = 13   # chevauchement Londres/NY (meilleure liquidité)
PRIME_SESSION_END_UTC = 17


def is_market_open(now: datetime = None) -> bool:
    if now is None:
        now = datetime.now(timezone.utc)

    weekday = now.weekday()  # lundi=0 ... dimanche=6

    if weekday == 5:  # samedi : toujours fermé
        return False
    if weekday == 4 and now.hour >= FRIDAY_CLOSE_HOUR_UTC:  # vendredi soir
        return False
    if weekday == 6 and now.hour < SUNDAY_OPEN_HOUR_UTC:  # dimanche avant réouverture
        return False

    return True


def is_active_session(now: datetime = None) -> bool:
    """Londres + New York, la plage horaire la plus liquide pour l'or."""
    if now is None:
        now = datetime.now(timezone.utc)
    return ACTIVE_SESSION_START_UTC <= now.hour < ACTIVE_SESSION_END_UTC


def is_prime_session(now: datetime = None) -> bool:
    """Chevauchement Londres/NY : la fenêtre la plus fiable de la journée."""
    if now is None:
        now = datetime.now(timezone.utc)
    return PRIME_SESSION_START_UTC <= now.hour < PRIME_SESSION_END_UTC
