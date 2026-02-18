"""
User management routes (admin only for most operations)
"""

from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from werkzeug.security import generate_password_hash
from pydantic import BaseModel

from backend.routes.auth import get_current_user, get_admin_user
from backend.store import users, log_activity
from backend.store import _auto_id

router = APIRouter()

MAX_USERS = 6


class CreateUserRequest(BaseModel):
    name: str
    email: str
    username: str
    password: str
    role: str = "operator"


class UpdateUserRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    role: str | None = None
    is_active: bool | None = None


@router.get("/")
async def get_users(current_user: dict = Depends(get_current_user)):
    safe = []
    for u in sorted(users, key=lambda x: x["created_at"]):
        safe.append({k: u[k] for k in
                     ("id", "name", "username", "email", "role",
                      "is_active", "created_at", "last_login")})
    return {"users": safe}


@router.post("/")
async def create_user(body: CreateUserRequest, request: Request,
                      current_user: dict = Depends(get_admin_user)):
    name = body.name.strip()
    email = body.email.strip().lower()
    username = body.username.strip().lower()
    password = body.password
    role = body.role

    if not all([name, email, username, password]):
        raise HTTPException(status_code=400,
                            detail="Name, email, username, and password are required")
    if len(password) < 6:
        raise HTTPException(status_code=400,
                            detail="Password must be at least 6 characters")
    if role not in ("admin", "operator", "viewer"):
        raise HTTPException(status_code=400,
                            detail="Role must be admin, operator, or viewer")

    active_count = sum(1 for u in users if u["is_active"])
    if active_count >= MAX_USERS:
        raise HTTPException(status_code=400,
                            detail=f"Maximum {MAX_USERS} users allowed per the license")

    if any(u["username"] == username for u in users):
        raise HTTPException(status_code=409, detail="Username already exists")
    if any(u["email"] == email for u in users):
        raise HTTPException(status_code=409, detail="Email already exists")

    now = datetime.utcnow().isoformat()
    user_id = _auto_id("users")
    users.append({
        "id": user_id,
        "name": name, "email": email, "username": username,
        "password_hash": generate_password_hash(password),
        "role": role, "is_active": 1,
        "created_at": now, "last_login": None,
    })

    log_activity(current_user["user_id"], current_user["username"],
                 "CREATE_USER", f"Created user: {username} ({role})", request.client.host)

    return {"success": True, "user_id": user_id, "message": "User created successfully"}


@router.put("/{user_id}")
async def update_user(user_id: int, body: UpdateUserRequest, request: Request,
                      current_user: dict = Depends(get_admin_user)):
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.name is not None:
        user["name"] = body.name
    if body.email is not None:
        user["email"] = body.email
    if body.role is not None:
        user["role"] = body.role
    if body.is_active is not None:
        user["is_active"] = int(body.is_active)

    log_activity(current_user["user_id"], current_user["username"],
                 "UPDATE_USER", f"Updated user ID: {user_id}", request.client.host)
    return {"success": True, "message": "User updated"}


@router.delete("/{user_id}")
async def delete_user(user_id: int, request: Request,
                      current_user: dict = Depends(get_admin_user)):
    if user_id == current_user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user["is_active"] = 0

    log_activity(current_user["user_id"], current_user["username"],
                 "DEACTIVATE_USER", f"Deactivated user ID: {user_id}", request.client.host)
    return {"success": True, "message": "User deactivated"}
