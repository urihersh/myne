"""
Face detection and recognition service wrapping InsightFace.

The InsightFace model is loaded lazily on first use (buffalo_l, CPU-only).
Embeddings are unit-length vectors so cosine similarity equals dot product —
no normalisation step required at comparison time.
"""

import base64
import shutil
import threading
import uuid
import numpy as np
import cv2
from pathlib import Path

_fa = None  # insightface FaceAnalysis singleton
_model_status = "not_started"  # not_started | loading | ready | error
_model_error: str | None = None
_model_lock = threading.Lock()  # guards status transitions and _fa assignment


def get_model_status() -> dict:
    with _model_lock:
        return {"status": _model_status, "error": _model_error}


def warm_up_model() -> None:
    """Download and load the InsightFace model. Safe to call from a background thread."""
    global _fa, _model_status, _model_error
    with _model_lock:
        if _model_status in ("ready", "loading"):
            return
        _model_status = "loading"
    # Lock released — do the long download/load outside the lock so callers
    # can still read status while it's in progress.
    print("[face_service] Loading InsightFace buffalo_l model…", flush=True)
    try:
        from insightface.app import FaceAnalysis
        fa = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        fa.prepare(ctx_id=0, det_size=(640, 640))
        with _model_lock:
            _fa = fa
            _model_status = "ready"
        print("[face_service] Model ready.", flush=True)
    except Exception as e:
        with _model_lock:
            _model_status = "error"
            _model_error = str(e)
        print(f"[face_service] Model load failed: {e}", flush=True)
        raise


def _get_model():
    with _model_lock:
        if _fa is not None:
            return _fa
    # Model not ready yet — trigger a synchronous load (fallback path)
    warm_up_model()
    return _fa


def _largest_face(faces: list):
    """Return the face with the largest bounding-box area."""
    return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))


def _bbox_center_dist(a, b) -> float:
    """Distance between the centers of two [x1,y1,x2,y2] boxes (smaller = closer)."""
    ax, ay = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
    bx, by = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _best_match(face_embeddings: list, stored: list) -> tuple[float, int]:
    """Return (best_similarity, index into face_embeddings) for the face closest to any
    stored embedding. Shared by analyze_photo and analyze_video's per-frame scoring."""
    best_conf, best_idx = -1.0, -1
    for i, fe in enumerate(face_embeddings):
        for se in stored:
            d = float(np.dot(fe, se))
            if d > best_conf:
                best_conf, best_idx = d, i
    return best_conf, best_idx


def _negative_confidence(face_embedding, negatives: list) -> float:
    """Similarity of one face embedding to the closest stored negative example (0.0 if none)."""
    return max((float(np.dot(face_embedding, ne)) for ne in negatives), default=0.0)


DEFAULT_THRESHOLD = 0.35
NEG_MARGIN = 0.0  # suppress a match if similarity-to-negative >= similarity-to-positive - this margin


class FaceService:
    def __init__(self, data_dir: str):
        self.kids_dir = Path(data_dir) / "kids"
        self.kids_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, list] = {}  # kid_id -> [normed_embeddings]
        self._neg_cache: dict[str, list] = {}  # kid_id -> [normed_embeddings] (negative examples)

    # ── Directory helpers ──────────────────────────────────────────────────────

    def kid_dir(self, kid_id: str) -> Path:
        d = self.kids_dir / kid_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def emb_dir(self, kid_id: str) -> Path:
        d = self.kid_dir(kid_id) / "embeddings"
        d.mkdir(exist_ok=True)
        return d

    def enrolled_dir(self, kid_id: str) -> Path:
        d = self.kid_dir(kid_id) / "enrolled"
        d.mkdir(exist_ok=True)
        return d

    def neg_emb_dir(self, kid_id: str) -> Path:
        d = self.kid_dir(kid_id) / "negative_embeddings"
        d.mkdir(exist_ok=True)
        return d

    # ── Image helpers ──────────────────────────────────────────────────────────

    def _read(self, path: str) -> np.ndarray:
        img = cv2.imread(path)
        if img is None:
            raise ValueError(f"Could not read image: {path}")
        return img

    def detect_faces(self, image_path: str) -> list:
        try:
            return _get_model().get(self._read(image_path))
        except Exception:
            return []

    def detect_faces_with_image(self, image_path: str) -> tuple[list, np.ndarray | None]:
        """Return (faces, img) in one read — avoids re-reading the file for subsequent ops."""
        try:
            img = self._read(image_path)
            return _get_model().get(img), img
        except Exception:
            return [], None

    def get_face_crop_b64_from_array(self, img: np.ndarray, faces: list) -> str | None:
        """Crop the largest face from an already-loaded image."""
        if not faces:
            return None
        try:
            x1, y1, x2, y2 = [max(0, int(v)) for v in _largest_face(faces).bbox]
            _, buf = cv2.imencode(".jpg", img[y1:y2, x1:x2])
            return base64.b64encode(buf.tobytes()).decode()
        except Exception:
            return None

    def classify_face_quality(self, faces: list, img: np.ndarray) -> tuple[float, str]:
        """Return (face_size_ratio, quality_label) for the largest detected face."""
        if not faces:
            return 0.0, "small"
        bbox = _largest_face(faces).bbox
        face_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        img_area = img.shape[0] * img.shape[1]
        ratio = round(face_area / img_area, 3)
        if ratio < 0.02:
            return ratio, "small"
        if ratio < 0.05:
            return ratio, "ok"
        return ratio, "good"

    def get_face_crop_b64(self, image_path: str) -> str | None:
        try:
            img = self._read(image_path)
            faces = _get_model().get(img)
            if not faces:
                return None
            return self.get_face_crop_b64_from_array(img, faces)
        except Exception:
            return None

    def get_face_crop_b64_at_bbox(self, image_path: str, bbox: list[float]) -> str | None:
        """Crop a specific region (given a stored bbox) from the original image on disk."""
        try:
            img = self._read(image_path)
            h, w = img.shape[:2]
            x1, y1, x2, y2 = [max(0, min(int(v), w if i % 2 == 0 else h)) for i, v in enumerate(bbox)]
            if x2 <= x1 or y2 <= y1:
                return None
            _, buf = cv2.imencode(".jpg", img[y1:y2, x1:x2])
            return base64.b64encode(buf.tobytes()).decode()
        except Exception:
            return None

    def get_embedding_at_bbox(
        self, image_path: str, target_bbox: list[float]
    ) -> tuple[np.ndarray, list, list, tuple[int, int]] | None:
        """Re-detect faces in the original image and return the embedding of whichever
        detected face is closest to `target_bbox` — used to turn a bbox stored on an
        activity-log row back into a fresh embedding for negative/confirmed enrollment.

        Returns (normed_embedding, matched_bbox, all_faces_bboxes, image_shape) or None.
        """
        try:
            img = self._read(image_path)
            faces = _get_model().get(img)
            if not faces:
                return None
            best_face = min(faces, key=lambda f: _bbox_center_dist(f.bbox, target_bbox))
            all_bboxes = [f.bbox.tolist() for f in faces]
            return best_face.normed_embedding, best_face.bbox.tolist(), all_bboxes, img.shape[:2]
        except Exception:
            return None

    # ── Enrollment ─────────────────────────────────────────────────────────────

    def enroll_photo(self, image_path: str, photo_id: str, kid_id: str) -> dict:
        try:
            faces = _get_model().get(self._read(image_path))
            if not faces:
                return {"success": False, "error": "No face detected"}
            np.save(str(self.emb_dir(kid_id) / f"{photo_id}.npy"), _largest_face(faces).normed_embedding)
            self._cache.pop(kid_id, None)
            return {"success": True, "photo_id": photo_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_enrollment(self, photo_id: str, kid_id: str) -> bool:
        emb = self.emb_dir(kid_id) / f"{photo_id}.npy"
        removed = emb.exists()
        emb.unlink(missing_ok=True)
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            (self.enrolled_dir(kid_id) / f"{photo_id}{ext}").unlink(missing_ok=True)
        self._cache.pop(kid_id, None)
        return removed

    def delete_kid(self, kid_id: str) -> None:
        d = self.kids_dir / kid_id
        if d.exists():
            shutil.rmtree(d)
        self._cache.pop(kid_id, None)
        self._neg_cache.pop(kid_id, None)

    def add_negative_embedding(self, kid_id: str, embedding: np.ndarray) -> str:
        """Store a 'this is NOT kid_id' embedding, e.g. from a confirmed false positive."""
        photo_id = str(uuid.uuid4())
        np.save(str(self.neg_emb_dir(kid_id) / f"{photo_id}.npy"), embedding)
        self._neg_cache.pop(kid_id, None)
        return photo_id

    def add_confirmed_embedding(self, kid_id: str, image_path: str, bbox: list[float], source_label: str = "") -> dict:
        """Auto-enroll a face from a user-confirmed true-positive match.

        Gated on face quality and on not being a near-duplicate of an existing embedding,
        so a stream of confirmations can't degrade the pool. Saves through the same
        enrolled/embeddings storage used by manual enrollment, so it shows up in the
        normal Enrolled Photos UI.
        """
        found = self.get_embedding_at_bbox(image_path, bbox)
        if found is None:
            return {"added": False, "reason": "face_not_found"}
        embedding, matched_bbox, _, (img_h, img_w) = found

        face_area = (matched_bbox[2] - matched_bbox[0]) * (matched_bbox[3] - matched_bbox[1])
        img_area = img_h * img_w
        ratio = face_area / img_area if img_area else 0.0
        if ratio < 0.02:
            return {"added": False, "reason": "face_too_small"}

        stored = self._load_embeddings(kid_id)
        if stored and max(float(np.dot(embedding, se)) for se in stored) > 0.98:
            return {"added": False, "reason": "duplicate"}

        photo_id = str(uuid.uuid4())
        np.save(str(self.emb_dir(kid_id) / f"{photo_id}.npy"), embedding)
        try:
            crop_b64 = self.get_face_crop_b64_at_bbox(image_path, matched_bbox)
            if crop_b64:
                (self.enrolled_dir(kid_id) / f"{photo_id}.jpg").write_bytes(base64.b64decode(crop_b64))
        except Exception:
            pass
        self._cache.pop(kid_id, None)
        return {"added": True, "photo_id": photo_id, "filename": f"confirmed_{source_label or photo_id}.jpg"}

    # ── Recognition ────────────────────────────────────────────────────────────

    def _load_embeddings(self, kid_id: str) -> list:
        if kid_id in self._cache:
            return self._cache[kid_id]
        emb_d = self.kids_dir / kid_id / "embeddings"
        if not emb_d.exists():
            return []
        result = [np.load(str(f)) for f in emb_d.glob("*.npy")]
        self._cache[kid_id] = result
        return result

    def _load_negative_embeddings(self, kid_id: str) -> list:
        if kid_id in self._neg_cache:
            return self._neg_cache[kid_id]
        emb_d = self.kids_dir / kid_id / "negative_embeddings"
        if not emb_d.exists():
            return []
        result = [np.load(str(f)) for f in emb_d.glob("*.npy")]
        self._neg_cache[kid_id] = result
        return result

    def analyze_photo(self, image_path: str, kid_ids: list[str], thresholds: dict[str, float]) -> dict:
        """Check a photo against all specified kids.

        Returns overall match status, per-kid breakdown (incl. which face matched), and face count.
        Uses cosine similarity (= dot product on unit-length normed embeddings).

        `thresholds` maps kid_id -> effective threshold, letting a kid-specific override
        coexist with the global default (the caller resolves the fallback).
        """
        try:
            faces = _get_model().get(self._read(image_path))
        except Exception as e:
            return {"matched": False, "faces_detected": 0, "matches": [], "error": str(e)}

        if not faces:
            return {"matched": False, "faces_detected": 0, "matches": []}

        face_embeddings = [f.normed_embedding for f in faces]
        all_faces_bboxes = [f.bbox.tolist() for f in faces]
        kid_results = []
        for kid_id in kid_ids:
            stored = self._load_embeddings(kid_id)
            if not stored:
                continue
            best_conf, best_idx = _best_match(face_embeddings, stored)

            negatives = self._load_negative_embeddings(kid_id)
            neg_conf = _negative_confidence(face_embeddings[best_idx], negatives) if negatives else 0.0
            suppressed = bool(negatives) and neg_conf >= best_conf - NEG_MARGIN

            kid_results.append({
                "kid_id": kid_id,
                "confidence": round(best_conf, 4),
                "matched": best_conf >= thresholds.get(kid_id, DEFAULT_THRESHOLD) and not suppressed,
                "bbox": all_faces_bboxes[best_idx] if best_idx >= 0 else None,
                "suppressed_by_negative": suppressed,
                "neg_confidence": round(neg_conf, 4) if negatives else None,
            })

        return {
            "matched": any(r["matched"] for r in kid_results),
            "faces_detected": len(faces),
            "matches": kid_results,
            "all_faces": all_faces_bboxes,
        }

    def analyze_video(
        self,
        video_path: str,
        kid_ids: list[str],
        thresholds: dict[str, float],
    ) -> dict:
        """Sample frames from a video and match against enrolled kids.

        Samples every 0.5 s of video time (capped at 400 frames) so any appearance
        of ≥0.5 s is virtually guaranteed at least one sample. Additional improvements:
        - Blurry frames skipped via Laplacian variance (bad frames hurt embeddings)
        - Small/missing faces retried on a 2x upscaled frame
        - Per-kid score = average of top-3 frame confidences (more robust than single-frame max)
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {
                "matched": False, "faces_detected": 0, "matches": [],
                "error": "Could not open video", "frames_sampled": 0,
            }

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        # Sample every 0.5 s — guarantees coverage of any ≥0.5 s appearance.
        # Fall back to every 15 frames if FPS is unavailable.
        interval = max(1, int(fps * 0.5))
        if total_frames > 0:
            sample_indices = set(range(0, total_frames, interval))
        else:
            sample_indices = {i * interval for i in range(400)}
        # Safety cap for unusually long videos
        if len(sample_indices) > 400:
            step = len(sample_indices) / 400
            sample_indices = {int(i * step) for i in range(400)}

        # Load embeddings once outside the frame loop
        stored_embeddings = {kid_id: self._load_embeddings(kid_id) for kid_id in kid_ids}
        negative_embeddings = {kid_id: self._load_negative_embeddings(kid_id) for kid_id in kid_ids}

        # Top-3 confidences per kid across all frames
        kid_top_confs: dict[str, list[float]] = {kid_id: [] for kid_id in kid_ids}
        best_overall_conf = 0.0
        best_frame: np.ndarray | None = None
        best_frame_bboxes: dict[str, list] = {}
        best_frame_all_faces: list = []
        max_faces_seen = 0
        frame_idx = 0
        frames_sampled = 0
        neg_suppressed_frames = 0
        model = _get_model()

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx not in sample_indices:
                    frame_idx += 1
                    continue
                frame_idx += 1

                # Skip frames that are too blurry to produce useful embeddings
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if cv2.Laplacian(gray, cv2.CV_64F).var() < 10.0:
                    continue

                frames_sampled += 1

                try:
                    faces = model.get(frame)

                    # Retry on 2x upscale if no faces found or any face is small
                    small_face = faces and any(
                        (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]) < 80 * 80
                        for f in faces
                    )
                    if not faces or small_face:
                        h, w = frame.shape[:2]
                        up = cv2.resize(frame, (w * 2, h * 2), interpolation=cv2.INTER_LINEAR)
                        up_faces = model.get(up)
                        if up_faces:
                            faces = up_faces
                except Exception:
                    continue

                if not faces:
                    continue

                max_faces_seen = max(max_faces_seen, len(faces))
                face_embeddings = [f.normed_embedding for f in faces]
                frame_face_bboxes = [f.bbox.tolist() for f in faces]
                frame_best_conf = 0.0
                frame_kid_bboxes: dict[str, list] = {}
                frame_had_suppression = False

                for kid_id in kid_ids:
                    stored = stored_embeddings.get(kid_id)
                    if not stored:
                        continue
                    best_conf, best_idx = _best_match(face_embeddings, stored)

                    negatives = negative_embeddings.get(kid_id)
                    if negatives and best_idx >= 0:
                        neg_conf = _negative_confidence(face_embeddings[best_idx], negatives)
                        if neg_conf >= best_conf - NEG_MARGIN:
                            frame_had_suppression = True
                            continue  # this frame's face looks like a known look-alike — skip as evidence

                    # Maintain sorted top-3 list for this kid
                    top = kid_top_confs[kid_id]
                    top.append(best_conf)
                    top.sort(reverse=True)
                    kid_top_confs[kid_id] = top[:3]
                    if best_idx >= 0:
                        frame_kid_bboxes[kid_id] = frame_face_bboxes[best_idx]
                    if best_conf > frame_best_conf:
                        frame_best_conf = best_conf

                if frame_had_suppression:
                    neg_suppressed_frames += 1

                if frame_best_conf > best_overall_conf:
                    best_overall_conf = frame_best_conf
                    best_frame = frame.copy()
                    best_frame_bboxes = frame_kid_bboxes
                    best_frame_all_faces = frame_face_bboxes

                # Early exit: if we have 3 strong matches for any kid, stop processing
                # (confident match already established, no need to scan entire video)
                for kid_id in kid_ids:
                    top = kid_top_confs[kid_id]
                    if len(top) >= 3 and min(top[:3]) >= thresholds.get(kid_id, DEFAULT_THRESHOLD):
                        cap.release()
                        break
                else:
                    continue
                break
        finally:
            cap.release()

        best_frame_bytes: bytes | None = None
        if best_frame is not None:
            try:
                _, buf = cv2.imencode(".jpg", best_frame)
                best_frame_bytes = buf.tobytes()
            except Exception:
                pass

        kid_results = []
        for kid_id in kid_ids:
            if not stored_embeddings.get(kid_id):
                continue
            top = kid_top_confs[kid_id]
            final_conf = sum(top) / len(top) if top else 0.0
            kid_results.append({
                "kid_id": kid_id,
                "confidence": round(final_conf, 4),
                "matched": final_conf >= thresholds.get(kid_id, DEFAULT_THRESHOLD),
                "bbox": best_frame_bboxes.get(kid_id),
            })

        return {
            "matched": any(r["matched"] for r in kid_results),
            "faces_detected": max_faces_seen,
            "matches": kid_results,
            "all_faces": best_frame_all_faces,
            "frames_sampled": frames_sampled,
            "neg_suppressed_frames": neg_suppressed_frames,
            "best_frame_bytes": best_frame_bytes,
        }

    def get_enrolled_count(self, kid_id: str) -> int:
        d = self.kids_dir / kid_id / "embeddings"
        return len(list(d.glob("*.npy"))) if d.exists() else 0
