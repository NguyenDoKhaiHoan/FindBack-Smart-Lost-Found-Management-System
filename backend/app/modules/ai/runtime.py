from collections import OrderedDict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import BoundedSemaphore, Lock
from time import monotonic
from uuid import UUID, uuid4

from openai import (
    APIError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

from app.core.config import Settings
from app.shared.errors import DomainError


@dataclass
class Conversation:
    owner: str
    touched_at: float
    busy: bool = False
    history: deque[dict[str, str]] = field(default_factory=lambda: deque(maxlen=6))
    recent_results: dict[UUID, tuple[str, ...]] = field(default_factory=dict)


class AIRuntime:
    """Limits and conversation state shared within one local worker."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.lock = Lock()
        self.model_lock = Lock()
        self.model_slots = BoundedSemaphore(2)
        self.rates: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self.conversations: OrderedDict[UUID, Conversation] = OrderedDict()
        self.openai: OpenAI | None = None
        self.text_model = None
        self.image_model = None
        self.image_prototypes: dict[str, list[float]] = {}

    def require_enabled(self, feature: str) -> None:
        if not getattr(self.settings, f"ai_{feature}_enabled"):
            raise DomainError(503, "AI_DISABLED", "This AI feature is disabled")

    def throttle(self, feature: str, actor: str) -> None:
        with self.lock:
            now = monotonic()
            windows = []
            for key, limit in (
                ((feature, "all"), self.settings.ai_global_requests_per_minute),
                ((feature, actor), self.settings.ai_requests_per_minute),
            ):
                window = self.rates.setdefault(key, deque())
                self.rates.move_to_end(key)
                while window and window[0] <= now - 60:
                    window.popleft()
                if len(window) >= limit:
                    raise DomainError(429, "AI_RATE_LIMIT", "Try again in a minute")
                windows.append(window)
            for window in windows:
                window.append(now)
            while len(self.rates) > 1024:
                self.rates.popitem(last=False)

    @contextmanager
    def inference(self):
        if not self.model_slots.acquire(blocking=False):
            raise DomainError(503, "AI_BUSY", "The local AI models are busy")
        try:
            if not self.model_lock.acquire(timeout=15):
                raise DomainError(503, "AI_BUSY", "The local AI models are busy")
            try:
                yield
            finally:
                self.model_lock.release()
        finally:
            self.model_slots.release()

    @contextmanager
    def conversation(self, conversation_id: UUID | None, owner: str):
        with self.lock:
            now = monotonic()
            if conversation_id is None:
                if len(self.conversations) >= 256:
                    oldest = next(
                        (key for key, value in self.conversations.items() if not value.busy), None
                    )
                    if oldest is None:
                        raise DomainError(503, "AI_BUSY", "The assistant is busy")
                    del self.conversations[oldest]
                conversation_id = uuid4()
                conversation = Conversation(owner, now)
                self.conversations[conversation_id] = conversation
            else:
                conversation = self.conversations.get(conversation_id)
                if (
                    conversation is None
                    or conversation.owner != owner
                    or now - conversation.touched_at > 1800
                ):
                    raise DomainError(404, "AI_CONVERSATION_NOT_FOUND", "Conversation not found")
            if conversation.busy:
                raise DomainError(409, "AI_BUSY", "This conversation is busy")
            conversation.busy = True
            self.conversations.move_to_end(conversation_id)

        try:
            yield conversation_id, conversation
        finally:
            with self.lock:
                conversation.touched_at = monotonic()
                conversation.busy = False

    def openai_model(self, task: str) -> str:
        model = getattr(self.settings, f"openai_{task}_model").strip()
        key = self.settings.openai_api_key
        if not (key and key.get_secret_value().strip() and model):
            raise DomainError(503, "AI_NOT_CONFIGURED", "Configure the OpenAI key and model")
        return model

    def responses(self, task: str, **kwargs):
        model = self.openai_model(task)
        with self.lock:
            if self.openai is None:
                self.openai = OpenAI(
                    api_key=self.settings.openai_api_key.get_secret_value().strip(),
                    timeout=self.settings.openai_timeout_seconds,
                    max_retries=0,
                )
        try:
            return self.openai.responses.create(model=model, store=False, **kwargs)
        except APITimeoutError:
            raise DomainError(504, "AI_TIMEOUT", "OpenAI did not respond in time") from None
        except RateLimitError:
            raise DomainError(429, "AI_RATE_LIMIT", "OpenAI rate limit reached") from None
        except (AuthenticationError, PermissionDeniedError):
            raise DomainError(503, "AI_NOT_CONFIGURED", "Check OpenAI configuration") from None
        except APIError:
            raise DomainError(502, "AI_PROVIDER_ERROR", "OpenAI request failed") from None
