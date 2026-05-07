import asyncio
import uuid
import httpx
import base64
from datetime import datetime, date
from pathlib import Path
from fastapi import APIRouter, UploadFile
import aiofiles

from database import (DIGEST_DIR, enqueue_digest, get_digest_queue,
                      clear_digest_queue, get_settings, save_setting)

import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

BOT_API_URL = os.getenv("BOT_API_URL", "http://localhost:3001")

router = APIRouter(tags=["digest"])

_scheduler_task: asyncio.Task | None = None


@router.post("/enqueue")
async def enqueue(file: UploadFile,
                  sender: str = "", group_name: str = "", kid_names: str = "",
                  is_video: bool = False):
    suffix = ".mp4" if is_video else ".jpg"
    media_path = DIGEST_DIR / f"{uuid.uuid4()}{suffix}"
    async with aiofiles.open(media_path, "wb") as f:
        await f.write(await file.read())
    enqueue_digest(sender=sender, group_name=group_name, kid_names=kid_names,
                   is_video=is_video, media_path=str(media_path))
    return {"ok": True}


@router.get("/queue")
async def queue_status():
    items = get_digest_queue()
    return {"count": len(items), "items": items}


@router.post("/send-now")
async def send_now():
    sent, errors = await _send_digest()
    return {"sent": sent, "errors": errors}


async def _send_digest() -> tuple[int, int]:
    settings = get_settings()
    forward_to = settings.get("forward_to_id", "")
    if not forward_to:
        return 0, 0

    items = get_digest_queue()
    if not items:
        return 0, 0

    lang = settings.get("language", "en")
    sent = errors = 0
    async with httpx.AsyncClient(timeout=60) as client:
        count = len(items)
        if lang == "he":
            header = f"📸 תקציר יומי — {count} {'התאמות' if count != 1 else 'התאמה'}"
        else:
            header = f"📸 Daily digest — {count} match{'es' if count != 1 else ''}"
        try:
            await client.post(f"{BOT_API_URL}/send-text", json={"to": forward_to, "text": header})
        except Exception as e:
            print(f"[digest] Failed to send header: {e}", flush=True)

        for item in items:
            path = Path(item["media_path"])
            if not path.exists():
                errors += 1
                continue
            try:
                media_b64 = base64.b64encode(path.read_bytes()).decode()
                kids = item["kid_names"] or "Unknown"
                caption = f"🧒 {kids} · {item['group_name']} · {item['sender']}"
                if item["is_video"]:
                    await client.post(f"{BOT_API_URL}/send-video",
                                      json={"to": forward_to, "video_b64": media_b64, "caption": caption})
                else:
                    await client.post(f"{BOT_API_URL}/send",
                                      json={"to": forward_to, "image_b64": media_b64, "caption": caption})
                sent += 1
            except Exception:
                errors += 1

    clear_digest_queue()
    save_setting("digest_last_sent", date.today().isoformat())
    return sent, errors


async def _scheduler_loop():
    while True:
        await asyncio.sleep(60)
        try:
            settings = get_settings()
            if settings.get("digest_mode") != "true":
                continue
            digest_time = settings.get("digest_time", "20:00")
            now = datetime.now()
            h, m = map(int, digest_time.split(":"))
            if now.hour != h or now.minute != m:
                continue
            last_sent = settings.get("digest_last_sent", "")
            if last_sent == date.today().isoformat():
                continue
            await _send_digest()
        except Exception as e:
            print(f"[digest] Scheduler error: {e}", flush=True)


def start_scheduler():
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
