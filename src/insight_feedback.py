"""Append-only human feedback for generated insights.

Feedback deliberately lives outside model output files.  Each update is a new
JSONL event so reviewers can reconstruct the decision history without mutating
the evidence or recommendations that produced the insight.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid4


VALID_STATUSES = {"new", "needs_validation", "accepted", "rejected", "resolved"}
VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
VALID_FLAG_TYPES = {"label_error", "insufficient_evidence", "invalid_recommendation"}
VALID_EVENT_TYPES = {"decision_update", "quality_flag"}


@dataclass(frozen=True)
class FeedbackEvent:
    event_id: str
    insight_id: str
    event_type: str
    created_at: str
    actor: str
    status: str = "new"
    priority: str = "medium"
    owner: str = ""
    due_date: str = ""
    note: str = ""
    flag_type: str = ""


def _validate_date(value: str) -> None:
    if value:
        date.fromisoformat(value)


def create_feedback_event(
    insight_id: str,
    *,
    event_type: str,
    actor: str,
    status: str = "new",
    priority: str = "medium",
    owner: str = "",
    due_date: str = "",
    note: str = "",
    flag_type: str = "",
    event_id: str | None = None,
    created_at: str | None = None,
) -> FeedbackEvent:
    """Validate and create a feedback event ready for persistence."""
    if not insight_id.strip():
        raise ValueError("insight_id is required")
    if not actor.strip():
        raise ValueError("actor is required")
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(f"unsupported event_type: {event_type}")
    if status not in VALID_STATUSES:
        raise ValueError(f"unsupported status: {status}")
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"unsupported priority: {priority}")
    if event_type == "quality_flag" and flag_type not in VALID_FLAG_TYPES:
        raise ValueError("quality_flag requires a supported flag_type")
    if event_type == "decision_update" and flag_type:
        raise ValueError("decision_update cannot include flag_type")
    _validate_date(due_date)
    return FeedbackEvent(
        event_id=event_id or str(uuid4()),
        insight_id=insight_id.strip(),
        event_type=event_type,
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
        actor=actor.strip(),
        status=status,
        priority=priority,
        owner=owner.strip(),
        due_date=due_date,
        note=note.strip(),
        flag_type=flag_type,
    )


class FeedbackStore:
    """A small append-only JSONL repository for reviewer decisions."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, event: FeedbackEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=False, sort_keys=True))
            handle.write("\n")

    def events(self) -> list[FeedbackEvent]:
        if not self.path.exists():
            return []
        result: list[FeedbackEvent] = []
        with self.path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    result.append(FeedbackEvent(**json.loads(line)))
                except (TypeError, json.JSONDecodeError) as exc:
                    raise ValueError(f"invalid feedback event at line {line_number}") from exc
        return result

    def latest_by_insight(self) -> dict[str, FeedbackEvent]:
        latest: dict[str, FeedbackEvent] = {}
        for event in self.events():
            latest[event.insight_id] = event
        return latest

    def for_insight(self, insight_id: str) -> Iterable[FeedbackEvent]:
        return (event for event in self.events() if event.insight_id == insight_id)
