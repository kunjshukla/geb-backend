"""
Authentication routes — Login, Logout, Token validation, Change password
"""

import jwt
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from werkzeug.security import check_password_hash, generate_password_hash
from pydantic import BaseModel

from backend import config
from backend.store import users, log_activity

router = APIRouter()
security = HTTPBearer(auto_error=False)


# ── Pydantic Models ─────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ── Token helpers ────────────────────────────────────────────

def generate_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=config.JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm="HS256")


def _decode_token(token: str) -> dict:
    try:
        data = jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
        return {"user_id": data["user_id"], "username": data["username"], "role": data["role"]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ── Dependencies ─────────────────────────────────────────────

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    token = None
    if credentials:
        token = credentials.credentials
    if not token:
        token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication token required")
    return _decode_token(token)


async def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ── Routes ───────────────────────────────────────────────────

@router.post("/login")
async def login(body: LoginRequest, request: Request):
    username = body.username.strip()
    password = body.password

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")

    user = next((u for u in users if u["username"] == username and u["is_active"]), None)
    if not user or not check_password_hash(user["password_hash"], password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Update last login
    user["last_login"] = datetime.utcnow().isoformat()

    token = generate_token(user["id"], user["username"], user["role"])

    log_activity(user["id"], user["username"], "LOGIN",
                 f"Login from {request.client.host}", request.client.host)

    return {
        "success": True,
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
        },
    }


@router.post("/logout")
async def logout(request: Request, current_user: dict = Depends(get_current_user)):
    log_activity(current_user["user_id"], current_user["username"],
                 "LOGOUT", None, request.client.host)
    return {"success": True, "message": "Logged out successfully"}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    user = next((u for u in users if u["id"] == current_user["user_id"]), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user": {
            k: user[k] for k in
            ("id", "name", "username", "email", "role", "created_at", "last_login")
        }
    }


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, request: Request,
                          current_user: dict = Depends(get_current_user)):
    if not body.current_password or not body.new_password:
        raise HTTPException(status_code=400, detail="Both current and new password required")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    user = next((u for u in users if u["id"] == current_user["user_id"]), None)
    if not user or not check_password_hash(user["password_hash"], body.current_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user["password_hash"] = generate_password_hash(body.new_password)

    log_activity(current_user["user_id"], current_user["username"],
                 "PASSWORD_CHANGE", None, request.client.host)
    return {"success": True, "message": "Password changed successfully"}
