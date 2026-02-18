"""
Analytics routes — Dashboard metrics and charts data
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query

from backend.routes.auth import get_current_user
from backend.store import (
    message_logs, templates, campaigns, users, activity_logs,
)

router = APIRouter()


@router.get("/overview")
async def get_overview(current_user: dict = Depends(get_current_user)):
    total_sent = sum(1 for m in message_logs if m["status"] == "sent")
    total_delivered = sum(1 for m in message_logs if m["status"] == "delivered")
    total_read = sum(1 for m in message_logs if m["status"] == "read")
    total_failed = sum(1 for m in message_logs if m["status"] == "failed")
    total_all = len(message_logs)
    total_templates = sum(1 for t in templates if t["status"] == "approved")
    total_campaigns = len(campaigns)
    active_users = sum(1 for u in users if u["is_active"])

    # Last 7 days daily message volume
    daily_data = []
    for i in range(6, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        count = sum(1 for m in message_logs if m["sent_at"].startswith(day))
        failed = sum(1 for m in message_logs
                     if m["sent_at"].startswith(day) and m["status"] == "failed")
        daily_data.append({"date": day, "sent": count, "failed": failed})

    # Recent messages
    recent = sorted(message_logs, key=lambda m: m["sent_at"], reverse=True)[:10]

    # Recent campaigns
    recent_campaigns = sorted(campaigns, key=lambda c: c["created_at"], reverse=True)[:5]

    delivery_rate = round((total_delivered / total_sent * 100), 1) if total_sent > 0 else 0
    read_rate = round((total_read / total_sent * 100), 1) if total_sent > 0 else 0

    return {
        "stats": {
            "total_sent": total_sent,
            "total_delivered": total_delivered,
            "total_read": total_read,
            "total_failed": total_failed,
            "total_messages": total_all,
            "delivery_rate": delivery_rate,
            "read_rate": read_rate,
            "total_templates": total_templates,
            "total_campaigns": total_campaigns,
            "active_users": active_users,
        },
        "daily_chart": daily_data,
        "recent_messages": recent,
        "recent_campaigns": recent_campaigns,
    }


@router.get("/activity-logs")
async def get_activity_logs(
    page: int = Query(1),
    limit: int = Query(50),
    current_user: dict = Depends(get_current_user),
):
    total = len(activity_logs)
    sorted_logs = sorted(activity_logs, key=lambda l: l["timestamp"], reverse=True)
    offset = (page - 1) * limit
    page_logs = sorted_logs[offset:offset + limit]
    return {"logs": page_logs, "total": total, "page": page}
