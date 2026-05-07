from fastapi import FastAPI, UploadFile, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timedelta
import asyncio
import ipaddress
import os
import re
import json
import uuid
import base64
import httpx
import aiofiles
import numpy as np
import cv2
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from database import init_db, get_settings, log_activity, save_setting, get_activity_by_id, mark_activity_manually_matched
from face_service import FaceService, warm_up_model, get_model_status
from google_photos import GooglePhotosService
from routers.enrollment import router as enrollment_router, load_kids
from routers.settings import router as settings_router
from routers.dashboard import router as dashboard_router
from routers.auth import router as auth_router, is_valid_session
from routers.backup import router as backup_router
from routers.digest import router as digest_router, start_scheduler

DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent.parent / "data"))).resolve()
THUMBNAILS_DIR = DATA_DIR / "thumbnails"
ORIGINALS_DIR = DATA_DIR / "originals"
BOT_API_URL = os.getenv("BOT_API_URL", "http://localhost:3001")
_GENERIC_FILENAMES = {"photo.jpg", "video.mp4", "image.jpg"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in " -_." else "_" for c in name).strip() or "unknown"


def _extract_first_frame(video_path: str) -> bytes | None:
    """Return JPEG bytes of the first readable frame of a video, or None."""
    try:
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return None
        _, buf = cv2.imencode(".jpg", frame)
        return buf.tobytes()
    except Exception:
        return None


def _save_thumbnail(img_bytes: bytes) -> str:
    """Resize img_bytes to a small JPEG, save to THUMBNAILS_DIR, return filename."""
    try:
        THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
        arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return ""
        h, w = img.shape[:2]
        max_dim = 320
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        fname = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19] + f"_{uuid.uuid4().hex[:6]}.jpg"
        cv2.imwrite(str(THUMBNAILS_DIR / fname), img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return fname
    except Exception:
        return ""


def _purge_dir(directory: Path, cutoff: datetime) -> None:
    if not directory.exists():
        return
    for f in directory.iterdir():
        try:
            if f.is_file() and datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
        except Exception:
            pass


def purge_old_thumbnails(retention_hours: int = 168):
    """Delete thumbnails and originals older than retention_hours."""
    cutoff = datetime.now() - timedelta(hours=retention_hours)
    _purge_dir(THUMBNAILS_DIR, cutoff)
    _purge_dir(ORIGINALS_DIR, cutoff)


def _save_original(data: bytes, row_id: int, ext: str = ".jpg") -> None:
    """Save the original media so it can be used later by the rerun-actions endpoint."""
    try:
        (ORIGINALS_DIR / f"{row_id}{ext}").write_bytes(data)
    except Exception:
        pass


def _resolve_group(group_id: str, db_settings: dict) -> tuple[list, dict, str]:
    """Return (kid_ids, kid_names, group_name) from watch_groups config."""
    kid_ids, kid_names, group_name = [], {}, group_id
    try:
        watch_groups = json.loads(db_settings.get("watch_groups", "[]"))
        for g in watch_groups:
            if g.get("id") == group_id:
                kid_ids = g.get("kid_ids", [])
                group_name = g.get("name", group_id)
                break
        all_kids = load_kids()
        kid_names = {k["id"]: k["name"] for k in all_kids}
        if not kid_ids and db_settings.get("scan_all_groups") == "true":
            kid_ids = [k["id"] for k in all_kids]
    except Exception:
        pass
    return kid_ids, kid_names, group_name


def _resolve_kids(kid_ids: str, group_id: str, group_name: str, db_settings: dict) -> tuple[list, dict, str]:
    """Return (kid_id_list, kid_names, resolved_name).

    If kid_ids is provided without a group_id, parses the comma-separated IDs directly.
    Otherwise resolves from the watch_groups config.
    """
    if kid_ids and not group_id:
        kid_id_list = [k.strip() for k in kid_ids.split(",") if k.strip()]
        kid_names = {k["id"]: k["name"] for k in load_kids()}
        return kid_id_list, kid_names, group_name or "manual scan"
    kid_id_list, kid_names, config_name = _resolve_group(group_id, db_settings)
    return kid_id_list, kid_names, group_name or config_name


def _enrich_matches(result: dict, kid_names: dict) -> tuple[list, float]:
    """Add kid_name to each match. Return (matched_kids, best_confidence)."""
    for m in result.get("matches", []):
        m["kid_name"] = kid_names.get(m["kid_id"], m["kid_id"])
    matched_kids = [m for m in result.get("matches", []) if m["matched"]]
    best_conf = max((m["confidence"] for m in result.get("matches", [])), default=0.0)
    return matched_kids, best_conf


def _build_caption(names: str, count: int, best_conf: float, is_video: bool, lang: str) -> str:
    conf = f"{best_conf * 100:.0f}%"
    if lang == "he":
        medium = "סרטון" if is_video else "תמונה"
        verb = "מופיעים" if count > 1 else "מופיע"
        return f"{names} {verb} ב{medium}! ({conf} ביטחון)"
    medium = "video" if is_video else "photo"
    verb = "are" if count > 1 else "is"
    return f"{names} {verb} in this {medium}! ({conf} confidence)"


async def _forward_media(forward_to: str, media_bytes: bytes, matched_kids: list,
                         best_conf: float, is_video: bool = False) -> tuple[bool, str | None]:
    """Send matched photo or video to the bot. Return (forwarded, error_msg)."""
    try:
        names = " & ".join(m["kid_name"] for m in matched_kids)
        lang = get_settings().get("language", "en")
        caption = _build_caption(names, len(matched_kids), best_conf, is_video, lang)
        endpoint = "send-video" if is_video else "send"
        payload_key = "video_b64" if is_video else "image_b64"
        timeout = 60.0 if is_video else 15.0
        async with httpx.AsyncClient(timeout=timeout) as hx:
            await hx.post(f"{BOT_API_URL}/{endpoint}", json={
                "to": forward_to,
                "caption": caption,
                payload_key: base64.b64encode(media_bytes).decode(),
            })
        return True, None
    except Exception as e:
        return False, str(e)


async def save_to_google_photos(media_bytes: bytes, group_name: str, matched_kids: list, settings: dict,
                               filename: str = "") -> bool:
    """Upload matched photo or video to Google Photos if configured."""
    if settings.get("google_photos_enabled") != "true":
        return False
    client_id = settings.get("google_photos_client_id", "").strip()
    client_secret = settings.get("google_photos_client_secret", "").strip()
    tokens_json = settings.get("google_photos_tokens", "")
    if not (client_id and client_secret and tokens_json):
        return False
    try:
        tokens = json.loads(tokens_json)
    except Exception:
        return False

    svc = GooglePhotosService(
        client_id, client_secret,
        redirect_uri=f"{os.getenv('BACKEND_PUBLIC_URL', 'http://localhost:8000')}/api/settings/google-photos/callback",
        tokens=tokens,
        on_tokens_updated=lambda t: save_setting("google_photos_tokens", json.dumps(t)),
    )
    upload_filename = filename or f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
    organize_by = settings.get("google_photos_album_organize_by", "none")
    if organize_by == "none":
        return await svc.upload_photo(media_bytes, filename=upload_filename)
    elif organize_by == "kid":
        results = await asyncio.gather(*[
            svc.upload_photo(media_bytes, album_name=m["kid_name"], filename=upload_filename)
            for m in matched_kids
        ])
        return all(results)
    else:
        album = settings.get("google_photos_album_name", "").strip() or group_name
        return await svc.upload_photo(media_bytes, album_name=album, filename=upload_filename)


def save_matched_photo(img_bytes: bytes, group_name: str, kid_names: list, settings: dict,
                       original_filename: str = "") -> str:
    """Save a matched photo to the configured local folder. Returns saved path or ''."""
    if settings.get("save_photos_enabled") != "true":
        return ""
    save_path = settings.get("save_photos_path", "").strip()
    if not save_path:
        return ""
    base = Path(save_path)
    if original_filename and original_filename.lower() not in _GENERIC_FILENAMES:
        filename = _safe_filename(original_filename)
    else:
        ext = Path(original_filename).suffix if original_filename else ".jpg"
        filename = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19] + (ext or ".jpg")
    try:
        if settings.get("save_photos_organize_by") == "kid":
            first_path = ""
            for name in kid_names:
                folder = base / _safe_filename(name)
                folder.mkdir(parents=True, exist_ok=True)
                dest = folder / filename
                dest.write_bytes(img_bytes)
                if not first_path:
                    first_path = str(dest)
            return first_path
        else:
            folder = base / _safe_filename(group_name)
            folder.mkdir(parents=True, exist_ok=True)
            dest = folder / filename
            dest.write_bytes(img_bytes)
            return str(dest)
    except Exception:
        return ""


# ── App setup ──────────────────────────────────────────────────────────────────

async def _thumbnail_cleanup_scheduler():
    """Hourly background task: delete thumbnails older than configured retention."""
    while True:
        await asyncio.sleep(3600)
        settings = get_settings()
        try:
            hours = int(settings.get("thumbnail_retention_hours", "168") or "168")
        except ValueError:
            hours = 168
        purge_old_thumbnails(hours)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    for subdir in ["enrolled", "embeddings", "temp", "thumbnails", "originals"]:
        (DATA_DIR / subdir).mkdir(parents=True, exist_ok=True)
    app.state.face_service = FaceService(str(DATA_DIR))
    asyncio.get_running_loop().run_in_executor(None, warm_up_model)
    settings = get_settings()
    try:
        retention_hours = int(settings.get("thumbnail_retention_hours", "168") or "168")
    except ValueError:
        retention_hours = 168
    purge_old_thumbnails(retention_hours)
    cleanup_task = asyncio.create_task(_thumbnail_cleanup_scheduler())
    start_scheduler()
    yield
    cleanup_task.cancel()


app = FastAPI(title="Myne", lifespan=lifespan)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/") or path.startswith("/api/auth/"):
        return await call_next(request)
    s = get_settings()
    if s.get("pin_enabled") != "true":
        return await call_next(request)
    client_host = request.client.host if request.client else ""
    try:
        is_internal = ipaddress.ip_address(client_host).is_private
    except ValueError:
        is_internal = client_host in ("localhost",)
    if is_internal:
        return await call_next(request)
    token = request.cookies.get("myne_session", "")
    if is_valid_session(token):
        return await call_next(request)
    return JSONResponse({"detail": "Unauthorized"}, status_code=401)


app.include_router(enrollment_router, prefix="/api/enrollment")
app.include_router(settings_router, prefix="/api/settings")
app.include_router(dashboard_router, prefix="/api/dashboard")
app.include_router(auth_router, prefix="/api/auth")
app.include_router(backup_router, prefix="/api/myne")
app.include_router(digest_router, prefix="/api/digest")

app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


@app.get("/api/activity/thumbnail/{filename}")
async def get_activity_thumbnail(filename: str):
    if not re.match(r'^[a-zA-Z0-9_.-]+$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = THUMBNAILS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="image/jpeg")


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/api/model-status")
async def model_status_endpoint():
    return get_model_status()


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(str(Path(__file__).parent / "static" / "favicon.svg"), media_type="image/svg+xml")


@app.get("/")
async def root():
    return FileResponse(str(Path(__file__).parent / "static" / "myne.html"))


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post("/api/analyze")
async def analyze_photo(request: Request, file: UploadFile,
                        group_id: str = "", group_name: str = "", sender: str = "unknown",
                        kid_ids: str = "", forward: bool = False, is_test: bool = False):
    """Called by the WhatsApp bot (or test panel) when a photo arrives."""
    file_bytes = await file.read()
    temp_path = DATA_DIR / "temp" / f"{uuid.uuid4()}.jpg"
    try:
        async with aiofiles.open(temp_path, "wb") as f:
            await f.write(file_bytes)

        db_settings = get_settings()
        threshold = float(db_settings.get("confidence_threshold", "0.35"))
        kid_id_list, kid_names, group_name = _resolve_kids(kid_ids, group_id, group_name, db_settings)

        if not kid_id_list:
            return {"matched": False, "faces_detected": 0, "matches": [],
                    "error": "No kids configured for this group"}

        face_service = request.app.state.face_service
        result = await asyncio.get_running_loop().run_in_executor(
            None, face_service.analyze_photo, str(temp_path), kid_id_list, threshold
        )
        matched_kids, best_confidence = _enrich_matches(result, kid_names)

        matched_photo_path = ""
        thumbnail_filename = ""
        if db_settings.get("thumbnails_enabled", "true") != "false":
            thumbnail_filename = _save_thumbnail(file_bytes)
        gp_saved = False
        if result.get("matched"):
            matched_photo_path = save_matched_photo(
                file_bytes, group_name, [m["kid_name"] for m in matched_kids], db_settings,
                original_filename=file.filename or ""
            )
            gp_saved = await save_to_google_photos(file_bytes, group_name, matched_kids, db_settings)
            if not matched_photo_path and db_settings.get("save_photos_enabled") == "true":
                print("[backend] Local folder save failed or path not set", flush=True)
            if not gp_saved and db_settings.get("google_photos_enabled") == "true":
                print("[backend] Google Photos upload failed", flush=True)

        forwarded = False
        if result.get("matched"):
            forward_to = db_settings.get("forward_to_id")
            if forward and forward_to:
                forwarded, fwd_err = await _forward_media(
                    forward_to, file_bytes, matched_kids, best_confidence
                )
                if fwd_err:
                    result["forward_error"] = fwd_err

        result["forwarded"] = forwarded
        result["saved_to_folder"] = bool(matched_photo_path)
        result["saved_to_gp"] = gp_saved
        row_id = 0
        if not is_test:
            row_id = log_activity(
                photo_filename=file.filename or "photo.jpg",
                sender=sender or "unknown",
                group_name=group_name or group_id or "unknown",
                faces_detected=result.get("faces_detected", 0),
                matched=result.get("matched", False),
                confidence=best_confidence,
                forwarded=forwarded,
                kid_names=", ".join(m["kid_name"] for m in matched_kids),
                matched_photo_path=matched_photo_path,
                thumbnail_filename=thumbnail_filename,
            )
            _save_original(file_bytes, row_id)

        return result
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/api/analyze-video")
async def analyze_video(request: Request, file: UploadFile,
                        group_id: str = "", group_name: str = "", sender: str = "unknown",
                        kid_ids: str = "", forward: bool = False, is_test: bool = False):
    """Called by the WhatsApp bot when a video arrives in a watched group."""
    file_bytes = await file.read()
    suffix = Path(file.filename or "video.mp4").suffix or ".mp4"
    temp_path = DATA_DIR / "temp" / f"{uuid.uuid4()}{suffix}"
    try:
        async with aiofiles.open(temp_path, "wb") as f:
            await f.write(file_bytes)

        db_settings = get_settings()
        threshold = float(db_settings.get("confidence_threshold", "0.35"))
        kid_id_list, kid_names, group_name = _resolve_kids(kid_ids, group_id, group_name, db_settings)

        if not kid_id_list:
            return {"matched": False, "faces_detected": 0, "matches": [],
                    "error": "No kids configured for this group"}

        face_service = request.app.state.face_service
        result = await asyncio.get_running_loop().run_in_executor(
            None, face_service.analyze_video, str(temp_path), kid_id_list, threshold
        )
        best_frame_bytes = result.pop("best_frame_bytes", None) or _extract_first_frame(str(temp_path))
        matched_kids, best_confidence = _enrich_matches(result, kid_names)

        matched_photo_path = ""
        thumbnail_filename = ""
        forwarded = False
        gp_saved = False
        if best_frame_bytes and db_settings.get("thumbnails_enabled", "true") != "false":
            thumbnail_filename = _save_thumbnail(best_frame_bytes)
        if result.get("matched"):
            video_filename = file.filename or "video.mp4"
            matched_photo_path = save_matched_photo(
                file_bytes, group_name, [m["kid_name"] for m in matched_kids], db_settings,
                original_filename=video_filename
            )
            gp_saved = await save_to_google_photos(file_bytes, group_name, matched_kids, db_settings,
                                                   filename=video_filename)
            if not matched_photo_path and db_settings.get("save_photos_enabled") == "true":
                print("[backend] Local folder save failed or path not set", flush=True)
            if not gp_saved and db_settings.get("google_photos_enabled") == "true":
                print("[backend] Google Photos upload failed", flush=True)
            forward_to = db_settings.get("forward_to_id")
            if forward and forward_to:
                forwarded, fwd_err = await _forward_media(
                    forward_to, file_bytes, matched_kids, best_confidence, is_video=True
                )
                if fwd_err:
                    result["forward_error"] = fwd_err

        result["forwarded"] = forwarded
        result["saved_to_folder"] = bool(matched_photo_path)
        result["saved_to_gp"] = gp_saved
        if not is_test:
            row_id = log_activity(
                photo_filename=file.filename or "video.mp4",
                sender=sender or "unknown",
                group_name=group_name or group_id or "unknown",
                faces_detected=result.get("faces_detected", 0),
                matched=result.get("matched", False),
                confidence=best_confidence,
                forwarded=forwarded,
                kid_names=", ".join(m["kid_name"] for m in matched_kids),
                matched_photo_path=matched_photo_path,
                thumbnail_filename=thumbnail_filename,
            )
            _save_original(file_bytes, row_id, suffix)
        return result
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/api/myne/rerun/{activity_id}")
async def rerun_actions(activity_id: int):
    """Re-run all configured actions (forward, Google Photos, local save) for a logged photo."""
    row = get_activity_by_id(activity_id)
    if not row:
        raise HTTPException(status_code=404, detail="Activity row not found")

    media_bytes: bytes | None = None
    media_path: Path | None = None
    if ORIGINALS_DIR.exists():
        matches = list(ORIGINALS_DIR.glob(f"{activity_id}.*"))
        if matches:
            media_path = matches[0]
    if media_path is None and row.matched_photo_path:
        media_path = Path(row.matched_photo_path)
    if media_path is not None:
        try:
            media_bytes = media_path.read_bytes()
        except OSError:
            pass
    if not media_bytes:
        raise HTTPException(status_code=404, detail="Original media no longer available (retention period may have expired)")

    is_video = media_path.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    settings = get_settings()
    matched_kids = [{"kid_name": n.strip(), "kid_id": n.strip()}
                    for n in (row.kid_names or "").split(",") if n.strip()]
    group_name = row.group_name or ""
    forward_to = settings.get("forward_to_id", "")

    gp_task = save_to_google_photos(media_bytes, group_name, matched_kids, settings,
                                    filename=media_path.name if is_video else "")
    fwd_task = (
        _forward_media(forward_to, media_bytes, matched_kids, row.confidence or 0.0, is_video=is_video)
        if forward_to else None
    )
    saved_to_folder = save_matched_photo(media_bytes, group_name,
                                         [k["kid_name"] for k in matched_kids], settings,
                                         original_filename=media_path.name)
    tasks = [gp_task] + ([fwd_task] if fwd_task else [])
    task_results = await asyncio.gather(*tasks, return_exceptions=True)

    gp_ok = task_results[0] if not isinstance(task_results[0], Exception) else False
    forwarded, fwd_err = (task_results[1] if fwd_task and not isinstance(task_results[1], Exception)
                          else (False, None))

    if not row.matched:
        mark_activity_manually_matched(activity_id)

    result: dict = {"forwarded": forwarded, "saved_to_folder": saved_to_folder, "saved_to_gp": bool(gp_ok)}
    if fwd_err:
        result["forward_error"] = fwd_err
    return result


@app.post("/api/wa-logout")
async def wa_logout():
    async with httpx.AsyncClient(timeout=10.0) as hx:
        r = await hx.post(f"{BOT_API_URL}/wa-logout")
        return r.json()


@app.post("/api/wa-disconnect")
async def wa_disconnect():
    async with httpx.AsyncClient(timeout=10.0) as hx:
        r = await hx.post(f"{BOT_API_URL}/wa-disconnect")
        return r.json()


@app.post("/api/wa-connect")
async def wa_connect():
    async with httpx.AsyncClient(timeout=10.0) as hx:
        r = await hx.post(f"{BOT_API_URL}/wa-connect")
        return r.json()
