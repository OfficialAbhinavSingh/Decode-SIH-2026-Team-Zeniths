"""Crew Alert Dispatch Service.

Monitors fusion priority scores and dispatches actionable leak repair cards
to field repair crew leads via Telegram Bot, WhatsApp, or Webhooks.
"""

import json
import logging
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ALERT_WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL", "")


@dataclass
class AlertDispatchResult:
    zone_id: str
    fusion_score: float
    rank: int
    sent: bool
    channel: str
    message: str


def format_crew_alert_card(zone_score: dict[str, Any]) -> str:
    """Format a plain-language actionable dispatch note for repair crews."""
    zone_id = zone_score.get("zone_id", "Unknown")
    name = zone_score.get("name", "Zone")
    rank = zone_score.get("rank", 1)
    fusion_score = zone_score.get("fusion_score", 0.0)
    confidence = str(zone_score.get("confidence", "medium")).upper()
    signals_used = zone_score.get("signals_used", 0)
    explanation = zone_score.get("explanation", "Multiple signals indicate potential subsurface leak.")

    sat_score = zone_score.get("satellite_score")
    bill_score = zone_score.get("billing_score")
    cit_score = zone_score.get("citizen_score")

    sat_str = f"{sat_score:.1f}/100" if sat_score is not None else "N/A"
    bill_str = f"{bill_score:.1f}/100" if bill_score is not None else "N/A"
    cit_str = f"{cit_score:.1f}/100" if cit_score is not None else "N/A"

    urgency = "🔴 CRITICAL" if fusion_score >= 85 else "🟠 HIGH PRIORITY"

    lines = [
        f"{urgency}: WATER LEAK DISPATCH",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📍 Zone: {zone_id} ({name})",
        f"🏆 City Priority Rank: #{rank} | Score: {fusion_score:.1f}/100",
        f"🎯 Confidence: {confidence} ({signals_used}/3 signals agree)",
        f"",
        f"📊 Signal Breakdown:",
        f"  • 🛰️ Satellite Wetness Anomaly: {sat_str}",
        f"  • 💧 Non-Revenue Water Gap: {bill_str}",
        f"  • 📱 Citizen Incident Density: {cit_str}",
        f"",
        f"💡 Diagnostic Summary:",
        f"  \"{explanation}\"",
        f"",
        f"🛠️ Action Recommended: Deploy acoustic/ground team to pipeline corridor in {zone_id}.",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    return "\n".join(lines)


def send_telegram_alert(
    message: str,
    bot_token: str = TELEGRAM_BOT_TOKEN,
    chat_id: str = TELEGRAM_CHAT_ID,
) -> bool:
    """Send an alert message via Telegram Bot API."""
    if not bot_token or not chat_id:
        logger.info("[Telegram Alert] No token/chat_id configured. Simulation mode only.")
        return True

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        if httpx is not None:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(url, json=payload)
                return resp.status_code == 200
        else:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.status == 200
    except Exception as exc:
        logger.error(f"Failed to send Telegram alert: {exc}")
        return False


def dispatch_high_priority_alerts(
    scores: list[dict[str, Any]],
    min_score: float = 75.0,
    max_alerts: int = 3,
    bot_token: str = TELEGRAM_BOT_TOKEN,
    chat_id: str = TELEGRAM_CHAT_ID,
) -> list[AlertDispatchResult]:
    """Identify top priority zones and dispatch alerts to crew leads."""
    results: list[AlertDispatchResult] = []
    # Filter for urgent zones
    urgent_zones = [
        s for s in scores
        if float(s.get("fusion_score", 0)) >= min_score and s.get("confidence") in ("high", "medium")
    ]
    # Sort by rank
    urgent_zones.sort(key=lambda x: x.get("rank", 999))

    for zone_data in urgent_zones[:max_alerts]:
        message = format_crew_alert_card(zone_data)
        sent = send_telegram_alert(message, bot_token, chat_id)
        results.append(
            AlertDispatchResult(
                zone_id=zone_data.get("zone_id", ""),
                fusion_score=float(zone_data.get("fusion_score", 0)),
                rank=int(zone_data.get("rank", 1)),
                sent=sent,
                channel="telegram" if (bot_token and chat_id) else "console",
                message=message,
            )
        )
    return results
