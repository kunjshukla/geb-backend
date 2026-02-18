"""
WhatsApp Webhook handler — receives delivery status updates from Meta
"""

from datetime import datetime
from fastapi import APIRouter, Request, Query
from fastapi.responses import PlainTextResponse

from backend import config
from backend.store import message_logs

router = APIRouter()


@router.get("/")
async def verify_webhook(
    request: Request,
    hub_mode: str = Query("", alias="hub.mode"),
    hub_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
):
    """Meta webhook verification handshake."""
    if hub_mode == "subscribe" and hub_token == config.WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge, status_code=200)
    return {"error": "Verification failed"}


@router.post("/")
async def receive_webhook(request: Request):
    """Receive and process WhatsApp status updates."""
    try:
        data = await request.json()
    except Exception:
        return {"status": "ok"}

    if not data:
        return {"status": "ok"}

    try:
        entries = data.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                statuses = value.get("statuses", [])
                for status_update in statuses:
                    msg_id = status_update.get("id")
                    status = status_update.get("status")

                    if msg_id and status:
                        ts = datetime.utcnow().isoformat()
                        log = next((l for l in message_logs
                                    if l.get("message_id") == msg_id), None)
                        if log:
                            log["status"] = status
                            if status == "delivered":
                                log["delivered_at"] = ts
                            elif status == "read":
                                log["read_at"] = ts
                            elif status == "failed":
                                errors = status_update.get("errors", [{}])
                                err_msg = (errors[0].get("title", "Unknown error")
                                           if errors else "Failed")
                                log["error_message"] = err_msg
    except Exception as e:
        print(f"[Webhook] Error processing: {e}")

    return {"status": "ok"}
