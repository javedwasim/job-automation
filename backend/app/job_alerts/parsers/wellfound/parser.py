"""Wellfound job-alert parser (added per spec section 43 — new platforms
are additive parser modules, never pipeline edits).

Platform-specific knowledge ONLY — Wellfound digest emails list one job
per block (title, company, salary/equity) with /job-listings/<slug> links.
Segmentation, field vocabulary, date resolution, URL canonicalization and
defaults are inherited from BaseJobAlertParser and the centralized
services. Wellfound alerts rarely state a posting date, so job_posted_at
stays NULL per the explicit unknown-date policy (spec section 7) — never
defaulted to received_at.
"""

from app.gmail.dto import NormalizedEmail
from app.job_alerts.dto.normalized_job import NormalizedJob
from app.job_alerts.parsers.base_parser import BaseJobAlertParser


class WellfoundParser(BaseJobAlertParser):
    slug = "wellfound"

    def supports(self, email: NormalizedEmail) -> bool:
        return "wellfound.com" in email.sender.lower()

    def parse_jobs(self, email: NormalizedEmail) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for block, link in self._job_blocks(email):
            fields = self._fields_from_block(block)
            if fields.title is None:
                # No job-like content in this block — no pseudo-jobs.
                continue
            jobs.append(self._candidate(fields, link, email))
        return jobs

