"""
Activity log, stats, Wrapped report, and memory book endpoints.
"""

from fastapi import APIRouter
from fastapi.responses import Response, FileResponse
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")

import database as _db
from database import get_stats, get_activity_log, clear_activity_log, ActivityLog

DATA_DIR = Path(os.getenv("DATA_DIR", str(Path(__file__).parent.parent.parent / "data"))).resolve()

router = APIRouter(tags=["dashboard"])

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@router.get("/stats")
async def stats():
    s = get_stats()
    kids_dir = DATA_DIR / "kids"
    s["enrolled_photos"] = len(list(kids_dir.glob("*/embeddings/*.npy"))) if kids_dir.exists() else 0
    return s


@router.get("/activity")
async def activity(
    limit: int = 1000,
    days: int = 7,
    matched: bool | None = None,
    group_name: str = "",
    kid_name: str = "",
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return {"activity": get_activity_log(limit, matched=matched, group_name=group_name,
                                         kid_name=kid_name, since=since)}


@router.delete("/activity")
async def delete_activity():
    clear_activity_log()
    return {"ok": True}


@router.get("/wrapped")
async def wrapped(year: int | None = None):
    """Return yearly stats for the Wrapped report."""
    target_year = year or datetime.now().year
    db = _db.SessionLocal()
    try:
        rows = db.query(ActivityLog).filter(
            ActivityLog.timestamp >= datetime(target_year, 1, 1),
            ActivityLog.timestamp < datetime(target_year + 1, 1, 1),
        ).all()
    finally:
        db.close()

    if not rows:
        return {
            "year": target_year, "total_scanned": 0, "total_matched": 0,
            "match_rate": 0, "monthly_counts": [], "top_groups": [],
            "top_kids": [], "best_month": None, "most_active_dow": None,
        }

    total_scanned = len(rows)
    matched_rows = [r for r in rows if r.matched]
    total_matched = len(matched_rows)
    match_rate = round(total_matched / total_scanned * 100, 1) if total_scanned else 0

    monthly: dict[int, dict] = {i: {"scanned": 0, "matched": 0} for i in range(1, 13)}
    for r in rows:
        m = r.timestamp.month
        monthly[m]["scanned"] += 1
        if r.matched:
            monthly[m]["matched"] += 1
    monthly_counts = [
        {"month": MONTH_NAMES[i - 1], "month_num": i, **monthly[i]}
        for i in range(1, 13)
    ]

    group_counter: Counter = Counter(
        r.group_name for r in matched_rows if r.group_name
    )
    top_groups = [{"name": n, "matched": c} for n, c in group_counter.most_common(5)]

    kid_counter: Counter = Counter()
    for r in matched_rows:
        for name in (r.kid_names or "").split(","):
            if name.strip():
                kid_counter[name.strip()] += 1
    top_kids = [{"name": n, "count": c} for n, c in kid_counter.most_common(5)]

    best_month = None
    if total_matched > 0:
        best_m = max(range(1, 13), key=lambda i: monthly[i]["matched"])
        best_month = {"month": MONTH_NAMES[best_m - 1], "count": monthly[best_m]["matched"]}

    dow_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_counter: Counter = Counter(r.timestamp.weekday() for r in matched_rows)
    most_active_dow = dow_names[dow_counter.most_common(1)[0][0]] if dow_counter else None

    return {
        "year": target_year,
        "total_scanned": total_scanned,
        "total_matched": total_matched,
        "match_rate": match_rate,
        "monthly_counts": monthly_counts,
        "top_groups": top_groups,
        "top_kids": top_kids,
        "best_month": best_month,
        "most_active_dow": most_active_dow,
    }


@router.get("/memory-book")
async def memory_book(year: int | None = None, month: int | None = None):
    """Return matched activity log entries grouped by month for the memory book."""
    db = _db.SessionLocal()
    try:
        query = db.query(ActivityLog).filter(ActivityLog.matched.is_(True))
        if year:
            query = query.filter(
                ActivityLog.timestamp >= datetime(year, 1, 1),
                ActivityLog.timestamp < datetime(year + 1, 1, 1),
            )
        if month:
            if not year:
                year = datetime.now().year
            next_month = month % 12 + 1
            next_year = year + 1 if month == 12 else year
            query = query.filter(
                ActivityLog.timestamp >= datetime(year, month, 1),
                ActivityLog.timestamp < datetime(next_year, next_month, 1),
            )
        rows = query.order_by(ActivityLog.timestamp.desc()).limit(500).all()
    finally:
        db.close()

    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        key = (r.timestamp.year, r.timestamp.month)
        groups[key].append({
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "photo_filename": r.photo_filename,
            "sender": r.sender,
            "group_name": r.group_name,
            "kid_names": r.kid_names or "",
            "confidence": r.confidence,
            "has_photo": bool(r.matched_photo_path and Path(r.matched_photo_path).exists()),
        })

    months_list = [
        {
            "year": y,
            "month": m,
            "label": f"{MONTH_NAMES[m - 1]} {y}",
            "entries": groups[(y, m)],
        }
        for (y, m) in sorted(groups.keys(), reverse=True)
    ]
    return {"months": months_list}


@router.get("/memory-book/photo/{activity_id}")
async def memory_book_photo(activity_id: int):
    """Serve the saved photo for a memory book entry."""
    db = _db.SessionLocal()
    try:
        row = db.query(ActivityLog).filter(ActivityLog.id == activity_id).first()
    finally:
        db.close()
    if not row or not row.matched_photo_path:
        return Response(status_code=404)
    p = Path(row.matched_photo_path)
    if not p.exists():
        return Response(status_code=404)
    return FileResponse(str(p), headers={"Cache-Control": "max-age=86400"})
