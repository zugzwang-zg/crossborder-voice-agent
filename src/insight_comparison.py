"""Deterministic comparison between two generated insight versions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class InsightChange:
    insight_id: str
    title: str
    previous_support: int
    current_support: int

    @property
    def delta(self) -> int:
        return self.current_support - self.previous_support


@dataclass(frozen=True)
class InsightVersionDiff:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[InsightChange, ...]


def _support(item: dict[str, Any]) -> int:
    if "support_count" in item:
        return int(item["support_count"])
    evidence = item.get("data_evidence", {})
    return int(evidence.get("support_reviews", 0))


def _index(items: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        insight_id = str(item.get("insight_id", "")).strip()
        if not insight_id:
            raise ValueError("every insight requires insight_id")
        if insight_id in result:
            raise ValueError(f"duplicate insight_id: {insight_id}")
        result[insight_id] = item
    return result


def compare_insight_versions(
    previous: Iterable[dict[str, Any]], current: Iterable[dict[str, Any]]
) -> InsightVersionDiff:
    """Return additions, removals and support changes in stable order."""
    before = _index(previous)
    after = _index(current)
    added = tuple(sorted(after.keys() - before.keys()))
    removed = tuple(sorted(before.keys() - after.keys()))
    changed: list[InsightChange] = []
    for insight_id in sorted(before.keys() & after.keys()):
        previous_support = _support(before[insight_id])
        current_support = _support(after[insight_id])
        if previous_support != current_support:
            changed.append(InsightChange(
                insight_id=insight_id,
                title=str(after[insight_id].get("title") or before[insight_id].get("title") or insight_id),
                previous_support=previous_support,
                current_support=current_support,
            ))
    return InsightVersionDiff(added=added, removed=removed, changed=tuple(changed))
