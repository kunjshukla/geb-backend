"""
Template management routes
"""

from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from pydantic import BaseModel

from backend.routes.auth import get_current_user, get_admin_user
from backend.store import templates, log_activity
from backend.store import _auto_id

router = APIRouter()


class CreateTemplateRequest(BaseModel):
    name: str
    category: str = "UTILITY"
    language: str = "en"
    body: str
    header: str = ""
    footer: str = ""
    button_text: str = ""
    button_url: str = ""


class UpdateTemplateRequest(BaseModel):
    body: str | None = None
    header: str | None = None
    footer: str | None = None
    button_text: str | None = None
    button_url: str | None = None
    status: str | None = None


@router.get("/")
async def get_templates(
    category: str = Query("", alias="category"),
    status: str = Query("", alias="status"),
    current_user: dict = Depends(get_current_user),
):
    filtered = templates[:]
    if category:
        filtered = [t for t in filtered if t["category"] == category]
    if status:
        filtered = [t for t in filtered if t["status"] == status]
    # Sort newest first
    filtered.sort(key=lambda t: t["created_at"], reverse=True)
    return {"templates": filtered}


@router.get("/{template_id}")
async def get_template(template_id: int, current_user: dict = Depends(get_current_user)):
    tmpl = next((t for t in templates if t["id"] == template_id), None)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"template": tmpl}


@router.post("/")
async def create_template(body: CreateTemplateRequest, request: Request,
                          current_user: dict = Depends(get_current_user)):
    name = body.name.strip().lower().replace(" ", "_")
    category = body.category.upper()
    language = body.language
    tmpl_body = body.body.strip()
    header = body.header.strip() or None
    footer = body.footer.strip() or None
    button_text = body.button_text.strip() or None
    button_url = body.button_url.strip() or None

    if not name or not tmpl_body:
        raise HTTPException(status_code=400, detail="Template name and body are required")
    if category not in ("UTILITY", "MARKETING", "AUTHENTICATION"):
        raise HTTPException(status_code=400,
                            detail="Category must be UTILITY, MARKETING, or AUTHENTICATION")

    if any(t["name"] == name for t in templates):
        raise HTTPException(status_code=409,
                            detail=f'Template with name "{name}" already exists')

    now = datetime.utcnow().isoformat()
    tmpl_id = _auto_id("templates")
    templates.append({
        "id": tmpl_id, "name": name, "category": category,
        "language": language, "body": tmpl_body,
        "header": header, "footer": footer,
        "button_text": button_text, "button_url": button_url,
        "status": "pending",
        "created_by": current_user["user_id"],
        "created_at": now,
    })

    log_activity(current_user["user_id"], current_user["username"],
                 "CREATE_TEMPLATE", f"Template: {name}", request.client.host)

    return {"success": True, "template_id": tmpl_id,
            "message": "Template created (pending approval)"}


@router.put("/{template_id}")
async def update_template(template_id: int, body: UpdateTemplateRequest, request: Request,
                          current_user: dict = Depends(get_current_user)):
    tmpl = next((t for t in templates if t["id"] == template_id), None)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    if body.body is not None:
        tmpl["body"] = body.body
    if body.header is not None:
        tmpl["header"] = body.header or None
    if body.footer is not None:
        tmpl["footer"] = body.footer or None
    if body.button_text is not None:
        tmpl["button_text"] = body.button_text or None
    if body.button_url is not None:
        tmpl["button_url"] = body.button_url or None
    if body.status is not None:
        tmpl["status"] = body.status

    log_activity(current_user["user_id"], current_user["username"],
                 "UPDATE_TEMPLATE", f"Template ID: {template_id}", request.client.host)
    return {"success": True, "message": "Template updated"}


@router.delete("/{template_id}")
async def delete_template(template_id: int, request: Request,
                          current_user: dict = Depends(get_admin_user)):
    tmpl = next((t for t in templates if t["id"] == template_id), None)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    templates.remove(tmpl)

    log_activity(current_user["user_id"], current_user["username"],
                 "DELETE_TEMPLATE", f"Template: {tmpl['name']}", request.client.host)
    return {"success": True, "message": "Template deleted"}


@router.post("/{template_id}/approve")
async def approve_template(template_id: int, request: Request,
                           current_user: dict = Depends(get_admin_user)):
    tmpl = next((t for t in templates if t["id"] == template_id), None)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    tmpl["status"] = "approved"

    log_activity(current_user["user_id"], current_user["username"],
                 "APPROVE_TEMPLATE", f"Template ID: {template_id}", request.client.host)
    return {"success": True, "message": "Template approved"}
