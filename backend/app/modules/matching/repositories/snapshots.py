"""Adapter seam for Posts and completed match generations.

Production adapters must provide an atomic read of current Posts and generation.
The memory implementation is for tests/demo, never a substitute for PostgreSQL.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Protocol
from uuid import UUID

from ..schemas.contracts import PublicPostInput
from ..services.scoring import RULE_VERSION, ScoredPair, eligible, rank_candidates


@dataclass(frozen=True)
class Generation:
    source_id: UUID
    rule_version: str
    calculated_at: datetime
    inputs: dict[UUID, str]
    pairs: tuple[ScoredPair, ...]


@dataclass(frozen=True)
class MatchSnapshot:
    posts: dict[UUID, PublicPostInput]
    generation: Generation | None


class SnapshotReader(Protocol):
    def read(self, source_id: UUID) -> MatchSnapshot:
        """Read a consistent, detached snapshot; raise OSError if unavailable."""
        ...


class UnavailableReader:
    def read(self, source_id: UUID) -> MatchSnapshot:
        raise OSError("Posts adapter has not been configured")


def fingerprint(record: PublicPostInput) -> str:
    # Full public projection catches content and policy-visible mapping changes.
    return record.post.model_dump_json()


class MemoryMatchingStore:
    def __init__(self, posts: list[PublicPostInput] = ()):
        self._lock = RLock()
        self._posts = {item.post.id: item.model_copy(deep=True) for item in posts}
        self._generations: dict[UUID, Generation] = {}

    def put(self, record: PublicPostInput) -> None:
        with self._lock:
            self._posts[record.post.id] = record.model_copy(deep=True)

    def recalculate(self, source_id: UUID) -> Generation:
        """Explicit operation, never called by GET. Atomic in this demo adapter."""
        with self._lock:
            source = self._posts[source_id]
            if not eligible(source):
                raise ValueError("Source is not matchable")
            candidates = [item for item in self._posts.values() if eligible(item) and item.post.type != source.post.type]
            inputs = {item.post.id: fingerprint(item) for item in [source, *candidates]}
            generation = Generation(source_id, RULE_VERSION, datetime.now(timezone.utc), inputs,
                                    tuple(rank_candidates(source, candidates)))
            self._generations[source_id] = generation
            return deepcopy(generation)

    def read(self, source_id: UUID) -> MatchSnapshot:
        with self._lock:
            return deepcopy(MatchSnapshot(self._posts, self._generations.get(source_id)))
