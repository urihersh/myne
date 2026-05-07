from fastapi import APIRouter, UploadFile, Request, HTTPException
from fastapi.responses import Response
import asyncio
import base64
from pathlib import Path
from datetime import datetime, timezone
import os
import uuid
import json
import aiofiles
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent.parent.parent / "data"))).resolve()
KIDS_FILE = DATA_DIR / "kids.json"

router = APIRouter(tags=["enrollment"])


# ── Kids metadata helpers ──────────────────────────────────────────────────────

def load_kids() -> list:
    if KIDS_FILE.exists():
        return json.loads(KIDS_FILE.read_text())
    return []


def save_kids(kids: list):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    KIDS_FILE.write_text(json.dumps(kids, indent=2))


def load_kid_meta(kid_id: str) -> dict:
    path = DATA_DIR / "kids" / kid_id / "metadata.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_kid_meta(kid_id: str, meta: dict):
    path = DATA_DIR / "kids" / kid_id / "metadata.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2))


# ── Kid management ─────────────────────────────────────────────────────────────

@router.get("/kids")
async def list_kids(request: Request):
    kids = load_kids()
    face_service = request.app.state.face_service
    for k in kids:
        k["enrolled_count"] = face_service.get_enrolled_count(k["id"])
    return {"kids": kids}


@router.post("/kids")
async def create_kid(request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    kid = {"id": str(uuid.uuid4()), "name": name, "created_at": datetime.now(timezone.utc).isoformat()}
    kids = load_kids()
    kids.append(kid)
    save_kids(kids)
    return kid


@router.patch("/kids/{kid_id}")
async def rename_kid(kid_id: str, request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    kids = load_kids()
    kid = next((k for k in kids if k["id"] == kid_id), None)
    if not kid:
        raise HTTPException(status_code=404, detail="Kid not found")
    kid["name"] = name
    save_kids(kids)
    return kid


@router.delete("/kids/{kid_id}")
async def delete_kid(kid_id: str, request: Request):
    kids = load_kids()
    if not any(k["id"] == kid_id for k in kids):
        raise HTTPException(status_code=404, detail="Kid not found")
    kids = [k for k in kids if k["id"] != kid_id]
    save_kids(kids)
    request.app.state.face_service.delete_kid(kid_id)
    return {"success": True}


# ── Photo enrollment ───────────────────────────────────────────────────────────

@router.post("/kids/{kid_id}/upload")
async def upload_photo(kid_id: str, request: Request, file: UploadFile):
    kids = load_kids()
    if not any(k["id"] == kid_id for k in kids):
        raise HTTPException(status_code=404, detail="Kid not found")

    face_service = request.app.state.face_service
    enrolled_dir = face_service.enrolled_dir(kid_id)

    photo_id = str(uuid.uuid4())
    suffix = Path(file.filename or "photo.jpg").suffix or ".jpg"
    save_path = enrolled_dir / f"{photo_id}{suffix}"

    async with aiofiles.open(save_path, "wb") as f:
        await f.write(await file.read())

    # Single read + single model inference for all derived data (run in thread — blocks CPU)
    faces, img = await asyncio.get_running_loop().run_in_executor(
        None, face_service.detect_faces_with_image, str(save_path)
    )
    if not faces:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="No face detected. Try a clearer, well-lit photo.")

    face_size_ratio, quality = face_service.classify_face_quality(faces, img)
    face_crop_b64 = face_service.get_face_crop_b64_from_array(img, faces)

    return {
        "photo_id": photo_id,
        "filename": file.filename,
        "faces_found": len(faces),
        "face_crop": face_crop_b64,
        "face_size_ratio": float(face_size_ratio),
        "quality": quality,
    }


@router.post("/kids/{kid_id}/confirm/{photo_id}")
async def confirm_enrollment(kid_id: str, photo_id: str, request: Request):
    face_service = request.app.state.face_service
    enrolled_dir = face_service.enrolled_dir(kid_id)
    matches = list(enrolled_dir.glob(f"{photo_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Photo not found. Please re-upload.")

    result = await asyncio.get_running_loop().run_in_executor(
        None, face_service.enroll_photo, str(matches[0]), photo_id, kid_id
    )
    if not result["success"]:
        raise HTTPException(status_code=422, detail=result.get("error", "Enrollment failed"))

    meta = load_kid_meta(kid_id)
    meta[photo_id] = {"photo_id": photo_id, "filename": matches[0].name, "enrolled_at": datetime.now(timezone.utc).isoformat()}
    save_kid_meta(kid_id, meta)

    return {"success": True, "enrolled_count": face_service.get_enrolled_count(kid_id)}


@router.delete("/kids/{kid_id}/photos/{photo_id}/original")
async def delete_original_photo(kid_id: str, photo_id: str, request: Request):
    """Delete the original image file but keep the embedding — recognition still works."""
    face_service = request.app.state.face_service
    enrolled_dir = face_service.enrolled_dir(kid_id)
    deleted = False
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        p = enrolled_dir / f"{photo_id}{ext}"
        if p.exists():
            p.unlink()
            deleted = True
    if not deleted:
        raise HTTPException(status_code=404, detail="Original photo not found (may already be deleted)")
    return {"success": True}


@router.delete("/kids/{kid_id}/photos/{photo_id}")
async def remove_photo(kid_id: str, photo_id: str, request: Request):
    face_service = request.app.state.face_service
    removed = face_service.remove_enrollment(photo_id, kid_id)
    meta = load_kid_meta(kid_id)
    meta.pop(photo_id, None)
    save_kid_meta(kid_id, meta)
    if not removed:
        raise HTTPException(status_code=404, detail="Photo not found")
    return {"success": True, "enrolled_count": face_service.get_enrolled_count(kid_id)}


@router.get("/kids/{kid_id}/thumbnail")
async def kid_thumbnail(kid_id: str, request: Request):
    face_service = request.app.state.face_service
    enrolled_dir = face_service.enrolled_dir(kid_id)
    photos = sorted(enrolled_dir.glob("*.*")) if enrolled_dir.exists() else []
    if not photos:
        raise HTTPException(status_code=404, detail="No photos enrolled")
    crop_b64 = face_service.get_face_crop_b64(str(photos[0]))
    if not crop_b64:
        raise HTTPException(status_code=404, detail="Could not generate thumbnail")
    return Response(content=base64.b64decode(crop_b64), media_type="image/jpeg",
                    headers={"Cache-Control": "max-age=3600"})


@router.get("/kids/{kid_id}/photos/{photo_id}/thumbnail")
async def photo_thumbnail(kid_id: str, photo_id: str, request: Request):
    face_service = request.app.state.face_service
    enrolled_dir = face_service.enrolled_dir(kid_id)
    matches = list(enrolled_dir.glob(f"{photo_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Photo not found")
    crop_b64 = face_service.get_face_crop_b64(str(matches[0]))
    if not crop_b64:
        raise HTTPException(status_code=404, detail="Could not generate thumbnail")
    return Response(content=base64.b64decode(crop_b64), media_type="image/jpeg",
                    headers={"Cache-Control": "max-age=3600"})


@router.get("/kids/{kid_id}/photos")
async def list_photos(kid_id: str, request: Request):
    meta = load_kid_meta(kid_id)
    count = request.app.state.face_service.get_enrolled_count(kid_id)
    return {"photos": list(meta.values()), "count": count}
