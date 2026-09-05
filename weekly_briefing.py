"""
Briefing hebdomadaire.
Envoyé chaque dimanche soir : résumé des événements macro majeurs (Fed, CPI,
NFP...) prévus pour la semaine à venir, pour que l'utilisateur puisse s'y
préparer à l'avance plutôt que de découvrir un événement à la dernière heure.
"""
from datetime import datetime, timezone

from agents import calendar_agent
import telegram_bot


def build_weekly_briefing() -> str:
    try:
        raw_events = calendar_agent.fetch_calendar()
    except Exception as e:
        return f"⚠️ Impossible de récupérer le calendrier économique cette semaine ({e})"

    relevant = calendar_agent.get_relevant_usd_events(raw_events)

    now = datetime.now(timezone.utc)
    upcoming = []
    for event in relevant:
        event_time = calendar_agent._parse_event_time(event)
        if event_time is None:
            continue
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        if event_time >= now:
            upcoming.append((event, event_time))

    if not upcoming:
        return "📅 SEMAINE À VENIR — OR (XAU/USD)\n\nAucun événement macro majeur restant cette semaine."

    lines = ["📅 SEMAINE À VENIR — OR (XAU/USD)", "", "Événements macro majeurs à surveiller :"]

    for event, event_time in sorted(upcoming, key=lambda x: x[1]):
        title = event.get("title") or event.get("event")
        date_str = event_time.strftime("%A %d/%m à %H:%M UTC")
        lines.append(f"• {date_str} — {title}")

    lines.append("")
    lines.append("Le système passera automatiquement en NEUTRE dans les 2h précédant chaque événement.")

    return "\n".join(lines)


if __name__ == "__main__":
    message = build_weekly_briefing()
    telegram_bot.send_message(message)
    print(f"[{datetime.now(timezone.utc)}] Briefing hebdomadaire envoyé.")
