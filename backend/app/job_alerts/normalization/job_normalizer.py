"""JobNormalizer (spec sections 2, 15) — centralized normalization +
validation of every NormalizedJob candidate, platform-independent.

This is the single place where a job candidate gets its canonical form:
text fields cleaned, URL canonicalized, platform job ID extracted,
posting date resolved from the raw relative phrase. A candidate that
cannot be validated (no usable title, no identity anchor, a URL that is
not a job URL) is rejected with an explicit reason — never half-fixed and
persisted. A job URL is necessary but NEVER sufficient: a candidate built
from a live link plus arbitrary surrounding text is still not a job.
"""

import re
from dataclasses import dataclass
from html import unescape

from app.job_alerts.dto.normalized_job import NormalizedJob
from app.job_alerts.extraction.job_posted_date_extractor import JobPostedDateExtractor
from app.job_alerts.extraction.url_extractor import is_supported_job_url
from app.job_alerts.extraction.url_normalizer import JobUrlNormalizer

_WHITESPACE_RE = re.compile(r"\s+")
_MAX_FIELD_LENGTH = 255
_MAX_URL_LENGTH = 2048


@dataclass(frozen=True)
class RejectedJob:
    """A candidate dropped during normalization, with the explicit reason."""

    job: NormalizedJob
    reason: str


class JobNormalizer:
    def __init__(
        self,
        url_normalizer: JobUrlNormalizer | None = None,
        date_extractor: JobPostedDateExtractor | None = None,
    ) -> None:
        self._urls = url_normalizer or JobUrlNormalizer()
        self._dates = date_extractor or JobPostedDateExtractor()

    def normalize_all(
        self, jobs: list[NormalizedJob], *, platform: str | None = None
    ) -> tuple[list[NormalizedJob], list[RejectedJob]]:
        """Normalizes every candidate; returns (kept, rejected) so the
        pipeline can record an explicit processing event per rejection."""
        kept: list[NormalizedJob] = []
        rejected: list[RejectedJob] = []
        for job in jobs:
            normalized = self.normalize(job, platform=platform)
            if normalized is None:
                rejected.append(RejectedJob(job=job, reason=self._rejection_reason(job)))
            else:
                kept.append(normalized)
        return kept, rejected

    def normalize(
        self, job: NormalizedJob, *, platform: str | None = None
    ) -> NormalizedJob | None:
        """Returns the canonical NormalizedJob, or None when the candidate
        fails validation (missing title, no identity anchor)."""
        if not self.is_valid(job):
            return None

        source = platform or job.source
        job_url = job.job_url
        if job_url:
            job_url = self._urls.canonical(job_url, source)[:_MAX_URL_LENGTH]

        platform_job_id = job.platform_job_id
        if platform_job_id is None and job_url:
            # Centralized job-ID extraction (spec section 8) — parsers never
            # reimplement per-platform ID regexes.
            platform_job_id = self._urls.extract_job_id(job_url, source)

        job_posted_at = job.job_posted_at
        if job_posted_at is None and job.posted_date:
            # Centralized date extraction — relative phrases resolve against
            # the email's received_at (spec section 4), never "now".
            job_posted_at = self._dates.extract(job.posted_date, job.received_at)

        return NormalizedJob(
            title=self._clean(job.title) or job.title,
            company=self._clean(job.company),
            location=self._clean(job.location),
            source=source or job.source,
            platform_job_id=platform_job_id,
            job_url=job_url or None,
            application_url=job.application_url,
            job_posted_at=job_posted_at,
            received_at=job.received_at,
            description=self._clean(job.description),
            source_email_id=job.source_email_id,
            remote_type=self._clean(job.remote_type),
            salary=self._clean(job.salary),
            employment_type=self._clean(job.employment_type),
            is_promoted=job.is_promoted,
            posted_date=job.posted_date,
        )

    def is_valid(self, job: NormalizedJob) -> bool:
        """A candidate is valid only when it carries RELIABLE job evidence:

          * a usable title (never a fragment / badge / location / date), and
          * an identity anchor — a job URL that is a supported job-posting
            URL (or carries a platform job ID), or a bare platform job ID.

        Missing company/location/salary/employment-type/posting date NEVER
        invalidates a candidate — those fields may legitimately be NULL.
        """
        if not self._is_reliable_title(job.title):
            return False
        if not job.job_url and not job.platform_job_id:
            return False
        if not job.received_at:
            return False

        url = (job.job_url or "").strip()
        if url and not job.platform_job_id:
            # A URL alone is not enough — it must carry a job identity: a
            # platform job ID, or at least a recognized job-posting URL.
            source = job.source
            has_id = self._urls.extract_job_id(url, source) is not None
            if not has_id and not is_supported_job_url(url):
                return False
        return True

    @staticmethod
    def _is_reliable_title(title: str | None) -> bool:
        """Rejects the garbage the old blocker used to mint as titles: blank
        strings, one/two-char fragments, punctuation-only lines and a lone
        short token without a space (e.g. "job", "ogy", "ved"). A real title
        is a noun phrase — usually several words; a legitimate single-word
        title (Engineer, Developer, Backend) is long enough to survive."""
        text = (title or "").strip()
        if not text:
            return False
        if len(text) < 3:
            return False
        if not any(ch.isalnum() for ch in text):
            return False
        if " " not in text and len(text) < 6:
            return False
        return True

    def _rejection_reason(self, job: NormalizedJob) -> str:
        text = (job.title or "").strip()
        if not text:
            return "missing title"
        if not self._is_reliable_title(text):
            return "title is not a reliable job title"
        if not job.job_url and not job.platform_job_id:
            return "no job URL or platform job id"
        url = (job.job_url or "").strip()
        if url and not job.platform_job_id:
            has_id = self._urls.extract_job_id(url, job.source) is not None
            if not has_id and not is_supported_job_url(url):
                return "URL is not a supported job URL"
        return "missing received_at"

    def _clean(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = _WHITESPACE_RE.sub(" ", unescape(value)).strip()
        if not cleaned:
            return None
        return cleaned[:_MAX_FIELD_LENGTH]
