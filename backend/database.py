"""
SQLAlchemy models and all database access helpers.

The engine is initialised lazily by `init_db()` which is called once during
FastAPI's lifespan startup.  All session management follows the open/close
pattern so that nothing leaks between requests.
"""

from sqlalchemy import create_engine, Column, Index, Integer, String, Boolean, Float, DateTime, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent.parent / "data"))).resolve()
DB_PATH = DATA_DIR / "myne.db"
ORIGINALS_DIR = DATA_DIR / "originals"
DIGEST_DIR = DATA_DIR / "digest_queue"

engine = None
SessionLocal = None
Base = declarative_base()


# ── Models ─────────────────────────────────────────────────────────────────────

class ActivityLog(Base):
    __tablename__ = "activity_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    photo_filename = Column(String)
    sender = Column(String)
    group_name = Column(String)
    faces_detected = Column(Integer, default=0)
    matched = Column(Boolean, default=False)
    confidence = Column(Float, default=0.0)
    forwarded = Column(Boolean, default=False)
    saved_to_gp = Column(Boolean, default=False)
    kid_names = Column(String, default="")
    matched_photo_path = Column(String, default="")
    thumbnail_filename = Column(String, default="")
    manually_matched = Column(Boolean, default=False)

    __table_args__ = (
        # Most queries filter/sort by timestamp; matched filter is also common
        Index("ix_activity_log_timestamp", "timestamp"),
        Index("ix_activity_log_matched_timestamp", "matched", "timestamp"),
    )


class AppConfig(Base):
    __tablename__ = "app_config"
    key = Column(String, primary_key=True)
    value = Column(String)


class DigestQueue(Base):
    __tablename__ = "digest_queue"
    id = Column(Integer, primary_key=True, autoincrement=True)
    queued_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sender = Column(String, default="")
    group_name = Column(String, default="")
    kid_names = Column(String, default="")
    is_video = Column(Boolean, default=False)
    media_path = Column(String, default="")


# ── Initialisation ─────────────────────────────────────────────────────────────

def _add_column(conn, table: str, column: str, definition: str) -> None:
    """Add a column to an existing table, silently skipping if it already exists."""
    try:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        conn.commit()
    except OperationalError as exc:
        if "duplicate column" not in str(exc).lower() and "already has column" not in str(exc).lower():
            raise


def init_db() -> None:
    global engine, SessionLocal
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{DB_PATH}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    # Schema migrations: safe to run on every startup
    with engine.connect() as conn:
        _add_column(conn, "activity_log", "kid_names",        "TEXT DEFAULT ''")
        _add_column(conn, "activity_log", "matched_photo_path", "TEXT DEFAULT ''")
        _add_column(conn, "activity_log", "thumbnail_filename", "TEXT DEFAULT ''")
        _add_column(conn, "activity_log", "manually_matched",  "INTEGER DEFAULT 0")
        _add_column(conn, "activity_log", "saved_to_gp",       "INTEGER DEFAULT 0")


# ── Settings helpers ───────────────────────────────────────────────────────────

def get_settings() -> dict:
    db = SessionLocal()
    try:
        return {row.key: row.value for row in db.query(AppConfig).all()}
    finally:
        db.close()


def save_setting(key: str, value: str) -> None:
    db = SessionLocal()
    try:
        row = db.query(AppConfig).filter(AppConfig.key == key).first()
        if row:
            row.value = value
        else:
            db.add(AppConfig(key=key, value=value))
        db.commit()
    finally:
        db.close()


# ── Activity log helpers ───────────────────────────────────────────────────────

def log_activity(
    photo_filename: str,
    sender: str,
    group_name: str,
    faces_detected: int,
    matched: bool,
    confidence: float,
    forwarded: bool,
    kid_names: str = "",
    matched_photo_path: str = "",
    thumbnail_filename: str = "",
    saved_to_gp: bool = False,
) -> int:
    db = SessionLocal()
    try:
        row = ActivityLog(
            photo_filename=photo_filename,
            sender=sender,
            group_name=group_name,
            faces_detected=faces_detected,
            matched=matched,
            confidence=confidence,
            forwarded=forwarded,
            saved_to_gp=saved_to_gp,
            kid_names=kid_names,
            matched_photo_path=matched_photo_path,
            thumbnail_filename=thumbnail_filename,
        )
        db.add(row)
        db.commit()
        return row.id
    finally:
        db.close()


def get_activity_log(
    limit: int = 1000,
    matched: bool | None = None,
    group_name: str = "",
    kid_name: str = "",
    since: datetime | None = None,
) -> list:
    db = SessionLocal()
    try:
        query = db.query(ActivityLog).order_by(ActivityLog.timestamp.desc())
        if since is not None:
            query = query.filter(ActivityLog.timestamp >= since)
        if matched is not None:
            query = query.filter(ActivityLog.matched == matched)
        if group_name:
            query = query.filter(ActivityLog.group_name.ilike(f"%{group_name}%"))
        if kid_name:
            query = query.filter(ActivityLog.kid_names.ilike(f"%{kid_name}%"))
        rows = query.limit(limit).all()

        original_ids = (
            {p.stem for p in ORIGINALS_DIR.iterdir() if p.is_file()}
            if ORIGINALS_DIR.exists() else set()
        )
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat() + "Z",
                "photo_filename": r.photo_filename,
                "sender": r.sender,
                "group_name": r.group_name,
                "faces_detected": r.faces_detected,
                "matched": r.matched,
                "confidence": r.confidence,
                "forwarded": r.forwarded,
                "saved_to_gp": bool(r.saved_to_gp),
                "kid_names": r.kid_names or "",
                "matched_photo_path": r.matched_photo_path or "",
                "thumbnail_filename": r.thumbnail_filename or "",
                "manually_matched": bool(r.manually_matched),
                "has_original": (
                    str(r.id) in original_ids
                    or bool(r.matched_photo_path and Path(r.matched_photo_path).exists())
                ),
            }
            for r in rows
        ]
    finally:
        db.close()


def mark_activity_manually_matched(activity_id: int) -> None:
    db = SessionLocal()
    try:
        row = db.query(ActivityLog).filter(ActivityLog.id == activity_id).first()
        if row:
            row.matched = True
            row.manually_matched = True
            db.commit()
    finally:
        db.close()


def get_activity_by_id(activity_id: int) -> ActivityLog | None:
    db = SessionLocal()
    try:
        return db.query(ActivityLog).filter(ActivityLog.id == activity_id).first()
    finally:
        db.close()


def clear_activity_log() -> None:
    db = SessionLocal()
    try:
        db.query(ActivityLog).delete()
        db.commit()
    finally:
        db.close()


# ── Stats ──────────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    db = SessionLocal()
    try:
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        total = db.query(ActivityLog).count()
        total_matched = db.query(ActivityLog).filter(ActivityLog.matched.is_(True)).count()
        today_total = db.query(ActivityLog).filter(ActivityLog.timestamp >= today).count()
        today_matched = db.query(ActivityLog).filter(
            ActivityLog.matched.is_(True),
            ActivityLog.timestamp >= today,
        ).count()
        return {
            "total_processed": total,
            "total_matched": total_matched,
            "total_unmatched": total - total_matched,
            "today_matched": today_matched,
            "today_unmatched": today_total - today_matched,
        }
    finally:
        db.close()


# ── Digest queue helpers ───────────────────────────────────────────────────────

def enqueue_digest(sender: str, group_name: str, kid_names: str, is_video: bool, media_path: str) -> None:
    db = SessionLocal()
    try:
        db.add(DigestQueue(
            sender=sender,
            group_name=group_name,
            kid_names=kid_names,
            is_video=is_video,
            media_path=media_path,
        ))
        db.commit()
    finally:
        db.close()


def get_digest_queue() -> list:
    db = SessionLocal()
    try:
        rows = db.query(DigestQueue).order_by(DigestQueue.queued_at.asc()).all()
        return [
            {
                "id": r.id,
                "sender": r.sender,
                "group_name": r.group_name,
                "kid_names": r.kid_names,
                "is_video": r.is_video,
                "media_path": r.media_path,
                "queued_at": r.queued_at.isoformat() + "Z",
            }
            for r in rows
        ]
    finally:
        db.close()


def clear_digest_queue() -> None:
    db = SessionLocal()
    try:
        rows = db.query(DigestQueue).all()
        for r in rows:
            try:
                Path(r.media_path).unlink(missing_ok=True)
            except Exception:
                pass
        db.query(DigestQueue).delete()
        db.commit()
    finally:
        db.close()
