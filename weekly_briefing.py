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

    if not relevant:
        return "📅 SEMAINE À VENIR — OR (XAU/USD)\n\nAucun événement macro majeur détecté pour cette semaine."

    lines = ["📅 SEMAINE À VENIR — OR (XAU/USD)", "", "Événements macro majeurs à surveiller :"]

    for event in sorted(relevant, key=lambda e: e.get("date", "")):
        title = event.get("title") or event.get("event")
        event_time = calendar_agent._parse_event_time(event)
        if event_time:
            date_str = event_time.strftime("%A %d/%m à %H:%M UTC")
        else:
            date_str = "date inconnue"
        lines.append(f"• {date_str} — {title}")

    lines.append("")
    lines.append("Le système passera automatiquement en NEUTRE dans les 2h précédant chaque événement.")

    return "\n".join(lines)


if __name__ == "__main__":
    message = build_weekly_briefing()
    telegram_bot.send_message(message)
    print(f"[{datetime.now(timezone.utc)}] Briefing hebdomadaire envoyé.")
