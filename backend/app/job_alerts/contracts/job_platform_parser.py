"""JobPlatformParser contract (spec section 6). Every platform parser must
satisfy this Protocol so the ParserRegistry can treat them uniformly."""

from typing import Protocol

from app.gmail.dto import NormalizedEmail
from app.job_alerts.dto.normalized_job import NormalizedJob


class JobPlatformParser(Protocol):
    slug: str

    def supports(self, email: NormalizedEmail) -> bool:
        """Returns True if this parser can handle the given email."""
        ...

    def parse(self, email: NormalizedEmail) -> list[NormalizedJob]:
        """Extracts zero or more jobs from a single job-alert email."""
        ...
