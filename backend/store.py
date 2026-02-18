"""
In-memory data store — replaces SQLite database.
All data is ephemeral and resets on server restart.
"""

from datetime import datetime
from werkzeug.security import generate_password_hash
from backend import config


# ── Helper ──────────────────────────────────────────────────

_next_id: dict[str, int] = {}


def _auto_id(collection: str) -> int:
    _next_id.setdefault(collection, 1)
    val = _next_id[collection]
    _next_id[collection] += 1
    return val


# ── Users ───────────────────────────────────────────────────

users: list[dict] = []


def _seed_admin():
    if not any(u["username"] == config.ADMIN_USERNAME for u in users):
        users.append({
            "id": _auto_id("users"),
            "name": config.ADMIN_NAME,
            "email": config.ADMIN_EMAIL,
            "username": config.ADMIN_USERNAME,
            "password_hash": generate_password_hash(config.ADMIN_PASSWORD),
            "role": "admin",
            "is_active": 1,
            "created_at": datetime.utcnow().isoformat(),
            "last_login": None,
        })


# ── Templates ───────────────────────────────────────────────

templates: list[dict] = []


def _seed_templates():
    if templates:
        return
    now = datetime.utcnow().isoformat()
    samples = [
        {
            "name": "service_update", "category": "UTILITY", "language": "en",
            "body": "Important update regarding your service request {{1}}: {{2}}",
            "header": "GEB Service Update", "footer": "Thank you for choosing GEB",
            "button_text": None, "button_url": None, "status": "approved",
            "created_by": 1, "created_at": now,
        },
        {
            "name": "group_invite", "category": "UTILITY", "language": "en",
            "body": "Hi {{1}}, you are invited to join the GEB group. Click below to join.",
            "header": "GEB Group Invitation", "footer": None,
            "button_text": "Join Group", "button_url": "https://chat.whatsapp.com/example",
            "status": "approved", "created_by": 1, "created_at": now,
        },
        {
            "name": "payment_reminder", "category": "UTILITY", "language": "en",
            "body": "Dear {{1}}, your payment of ₹{{2}} is due on {{3}}. Please pay to avoid interruption.",
            "header": "Payment Reminder", "footer": "GEB Billing",
            "button_text": None, "button_url": None, "status": "approved",
            "created_by": 1, "created_at": now,
        },
        {
            "name": "welcome_message", "category": "MARKETING", "language": "en",
            "body": "Welcome to GEB, {{1}}! We are excited to have you on board. Your account is now active.",
            "header": "Welcome to GEB", "footer": None,
            "button_text": None, "button_url": None, "status": "approved",
            "created_by": 1, "created_at": now,
        },
    ]
    for s in samples:
        s["id"] = _auto_id("templates")
        templates.append(s)


# ── Message Logs ────────────────────────────────────────────

message_logs: list[dict] = []

# ── Campaigns ───────────────────────────────────────────────

campaigns: list[dict] = []

# ── Activity Logs ───────────────────────────────────────────

activity_logs: list[dict] = []


def log_activity(user_id: int, username: str, action: str,
                 details: str | None = None, ip_address: str | None = None):
    activity_logs.append({
        "id": _auto_id("activity_logs"),
        "user_id": user_id,
        "username": username,
        "action": action,
        "details": details,
        "ip_address": ip_address,
        "timestamp": datetime.utcnow().isoformat(),
    })


# ── Seed on import ──────────────────────────────────────────

_seed_admin()
_seed_templates()
