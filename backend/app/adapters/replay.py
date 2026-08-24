from __future__ import annotations

import builtins
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas import NormalizedInput
from app.services.reply_context import enrich_reply_context


class ReplayAdapter:
    def __init__(self, fixture_dir: Path):
        self.fixture_dir = fixture_dir.resolve()

    def list(self) -> list[dict[str, Any]]:
        fixtures = []
        for path in sorted(self.fixture_dir.glob("*.json")):
            data = json.loads(path.read_text())
            fixtures.append(
                {
                    key: data[key]
                    for key in ("fixture_name", "description", "content_origin", "expected_outcome")
                }
            )
        return fixtures

    def load(self, name: str) -> tuple[dict[str, Any], builtins.list[NormalizedInput]]:
        path = (self.fixture_dir / f"{name}.json").resolve()
        if path.parent != self.fixture_dir or not path.exists():
            raise FileNotFoundError(name)
        data = json.loads(path.read_text())
        received = datetime.now(timezone.utc)
        events = [
            NormalizedInput(
                source="replay",
                source_event_id=item["source_event_id"],
                post_id=item["post_id"],
                comment_id=item["comment_id"],
                parent_id=item.get("parent_id"),
                raw_author_identifier=item["author"],
                occurred_at=item["occurred_at"],
                received_at=received,
                text=item["text"],
                manual_content_review_score=item.get("manual_content_review_score"),
                metadata={"fixture_label": name, **item.get("metadata", {})},
            )
            for item in data["events"]
        ]
        return data, enrich_reply_context(events)
