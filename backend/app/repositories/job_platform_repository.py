from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jobs.models.job_platform import JobPlatform


class JobPlatformRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_enabled(self) -> list[JobPlatform]:
        return list(
            self._db.scalars(
                select(JobPlatform)
                .where(JobPlatform.enabled.is_(True))
                .order_by(JobPlatform.priority)
            )
        )

    def enabled_domains(self) -> list[str]:
        return [p.domain for p in self.list_enabled()]

    def detect_by_sender(self, sender: str) -> JobPlatform | None:
        """Naive domain match against the sender header — good enough for
        Phase 1's ingestion-level tagging. Real per-email-format platform
        detection is Phase 2's PlatformDetector."""
        sender_lower = sender.lower()
        for platform in self.list_enabled():
            if platform.domain.lower() in sender_lower:
                return platform
        return None
