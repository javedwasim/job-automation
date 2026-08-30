"""LinkedIn job-alert parser (spec section 11).

Platform-specific knowledge ONLY — how LinkedIn structures its alert
emails: inline "Title at Company - Location" lines, /jobs/view/<id> links,
optional "Promoted" badges. Multi-job segmentation, field reading, date
resolution, URL canonicalization, job-ID extraction and defaults are all
inherited from BaseJobAlertParser and the centralized services (spec
section 14). Promoted jobs are flagged, never auto-rejected — their actual
job_posted_at decides freshness (spec section 11).
"""

from app.gmail.dto import NormalizedEmail
from app.job_alerts.dto.normalized_job import NormalizedJob
from app.job_alerts.parsers.base_parser import BaseJobAlertParser


class LinkedInParser(BaseJobAlertParser):
    slug = "linkedin"

    def supports(self, email: NormalizedEmail) -> bool:
        return "linkedin.com" in email.sender.lower()

    def parse_jobs(self, email: NormalizedEmail) -> list[NormalizedJob]:
        """EVERY job card in the email becomes one candidate (spec sections
        3, 9) — a digest with 8 jobs yields 8 candidates."""
        jobs: list[NormalizedJob] = []
        for block, link in self._job_blocks(email):
            fields = self._fields_from_block(block)
            if fields.title is None:
                # No job-like content in this block — never fabricate a
                # pseudo-job from header/footer noise.
                continue
            jobs.append(self._candidate(fields, link, email))
        return jobs

