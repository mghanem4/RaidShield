from __future__ import annotations

import asyncio
import hmac
import json
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.instagram import InstagramWebhookAdapter, verify_signature
from app.adapters.replay import ReplayAdapter
from app.config import Settings, get_settings
from app.db import SessionLocal, get_db
from app.models import Alert, ContentReview, DetectionSetting, Event, Post, ReplayRun
from app.schemas import AlertPatch, ReplayRequest, ReviewRequest, SettingsUpdate
from app.services.crypto import decrypt_text, display_pseudonym
from app.services.evidence import build_evidence_zip
from app.services.ingestion import IngestionService, purge_all
from app.services.retention import purge_expired

app = FastAPI(title="RaidShield API", version="0.1.0")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(HTTPException)
async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": f"http_{exc.status_code}", "message": exc.detail}},
    )


def admin(
    authorization: Annotated[str | None, Header()] = None, config: Settings = Depends(get_settings)
) -> None:
    supplied = authorization.removeprefix("Bearer ") if authorization else ""
    if not config.admin_token or not hmac.compare_digest(supplied, config.admin_token):
        raise HTTPException(401, "Administrator token required")


def serialize_post(db: Session, post: Post) -> dict[str, Any]:
    alerts = db.scalar(select(func.count()).select_from(Alert).where(Alert.post_id == post.id)) or 0
    return {
        "id": post.id,
        "source": post.source,
        "source_post_id": post.source_post_id,
        "display_label": post.display_label,
        "first_observed_at": post.first_observed_at,
        "last_event_at": post.last_event_at,
        "comment_count": post.comment_count,
        "reply_count": post.reply_count,
        "alert_count": alerts,
        "monitoring_status": post.monitoring_status,
    }


def serialize_alert(alert: Alert) -> dict[str, Any]:
    return {
        "id": alert.id,
        "post_id": alert.post_id,
        "parent_thread_id": alert.parent_thread_id,
        "created_at": alert.created_at,
        "window_start": alert.window_start,
        "window_end": alert.window_end,
        "coordination_score": alert.coordination_score,
        "content_review_score": alert.content_review_score,
        "priority": alert.priority,
        "confidence": alert.confidence,
        "features": alert.features,
        "explanations": alert.explanations,
        "event_ids": alert.event_ids,
        "status": alert.status,
        "resolution": alert.resolution,
        "reviewer_note": alert.reviewer_note,
    }


@app.get("/api/v1/health")
def health(
    db: Session = Depends(get_db), config: Settings = Depends(get_settings)
) -> dict[str, Any]:
    ready = True
    try:
        db.execute(select(1))
    except Exception:
        ready = False
    configured = bool(config.meta_verify_token and config.meta_app_secret)
    return {
        "status": "ok" if ready else "degraded",
        "database_ready": ready,
        "mode": "instagram" if configured else "replay",
        "meta_configured": configured,
        "raw_text_storage": config.store_raw_text,
        "version": "0.1.0",
    }


@app.get("/api/v1/fixtures")
def fixtures(config: Settings = Depends(get_settings)) -> list[dict[str, Any]]:
    return ReplayAdapter(config.fixture_dir).list()


def run_replay(replay_id: str, fixture: str, speed: float) -> None:
    config = get_settings()
    adapter = ReplayAdapter(config.fixture_dir)
    _, events = adapter.load(fixture)
    with SessionLocal() as db:
        run = db.get(ReplayRun, replay_id)
        if not run:
            return
        run.status = "running"
        db.commit()
        first_time = events[0].occurred_at if events else None
        prior_offset = 0.0
        for item in events:
            if speed > 0 and first_time:
                offset = (item.occurred_at - first_time).total_seconds() / speed
                asyncio.run(asyncio.sleep(max(0, offset - prior_offset)))
                prior_offset = offset
            event, _, alert = IngestionService(db, config).ingest(item)
            run = db.get(ReplayRun, replay_id)
            if run:
                run.processed_events += 1
                run.result_post_id = event.post_id
                run.result_alert_id = alert.id if alert else run.result_alert_id
                db.commit()
        run = db.get(ReplayRun, replay_id)
        if run:
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()


@app.post("/api/v1/replay", dependencies=[Depends(admin)])
def replay(
    request: ReplayRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    config: Settings = Depends(get_settings),
) -> dict[str, Any]:
    try:
        _, events = ReplayAdapter(config.fixture_dir).load(request.fixture)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Fixture not found") from exc
    if request.reset_before_replay:
        purge_all(db)
    run = ReplayRun(
        fixture=request.fixture,
        status="queued",
        total_events=len(events),
        processed_events=0,
        created_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    if request.speed == 0:
        run_replay(run.id, request.fixture, 0)
        db.refresh(run)
    else:
        background.add_task(run_replay, run.id, request.fixture, request.speed)
    return replay_status(run.id, db)


@app.get("/api/v1/replay/{replay_id}")
def replay_status(replay_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    run = db.get(ReplayRun, replay_id)
    if not run:
        raise HTTPException(404, "Replay not found")
    return {
        "id": run.id,
        "fixture": run.fixture,
        "status": run.status,
        "total_events": run.total_events,
        "processed_events": run.processed_events,
        "result_post_id": run.result_post_id,
        "result_alert_id": run.result_alert_id,
    }


@app.get("/api/v1/posts")
def posts(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [
        serialize_post(db, post)
        for post in db.scalars(select(Post).order_by(Post.last_event_at.desc()).limit(100))
    ]


@app.get("/api/v1/posts/{post_id}")
def post_detail(post_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    result = serialize_post(db, post)
    authors = db.scalar(
        select(func.count(func.distinct(Event.author_pseudonym))).where(Event.post_id == post.id)
    )
    result["unique_participants"] = authors or 0
    result["alerts"] = [
        serialize_alert(a)
        for a in db.scalars(
            select(Alert).where(Alert.post_id == post.id).order_by(Alert.created_at.desc())
        )
    ]
    return result


@app.get("/api/v1/posts/{post_id}/timeline")
def timeline(
    post_id: str, minutes: int = Query(15, ge=1, le=1440), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    events = list(
        db.scalars(select(Event).where(Event.post_id == post_id).order_by(Event.occurred_at))
    )
    buckets: dict[str, int] = {}
    for event in events:
        key = event.occurred_at.replace(second=0, microsecond=0).isoformat()
        buckets[key] = buckets.get(key, 0) + 1
    return [{"timestamp": key, "count": value} for key, value in sorted(buckets.items())][-minutes:]


@app.get("/api/v1/posts/{post_id}/threads")
def threads(
    post_id: str,
    include_content: bool = False,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
    config: Settings = Depends(get_settings),
) -> dict[str, Any]:
    if include_content:
        admin(authorization, config)
    events = list(
        db.scalars(select(Event).where(Event.post_id == post_id).order_by(Event.occurred_at))
    )
    by_comment = {event.comment_id: event for event in events}
    roots: dict[str, dict[str, Any]] = {}
    unknown: list[dict[str, Any]] = []

    def public(event: Event) -> dict[str, Any]:
        content = "content hidden"
        if include_content and event.encrypted_text and config.data_encryption_key:
            content = decrypt_text(event.encrypted_text, config.data_encryption_key)
        return {
            "id": event.id,
            "comment_id": event.comment_id,
            "parent_id": event.parent_id,
            "participant": display_pseudonym(event.author_pseudonym),
            "occurred_at": event.occurred_at,
            "content": content,
        }

    for event in events:
        if event.parent_id is None:
            roots[event.comment_id] = {**public(event), "replies": []}
    for event in events:
        if event.parent_id:
            if event.parent_id in roots:
                roots[event.parent_id]["replies"].append(public(event))
            elif event.parent_id in by_comment:
                grand_parent = by_comment[event.parent_id].parent_id
                if grand_parent is not None and grand_parent in roots:
                    roots[grand_parent]["replies"].append(public(event))
                else:
                    unknown.append(public(event))
            else:
                unknown.append(public(event))
    return {
        "threads": sorted(roots.values(), key=lambda x: len(x["replies"]), reverse=True),
        "unknown_parent_replies": unknown,
    }


@app.get("/api/v1/alerts")
def alerts(
    status: str | None = None,
    priority: str | None = None,
    post_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    query = select(Alert)
    if status:
        query = query.where(Alert.status == status)
    if priority:
        query = query.where(Alert.priority == priority)
    if post_id:
        query = query.where(Alert.post_id == post_id)
    return [
        serialize_alert(alert)
        for alert in db.scalars(query.order_by(Alert.created_at.desc()).limit(100))
    ]


@app.get("/api/v1/alerts/{alert_id}")
def alert_detail(alert_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    result = serialize_alert(alert)
    result["reviews"] = [
        {
            "score": r.score,
            "category": r.category,
            "reviewer_note": r.reviewer_note,
            "reviewed_at": r.reviewed_at,
        }
        for r in alert.reviews
    ]
    return result


@app.patch("/api/v1/alerts/{alert_id}", dependencies=[Depends(admin)])
def update_alert(alert_id: str, patch: AlertPatch, db: Session = Depends(get_db)) -> dict[str, Any]:
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.status, alert.resolution, alert.reviewer_note = (
        patch.status,
        patch.resolution,
        patch.reviewer_note,
    )
    db.commit()
    return serialize_alert(alert)


@app.post("/api/v1/alerts/{alert_id}/content-review", dependencies=[Depends(admin)])
def add_review(
    alert_id: str, request: ReviewRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    review = ContentReview(
        alert_id=alert.id,
        score=request.score,
        category=request.category,
        reviewer_note=request.reviewer_note,
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(review)
    alert.content_review_score = request.score
    alert.priority = (
        "high"
        if alert.coordination_score >= settings.alert_threshold and request.score >= 0.5
        else "medium"
    )
    db.commit()
    return serialize_alert(alert)


@app.post("/api/v1/alerts/{alert_id}/export", dependencies=[Depends(admin)])
def export(alert_id: str, db: Session = Depends(get_db)) -> Response:
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    return Response(
        build_evidence_zip(db, alert),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="raidshield-{alert.id}.zip"'},
    )


def settings_payload(config: Settings) -> dict[str, Any]:
    return {
        "alert_threshold": config.alert_threshold,
        "minimum_unique_authors": config.minimum_unique_authors,
        "similarity_threshold": config.similarity_threshold,
        "cold_start_threshold": config.cold_start_unique_author_threshold,
        "raw_text_retention_hours": config.raw_text_retention_hours,
        "aggregate_retention_days": config.aggregate_retention_days,
        "store_raw_text": config.store_raw_text,
    }


@app.get("/api/v1/settings/detection")
def detection_settings(config: Settings = Depends(get_settings)) -> dict[str, Any]:
    return settings_payload(config)


@app.put("/api/v1/settings/detection", dependencies=[Depends(admin)])
def update_settings(
    update: SettingsUpdate, db: Session = Depends(get_db), config: Settings = Depends(get_settings)
) -> dict[str, Any]:
    if update.store_raw_text and not config.data_encryption_key:
        raise HTTPException(422, "Configure DATA_ENCRYPTION_KEY before enabling raw-text storage")
    config.alert_threshold = update.alert_threshold
    config.minimum_unique_authors = update.minimum_unique_authors
    config.similarity_threshold = update.similarity_threshold
    config.cold_start_unique_author_threshold = update.cold_start_threshold
    config.raw_text_retention_hours = update.raw_text_retention_hours
    config.aggregate_retention_days = update.aggregate_retention_days
    config.store_raw_text = update.store_raw_text
    row = db.get(DetectionSetting, 1) or DetectionSetting(id=1)
    for key, value in update.model_dump().items():
        setattr(row, key, value)
    db.add(row)
    db.commit()
    return settings_payload(config)


@app.post("/api/v1/admin/purge-expired", dependencies=[Depends(admin)])
def purge(
    db: Session = Depends(get_db), config: Settings = Depends(get_settings)
) -> dict[str, int]:
    return purge_expired(db, config.raw_text_retention_hours, config.aggregate_retention_days)


@app.delete("/api/v1/admin/data", dependencies=[Depends(admin)])
def delete_data(confirmation: str = Query(...), db: Session = Depends(get_db)) -> dict[str, int]:
    if confirmation != "DELETE LOCAL RAIDSHIELD DATA":
        raise HTTPException(422, "Exact confirmation string required")
    counts = {
        "events": db.scalar(select(func.count()).select_from(Event)) or 0,
        "alerts": db.scalar(select(func.count()).select_from(Alert)) or 0,
        "posts": db.scalar(select(func.count()).select_from(Post)) or 0,
    }
    purge_all(db)
    return counts


@app.get("/webhooks/instagram")
def verify_webhook(request: Request, config: Settings = Depends(get_settings)) -> Response:
    token = request.query_params.get("hub.verify_token", "")
    challenge = request.query_params.get("hub.challenge", "")
    mode = request.query_params.get("hub.mode", "")
    if (
        mode == "subscribe"
        and config.meta_verify_token
        and hmac.compare_digest(token, config.meta_verify_token)
    ):
        return Response(challenge, media_type="text/plain")
    raise HTTPException(403, "Webhook verification failed")


@app.post("/webhooks/instagram")
async def instagram_webhook(
    request: Request,
    background: BackgroundTasks,
    signature: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
    config: Settings = Depends(get_settings),
) -> dict[str, int]:
    body = await request.body()
    if len(body) > 1_000_000:
        raise HTTPException(413, "Webhook payload too large")
    if not verify_signature(body, signature, config.meta_app_secret):
        raise HTTPException(401, "Invalid webhook signature")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Invalid JSON payload") from exc
    events = InstagramWebhookAdapter().normalize(payload)

    def process() -> None:
        with SessionLocal() as db:
            service = IngestionService(db, config)
            for item in events:
                service.ingest(item)

    background.add_task(process)
    return {"accepted": len(events)}
