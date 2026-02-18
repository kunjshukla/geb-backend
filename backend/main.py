"""
GEB WhatsApp Automation Dashboard — FastAPI Application
Code O Logic | Strategic Communication Infrastructure
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import config
from backend.routes import auth, messages, templates, analytics, users, webhooks

app = FastAPI(
    title="GEB WhatsApp Dashboard API",
    description="WhatsApp Automation Platform by Code O Logic",
    version="1.0.0",
)

# ── CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        config.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ────────────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(messages.router, prefix="/api/messages", tags=["Messages"])
app.include_router(templates.router, prefix="/api/templates", tags=["Templates"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(webhooks.router, prefix="/api/webhook", tags=["Webhooks"])


# ── Health-check ─────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "service": "GEB WhatsApp Dashboard API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
