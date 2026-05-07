from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import httpx
import json
import os
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

from database import get_settings, save_setting
from google_photos import GooglePhotosService

BOT_API_URL = os.getenv("BOT_API_URL", "http://localhost:3001")

router = APIRouter(tags=["settings"])


class SettingsUpdate(BaseModel):
    watch_groups: str | None = None
    forward_to_id: str | None = None
    forward_to_name: str | None = None
    confidence_threshold: str | None = None
    save_photos_enabled: str | None = None
    save_photos_path: str | None = None
    save_photos_organize_by: str | None = None
    google_photos_enabled: str | None = None
    google_photos_client_id: str | None = None
    google_photos_client_secret: str | None = None
    google_photos_album_organize_by: str | None = None
    google_photos_album_name: str | None = None
    digest_mode: str | None = None
    digest_time: str | None = None
    thumbnails_enabled: str | None = None
    thumbnail_retention_hours: str | None = None
    pin_enabled: str | None = None
    app_pin: str | None = None
    language: str | None = None
    schedule_enabled: str | None = None
    schedule_from: str | None = None
    schedule_to: str | None = None
    scan_all_groups: str | None = None


async def _bot_get(path: str, params: dict | None = None, timeout: float = 5.0):
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{BOT_API_URL}{path}", params=params or {})
            return r.json()
    except Exception:
        return None


@router.get("")
async def get_all_settings():
    s = get_settings()
    s.pop("app_pin", None)  # never expose the PIN to the frontend
    return s


@router.post("")
async def update_settings(data: SettingsUpdate):
    for key, value in data.model_dump().items():
        if value is not None:
            save_setting(key, str(value))
    return {"success": True}


@router.get("/browse-folder")
async def browse_folder():
    """Open a native folder picker dialog and return the chosen path."""
    import asyncio

    def _pick():
        if sys.platform == "darwin":
            script = (
                'tell application "System Events"\n'
                '  activate\n'
                '  set f to choose folder with prompt "Choose folder to save matched photos"\n'
                '  return POSIX path of f\n'
                'end tell'
            )
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            return result.stdout.strip().rstrip("/") if result.returncode == 0 else ""
        elif sys.platform == "win32":
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.wm_attributes('-topmost', True)
                folder = filedialog.askdirectory(title="Choose folder to save matched photos")
                root.destroy()
                return folder or ""
            except Exception:
                return ""
        return ""

    path = await asyncio.get_running_loop().run_in_executor(None, _pick)
    return {"path": path} if path else {"path": "", "error": "No folder selected or picker unavailable"}


@router.get("/whatsapp/status")
async def whatsapp_status():
    data = await _bot_get("/status")
    return data or {"connected": False, "error": "Bot not reachable"}


@router.get("/whatsapp/qr")
async def whatsapp_qr():
    data = await _bot_get("/qr")
    return data or {"qr": None, "error": "Bot not reachable"}


@router.get("/whatsapp/groups")
async def whatsapp_groups(refresh: bool = False):
    data = await _bot_get("/groups", params={"refresh": "1"} if refresh else None, timeout=30.0)
    return data or {"groups": [], "error": "Bot not reachable"}


@router.get("/whatsapp/chats")
async def whatsapp_chats(refresh: bool = False):
    data = await _bot_get("/chats", params={"refresh": "1"} if refresh else None, timeout=30.0)
    return data or {"chats": [], "error": "Bot not reachable"}


def _gp_redirect_uri(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/settings/google-photos/callback"


def _gp_service(request: Request) -> GooglePhotosService | None:
    settings = get_settings()
    client_id = settings.get("google_photos_client_id", "").strip()
    client_secret = settings.get("google_photos_client_secret", "").strip()
    if not client_id or not client_secret:
        return None
    return GooglePhotosService(client_id, client_secret, _gp_redirect_uri(request))


@router.get("/google-photos/auth-url")
async def google_photos_auth_url(request: Request):
    svc = _gp_service(request)
    if not svc:
        return {"error": "Save your Client ID and Client Secret first"}
    return {"url": svc.get_auth_url()}


@router.get("/google-photos/callback")
async def google_photos_callback(request: Request, code: str = "", error: str = ""):
    if error or not code:
        return RedirectResponse(url=f"/?gp_error={error or 'cancelled'}")
    svc = _gp_service(request)
    if not svc:
        return RedirectResponse(url="/?gp_error=missing_credentials")
    data = await svc.exchange_code(code)
    if "access_token" not in data:
        err_detail = data.get("error", "token_exchange_failed")
        return RedirectResponse(url=f"/?gp_error={err_detail}")
    save_setting("google_photos_tokens", json.dumps(svc.tokens))
    return RedirectResponse(url="/?gp_connected=1")


@router.get("/google-photos/status")
async def google_photos_status():
    settings = get_settings()
    tokens_json = settings.get("google_photos_tokens", "")
    if not tokens_json:
        return {"connected": False}
    try:
        tokens = json.loads(tokens_json)
        return {"connected": bool(tokens.get("access_token") and tokens.get("refresh_token"))}
    except Exception:
        return {"connected": False}


@router.post("/google-photos/disconnect")
async def google_photos_disconnect():
    save_setting("google_photos_tokens", "")
    return {"ok": True}
