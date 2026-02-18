"""
WhatsApp Cloud API Service Layer
Handles all communication with Meta's WhatsApp Business API
"""

import httpx
import random
import string
from backend import config


BASE_URL = "https://graph.facebook.com"


def _api_url() -> str:
    return f"{BASE_URL}/{config.META_API_VERSION}/{config.WHATSAPP_PHONE_ID}/messages"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {config.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }


def _simulate_response() -> dict:
    fake_id = "wamid." + "".join(random.choices(string.ascii_letters + string.digits, k=32))
    return {
        "success": True,
        "message_id": fake_id,
        "simulated": True,
        "note": "Running in demo mode — configure WHATSAPP_PHONE_ID and WHATSAPP_TOKEN for live sending",
    }


def _post(payload: dict) -> dict:
    if not config.WHATSAPP_PHONE_ID or not config.WHATSAPP_TOKEN:
        return _simulate_response()

    try:
        resp = httpx.post(_api_url(), headers=_headers(), json=payload, timeout=15)
        result = resp.json()
        if resp.status_code == 200:
            msg_id = result.get("messages", [{}])[0].get("id", "unknown")
            return {"success": True, "message_id": msg_id, "raw": result}
        else:
            error = result.get("error", {}).get("message", "Unknown error")
            return {"success": False, "error": error, "raw": result}
    except httpx.TimeoutException:
        return {"success": False, "error": "Request timed out"}
    except httpx.ConnectError:
        return {"success": False, "error": "Connection error — check network"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _normalize_phone(phone: str) -> str:
    cleaned = phone.strip().replace(" ", "").replace("-", "").replace("+", "")
    if not cleaned.startswith("91") and len(cleaned) == 10:
        cleaned = "91" + cleaned
    return cleaned


def validate_phone(phone: str) -> bool:
    cleaned = phone.strip().replace(" ", "").replace("-", "").replace("+", "")
    return cleaned.isdigit() and 7 <= len(cleaned) <= 15


def send_text_message(to_phone: str, text: str) -> dict:
    phone = _normalize_phone(to_phone)
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text, "preview_url": False},
    }
    return _post(payload)


def send_template_message(to_phone: str, template_name: str,
                          language_code: str = "en",
                          components: list | None = None) -> dict:
    phone = _normalize_phone(to_phone)
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }
    if components:
        payload["template"]["components"] = components
    return _post(payload)


def send_template_with_variables(to_phone: str, template_name: str,
                                 variables: list,
                                 language_code: str = "en",
                                 button_url: str | None = None) -> dict:
    phone = _normalize_phone(to_phone)
    components: list[dict] = []

    if variables:
        body_params = [{"type": "text", "text": str(v)} for v in variables]
        components.append({"type": "body", "parameters": body_params})

    if button_url:
        components.append({
            "type": "button",
            "sub_type": "url",
            "index": "0",
            "parameters": [{"type": "text", "text": button_url}],
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            "components": components if components else [],
        },
    }
    return _post(payload)
