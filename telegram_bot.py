"""
Envoi de la décision formatée vers Telegram.
"""
import requests
from datetime import datetime
import config

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def format_message(decision: dict) -> str:
    emoji = {"LONG": "🟢", "SHORT": "🔴", "NEUTRE": "🟡"}.get(decision["direction"], "🟡")
    if decision.get("caution_imminent_event"):
        emoji = "⚠️" + emoji
    now = datetime.now().strftime("%H:%M")

    lines = [
        f"{emoji} OR (XAU/USD) — {now}",
        "",
        f"📊 DÉCISION : {decision['direction']} (confiance : {decision['confidence']*100:.0f}%)",
        "",
        "💡 RAISONS :",
    ]
    for reason in decision["reasons"]:
        lines.append(f"• {reason}")

    if decision["entry"] and decision["stop_loss"] and decision["take_profit"]:
        lines += [
            "",
            "⚠️ NIVEAUX SUGGÉRÉS :",
            f"Entrée : ~{decision['entry']:.2f}$ | "
            f"Stop-loss : {decision['stop_loss']:.2f}$ | "
            f"Take-profit : {decision['take_profit']:.2f}$",
        ]

    position_info = decision.get("position_info")
    if position_info:
        lines += [
            "",
            "💰 TAILLE DE POSITION SUGGÉRÉE :",
            f"{position_info['lot_size']} lot(s) — risque : {position_info['risk_amount_eur']}€ "
            f"(exposition ~{position_info['notional_value_usd']}$)",
        ]
        if position_info.get("warning"):
            lines.append(f"⚠️ {position_info['warning']}")

    if decision["warnings"]:
        lines += ["", "🔶 POINTS DE PRUDENCE :"]
        for warning in decision["warnings"]:
            lines.append(f"• {warning}")

    lines += ["", "_Outil d'aide à la décision, pas un conseil financier. À toi de valider._"]

    return "\n".join(lines)


def send_message(text: str) -> None:
    url = TELEGRAM_API_URL.format(token=config.TELEGRAM_BOT_TOKEN)
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    response = requests.post(url, data=payload, timeout=15)
    if response.status_code != 200:
        raise RuntimeError(f"Erreur envoi Telegram: {response.text}")


def notify_decision(decision: dict) -> None:
    message = format_message(decision)
    send_message(message)
