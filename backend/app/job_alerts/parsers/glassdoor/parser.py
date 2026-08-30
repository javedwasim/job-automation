"""Glassdoor job-alert parser (spec section 13, added per section 43 —
new platforms are additive parser modules, never pipeline edits).

Platform-specific knowledge ONLY — Glassdoor digest emails list one job
per block ("Title at Company", location/remote line, salary, relative
date, "Easy Apply") with /job-listing/_JO<id>.htm links (often behind
Glassdoor email-redirects). Everything else — segmentation, field
vocabulary, date resolution, URL canonicalization, _JO job-ID extraction,
defaults — is inherited from BaseJobAlertParser and the centralized
services. Never assumes one job per email.
"""

from app.gmail.dto import NormalizedEmail
from app.job_alerts.dto.normalized_job import NormalizedJob
from app.job_alerts.parsers.base_parser import BaseJobAlertParser


class GlassdoorParser(BaseJobAlertParser):
    slug = "glassdoor"

    def supports(self, email: NormalizedEmail) -> bool:
        return "glassdoor.com" in email.sender.lower()

    def parse_jobs(self, email: NormalizedEmail) -> list[NormalizedJob]:
        """EVERY job block in the email becomes one candidate (spec sections
        3, 9) — a digest with 6 jobs yields 6 candidates. Glassdoor also
        sends review/salary/interview digests; blocks without job-like
        content produce no candidate (no pseudo-jobs)."""
        jobs: list[NormalizedJob] = []
        for block, link in self._job_blocks(email):
            fields = self._fields_from_block(block)
            if fields.title is None:
                # No job-like content in this block — never fabricate a
                # pseudo-job from header/footer noise.
                continue
            jobs.append(self._candidate(fields, link, email))
        return jobs
