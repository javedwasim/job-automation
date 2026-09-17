"""Indeed job-alert parser (spec section 12).

Platform-specific knowledge ONLY — Indeed digest emails list one job per
block (title, company, location, salary, employment type, relative date)
with /viewjob?jk=<key> (or rc/clk redirect) links. Everything else —
segmentation, field vocabulary, date resolution, URL canonicalization,
jk/VJK job-ID extraction, defaults — is inherited from BaseJobAlertParser
and the centralized services. Never assumes one job per email.
"""

from app.gmail.dto import NormalizedEmail
from app.job_alerts.dto.normalized_job import NormalizedJob
from app.job_alerts.parsers.base_parser import BaseJobAlertParser


class IndeedParser(BaseJobAlertParser):
    slug = "indeed"

    def supports(self, email: NormalizedEmail) -> bool:
        return "indeed.com" in email.sender.lower()

    def parse_jobs(self, email: NormalizedEmail) -> list[NormalizedJob]:
        """EVERY job block in the email becomes one candidate (spec sections
        3, 9) — a digest with 5 jobs yields 5 candidates."""
        jobs: list[NormalizedJob] = []
        for block, link in self._job_blocks(email):
            fields = self._fields_from_block(block)
            if fields.title is None:
                # No job-like content in this block — never fabricate a
                # pseudo-job from header/footer noise.
                continue
            jobs.append(self._candidate(fields, link, email))
        return jobs

