from __future__ import annotations

import asyncio
import hmac
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.offline import MAX_OFFLINE_BYTES, OfflineDatasetAdapter, OfflineDatasetError
from app.adapters.replay import ReplayAdapter
from app.config import Settings, get_settings
from app.db import SessionLocal, get_db
from app.models import Alert, ContentReview, DetectionSetting, Event, Post, ReplayRun
from app.schemas import AlertPatch, ReplayRequest, ReviewRequest, SettingsUpdate
from app.services.coordination_graph import build_coordination_graph
from app.services.crypto import decrypt_text, display_pseudonym
from app.services.evidence import build_evidence_zip
from app.services.ingestion import IngestionService, purge_all
from app.services.retention import purge_expired
from app.services.semantic_context import prepare_semantic_context

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
        "content_review_evidence": alert.content_review_evidence,
        "priority": alert.priority,
        "confidence": alert.confidence,
        "features": alert.features,
        "explanations": alert.explanations,
        "event_ids": alert.event_ids,
        "status": alert.status,
        "resolution": alert.resolution,
        "reviewer_note": alert.reviewer_note,
    }


def public_content_signal(event: Event) -> dict[str, Any] | None:
    if not isinstance(event.event_metadata, dict):
        return None
    signal = event.event_metadata.get("experimental_content_signal")
    if not isinstance(signal, dict):
        return None
    allowed = {
        "source",
        "status",
        "score",
        "category",
        "requires_review",
        "context_score",
        "model_id",
        "model_revision",
        "threshold",
        "reason",
    }
    result = {key: signal[key] for key in allowed if key in signal}
    label_scores = signal.get("label_scores")
    if isinstance(label_scores, dict):
        result["label_scores"] = {
            str(label)[:80]: float(value)
            for label, value in list(label_scores.items())[:20]
            if isinstance(value, (int, float))
        }
    return result


def public_semantic_context(event: Event) -> dict[str, Any] | None:
    if not isinstance(event.event_metadata, dict):
        return None
    context = event.event_metadata.get("semantic_context")
    if not isinstance(context, dict):
        return None
    allowed = {
        "source",
        "status",
        "model_id",
        "model_revision",
        "threshold",
        "time_window_seconds",
        "neighbor_count",
        "reason",
    }
    result = {key: context[key] for key in allowed if key in context}
    neighbors = context.get("neighbors")
    if isinstance(neighbors, list):
        safe_neighbors = [item for item in neighbors if isinstance(item, dict)]
        similarities = [
            float(item["similarity"])
            for item in safe_neighbors
            if isinstance(item.get("similarity"), (int, float))
        ]
        timings = [
            float(item["seconds_apart"])
            for item in safe_neighbors
            if isinstance(item.get("seconds_apart"), (int, float))
        ]
        result.update(
            {
                "strongest_similarity": max(similarities, default=0.0),
                "closest_timing_seconds": min(timings, default=None),
                "shared_parent_match_count": sum(
                    item.get("shared_parent") is True for item in safe_neighbors
                ),
            }
        )
    return result


@app.get("/api/v1/health")
def health(
    db: Session = Depends(get_db), config: Settings = Depends(get_settings)
) -> dict[str, Any]:
    ready = True
    try:
        db.execute(select(1))
    except Exception:
        ready = False
    return {
        "status": "ok" if ready else "degraded",
        "database_ready": ready,
        "mode": "offline",
        "offline_import_ready": ready,
        "raw_text_storage": config.store_raw_text,
        "content_detector_enabled": config.content_detector_enabled,
        "content_detector_model": (
            config.content_detector_model if config.content_detector_enabled else None
        ),
        "semantic_context_enabled": config.semantic_context_enabled,
        "semantic_context_model": (
            config.semantic_context_model if config.semantic_context_enabled else None
        ),
        "version": "0.1.0",
    }


@app.post("/api/v1/offline/import", dependencies=[Depends(admin)])
async def import_offline_dataset(
    file: UploadFile = File(...),
    reset_before_import: bool = Query(False),
    db: Session = Depends(get_db),
    config: Settings = Depends(get_settings),
) -> dict[str, Any]:
    if file.filename and not file.filename.lower().endswith(".json"):
        raise HTTPException(415, "Offline dataset must be a JSON file")
    try:
        raw = await file.read(MAX_OFFLINE_BYTES + 1)
    finally:
        await file.close()
    try:
        metadata, events = OfflineDatasetAdapter().load_bytes(raw)
    except OfflineDatasetError as exc:
        raise HTTPException(422, str(exc)) from exc
    events = prepare_semantic_context(events, config)

    if reset_before_import:
        purge_all(db)
    service = IngestionService(db, config)
    created_events = 0
    duplicate_events = 0
    post_ids: set[str] = set()
    alert_ids: set[str] = set()
    for item in events:
        event, created, alert = service.ingest(item)
        created_events += int(created)
        duplicate_events += int(not created)
        post_ids.add(event.post_id)
        if alert:
            alert_ids.add(alert.id)
    return {
        **metadata,
        "created_events": created_events,
        "duplicate_events": duplicate_events,
        "result_post_ids": sorted(post_ids),
        "result_alert_ids": sorted(alert_ids),
    }


@app.get("/api/v1/fixtures")
def fixtures(config: Settings = Depends(get_settings)) -> list[dict[str, Any]]:
    return ReplayAdapter(config.fixture_dir).list()


def run_replay(replay_id: str, fixture: str, speed: float) -> None:
    config = get_settings()
    adapter = ReplayAdapter(config.fixture_dir)
    _, events = adapter.load(fixture)
    events = prepare_semantic_context(events, config)
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


@app.get("/api/v1/posts/{post_id}/coordination-graph")
def coordination_graph(
    post_id: str, limit: int = Query(100, ge=2, le=200), db: Session = Depends(get_db)
) -> dict[str, Any]:
    if db.get(Post, post_id) is None:
        raise HTTPException(404, "Post not found")
    events = list(
        db.scalars(select(Event).where(Event.post_id == post_id).order_by(Event.occurred_at))
    )
    return build_coordination_graph(events, max_participants=limit)


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
            "content_signal": public_content_signal(event),
            "semantic_context": public_semantic_context(event),
            "reply_context": (
                event.event_metadata.get("reply_context")
                if isinstance(event.event_metadata, dict)
                else None
            ),
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
    prior_model = None
    if alert.content_review_evidence:
        prior_model = alert.content_review_evidence.get("experimental_local_model")
    alert.content_review_evidence = {
        "current": {
            "source": "human_review",
            "score": request.score,
            "category": request.category,
            "status": "review_required" if request.score >= 0.5 else "no_concern",
        },
        "experimental_local_model": prior_model,
    }
    alert.priority = (
        "high"
        if alert.coordination_score >= settings.alert_threshold and request.score >= 0.5
        else "medium"
    )
    db.commit()
    return serialize_alert(alert)


@app.post("/api/v1/alerts/{alert_id}/export", dependencies=[Depends(admin)])
def export(
    alert_id: str,
    db: Session = Depends(get_db),
    config: Settings = Depends(get_settings),
) -> Response:
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(404, "Alert not found")
    return Response(
        build_evidence_zip(db, alert, config.data_encryption_key if config.store_raw_text else ""),
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
