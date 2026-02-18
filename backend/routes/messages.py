"""
Message routes — Send individual and bulk messages via WhatsApp
"""

import csv
import io
import json
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File, Form, Query
from pydantic import BaseModel

from backend.routes.auth import get_current_user
from backend.store import templates, message_logs, campaigns, log_activity
from backend.store import _auto_id
from backend import whatsapp_service as wa

router = APIRouter()


class SendMessageRequest(BaseModel):
    phone: str
    name: str = ""
    type: str = "template"
    template_id: int | None = None
    variables: list = []
    text: str = ""


@router.post("/send")
async def send_single_message(body: SendMessageRequest, request: Request,
                               current_user: dict = Depends(get_current_user)):
    phone = body.phone.strip()
    name = body.name.strip()
    message_type = body.type
    template_id = body.template_id
    variables = body.variables
    text_body = body.text

    if not phone:
        raise HTTPException(status_code=400, detail="Phone number required")

    if not wa.validate_phone(phone):
        raise HTTPException(status_code=400, detail=f"Invalid phone number: {phone}")

    result = None
    template_name = None
    body_preview = text_body[:100] if text_body else ""

    if message_type == "template" and template_id:
        tmpl = next((t for t in templates if t["id"] == template_id), None)
        if not tmpl:
            raise HTTPException(status_code=404, detail="Template not found")
        template_name = tmpl["name"]
        body_preview = tmpl["body"][:100]
        result = wa.send_template_with_variables(
            phone, template_name, variables, tmpl["language"],
            tmpl.get("button_url")
        )
    elif message_type == "text" and text_body:
        result = wa.send_text_message(phone, text_body)
    else:
        raise HTTPException(status_code=400, detail="Provide template_id or text body")

    status = "sent" if result.get("success") else "failed"
    now = datetime.utcnow().isoformat()

    message_logs.append({
        "id": _auto_id("message_logs"),
        "message_id": result.get("message_id"),
        "recipient_phone": phone,
        "recipient_name": name or None,
        "message_type": message_type,
        "template_id": template_id,
        "template_name": template_name,
        "body_preview": body_preview,
        "status": status,
        "error_message": result.get("error"),
        "sent_by": current_user["user_id"],
        "sent_at": now,
        "delivered_at": None,
        "read_at": None,
    })

    log_activity(current_user["user_id"], current_user["username"],
                 "SEND_MESSAGE", f"To: {phone} | Status: {status}", request.client.host)

    return {
        "success": result.get("success"),
        "message_id": result.get("message_id"),
        "status": status,
        "simulated": result.get("simulated", False),
        "note": result.get("note", ""),
    }


@router.post("/bulk")
async def send_bulk_message(
    request: Request,
    current_user: dict = Depends(get_current_user),
    campaign_name: str = Form("Bulk Campaign"),
    template_id: str = Form(""),
    recipients: str = Form("[]"),
    csv_file: UploadFile | None = File(None),
):
    """Send bulk WhatsApp messages from CSV data or manual recipients."""
    tid = int(template_id) if template_id else None

    try:
        recs = json.loads(recipients) if isinstance(recipients, str) else recipients
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid recipients format")

    # Handle CSV file upload
    if csv_file and csv_file.filename:
        content = (await csv_file.read()).decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(content))
        recs = []
        for row in reader:
            phone = (row.get("phone") or row.get("Phone") or row.get("PHONE") or "").strip()
            r_name = (row.get("name") or row.get("Name") or row.get("NAME") or "").strip()
            var1 = (row.get("var1") or row.get("variable1") or "").strip()
            var2 = (row.get("var2") or row.get("variable2") or "").strip()
            var3 = (row.get("var3") or row.get("variable3") or "").strip()
            if phone:
                recs.append({"phone": phone, "name": r_name,
                             "variables": [v for v in [var1, var2, var3] if v]})

    if not recs:
        raise HTTPException(status_code=400, detail="No valid recipients found")
    if not tid:
        raise HTTPException(status_code=400, detail="Template ID required for bulk messaging")

    tmpl = next((t for t in templates if t["id"] == tid), None)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    now = datetime.utcnow().isoformat()
    campaign_id = _auto_id("campaigns")
    campaign = {
        "id": campaign_id,
        "name": campaign_name,
        "template_id": tid,
        "template_name": tmpl["name"],
        "total_recipients": len(recs),
        "sent_count": 0,
        "delivered_count": 0,
        "read_count": 0,
        "failed_count": 0,
        "status": "running",
        "created_by": current_user["user_id"],
        "created_at": now,
        "completed_at": None,
    }
    campaigns.append(campaign)

    sent_count = failed_count = 0
    results = []

    for rec in recs:
        r_phone = rec.get("phone", "").strip()
        r_name = rec.get("name", "")
        r_vars = rec.get("variables", [])

        if not r_phone or not wa.validate_phone(r_phone):
            failed_count += 1
            results.append({"phone": r_phone, "status": "failed", "error": "Invalid phone"})
            continue

        result = wa.send_template_with_variables(r_phone, tmpl["name"], r_vars, tmpl["language"])
        status = "sent" if result.get("success") else "failed"

        if result.get("success"):
            sent_count += 1
        else:
            failed_count += 1

        message_logs.append({
            "id": _auto_id("message_logs"),
            "message_id": result.get("message_id"),
            "recipient_phone": r_phone,
            "recipient_name": r_name,
            "message_type": "bulk",
            "template_id": tid,
            "template_name": tmpl["name"],
            "body_preview": tmpl["body"][:100],
            "status": status,
            "error_message": result.get("error"),
            "sent_by": current_user["user_id"],
            "sent_at": datetime.utcnow().isoformat(),
            "delivered_at": None,
            "read_at": None,
        })
        results.append({"phone": r_phone, "name": r_name, "status": status,
                        "message_id": result.get("message_id")})

    # Update campaign stats
    campaign["sent_count"] = sent_count
    campaign["failed_count"] = failed_count
    campaign["status"] = "completed"
    campaign["completed_at"] = datetime.utcnow().isoformat()

    log_activity(current_user["user_id"], current_user["username"], "BULK_SEND",
                 f"Campaign: {campaign_name} | Sent: {sent_count} | Failed: {failed_count}",
                 request.client.host)

    return {
        "success": True,
        "campaign_id": campaign_id,
        "total": len(recs),
        "sent": sent_count,
        "failed": failed_count,
        "results": results,
    }


@router.get("/logs")
async def get_logs(
    page: int = Query(1),
    limit: int = Query(50),
    status: str = Query(""),
    phone: str = Query(""),
    current_user: dict = Depends(get_current_user),
):
    filtered = message_logs[:]
    if status:
        filtered = [l for l in filtered if l["status"] == status]
    if phone:
        filtered = [l for l in filtered if phone in l["recipient_phone"]]

    total = len(filtered)
    filtered.sort(key=lambda l: l["sent_at"], reverse=True)
    offset = (page - 1) * limit
    page_logs = filtered[offset:offset + limit]

    return {
        "logs": page_logs,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit if total > 0 else 1,
    }


@router.get("/campaigns")
async def get_campaigns(current_user: dict = Depends(get_current_user)):
    sorted_campaigns = sorted(campaigns, key=lambda c: c["created_at"], reverse=True)
    return {"campaigns": sorted_campaigns}


@router.get("/campaigns/{campaign_id}")
async def get_campaign_detail(campaign_id: int,
                               current_user: dict = Depends(get_current_user)):
    campaign = next((c for c in campaigns if c["id"] == campaign_id), None)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    logs = [l for l in message_logs if l.get("template_name") == campaign["template_name"]]
    logs.sort(key=lambda l: l["sent_at"], reverse=True)
    return {"campaign": campaign, "logs": logs[:100]}
