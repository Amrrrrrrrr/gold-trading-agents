"""
Confirmation différée des signaux.
Inspiré des systèmes de trading algo les mieux notés : plutôt que d'agir dès
qu'un seuil est franchi, on attend que le signal se maintienne sur le cycle
suivant avant de le considérer "confirmé". Ça filtre les signaux qui
n'étaient qu'un pic isolé sur une seule bougie.

État persisté dans pending_signal.json (committé par le workflow, comme
weights.json), car chaque exécution GitHub Actions démarre sans mémoire.
"""
import json
import os
from datetime import datetime, timezone

STATE_PATH = os.path.join(os.path.dirname(__file__), "pending_signal.json")


def _load_state() -> dict:
    if os.path.isfile(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_state(state: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def check_confirmation(direction: str, now: datetime = None) -> dict:
    """
    Retourne {"confirmed": bool, "is_new_pending": bool, "pending_since": str|None}

    - Si direction est NEUTRE : on efface l'état en attente (le signal a disparu).
    - Si direction est LONG/SHORT et différente du pending précédent (ou aucun
      pending) : on démarre un nouveau pending, confirmed=False.
    - Si direction est LONG/SHORT et identique au pending précédent : confirmé,
      on efface le pending (prêt pour un nouveau cycle de confirmation après).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    state = _load_state()

    if direction == "NEUTRE":
        if state:
            _save_state({})
        return {"confirmed": False, "is_new_pending": False, "pending_since": None}

    if state.get("direction") == direction:
        pending_since = state.get("since")
        _save_state({})  # confirmé : on repart de zéro pour le prochain cycle
        return {"confirmed": True, "is_new_pending": False, "pending_since": pending_since}

    # Nouveau signal (différent du pending précédent, ou pas de pending)
    _save_state({"direction": direction, "since": now.isoformat()})
    return {"confirmed": False, "is_new_pending": True, "pending_since": now.isoformat()}
