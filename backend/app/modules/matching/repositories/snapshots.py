from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from ..schemas.contracts import PublicPostInput
from ..services.scoring import ScoredPair


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
    def read(self, source_id: UUID) -> MatchSnapshot: ...


def fingerprint(record: PublicPostInput) -> str:
    return sha256(record.post.model_dump_json().encode()).hexdigest()
