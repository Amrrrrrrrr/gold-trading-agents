"""
Briefing hebdomadaire.
Envoyé chaque dimanche soir : résumé des événements macro majeurs (Fed, CPI,
NFP...) prévus pour la semaine à venir + statistiques de performance de la
semaine écoulée, pour suivre l'évolution sans devoir ouvrir le CSV brut.
"""
import csv
import os
from datetime import datetime, timezone, timedelta

from agents import calendar_agent
import telegram_bot

LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "decisions.csv")


def build_calendar_section() -> str:
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
        return "📅 Aucun événement macro majeur restant cette semaine."

    lines = ["📅 Événements macro majeurs à surveiller :"]
    for event, event_time in sorted(upcoming, key=lambda x: x[1]):
        title = event.get("title") or event.get("event")
        date_str = event_time.strftime("%A %d/%m à %H:%M UTC")
        lines.append(f"• {date_str} — {title}")

    return "\n".join(lines)


def build_performance_section() -> str:
    if not os.path.isfile(LOG_PATH):
        return "📊 Pas encore de données de performance (système récemment lancé)."

    with open(LOG_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    recent_rows = [
        r for r in rows
        if datetime.fromisoformat(r["timestamp_utc"]) >= week_ago
    ]

    if not recent_rows:
        return "📊 Aucune décision cette semaine (marché fermé ou système en pause)."

    total = len(recent_rows)
    long_count = sum(1 for r in recent_rows if r["direction"] == "LONG")
    short_count = sum(1 for r in recent_rows if r["direction"] == "SHORT")
    neutral_count = sum(1 for r in recent_rows if r["direction"] == "NEUTRE")

    evaluated = [r for r in recent_rows if r.get("outcome_direction_correct") in ("True", "False")]
    correct = sum(1 for r in evaluated if r["outcome_direction_correct"] == "True")

    lines = [
        "📊 PERFORMANCE DE LA SEMAINE :",
        f"• {total} décisions au total ({long_count} LONG, {short_count} SHORT, {neutral_count} NEUTRE)",
    ]

    if evaluated:
        hit_rate = (correct / len(evaluated)) * 100
        lines.append(f"• {len(evaluated)} décisions directionnelles évaluées, taux de réussite : {hit_rate:.0f}%")
    else:
        lines.append("• Pas encore assez de décisions directionnelles évaluées cette semaine")

    return "\n".join(lines)


def build_weekly_briefing() -> str:
    calendar_section = build_calendar_section()
    performance_section = build_performance_section()

    return (
        "📅 BILAN HEBDOMADAIRE — OR (XAU/USD)\n\n"
        f"{performance_section}\n\n"
        f"{calendar_section}\n\n"
        "Le système passera automatiquement en NEUTRE dans les 2h précédant chaque événement macro majeur."
    )


if __name__ == "__main__":
    message = build_weekly_briefing()
    telegram_bot.send_message(message)
    print(f"[{datetime.now(timezone.utc)}] Briefing hebdomadaire envoyé.")
