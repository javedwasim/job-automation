"""GenericParser (spec section 11) — fallback for unrecognized platforms.
Always supports() == True so it must be registered LAST in the registry.

Uses the same BaseJobAlertParser scaffolding as every platform parser: it
only contributes the fallback *strategy* (guess the title from the subject
when a block has none). Multi-job segmentation, field reading, date
extraction, URL canonicalization and defaults all come from the base class
and the centralized services — a generic digest with N recognized job links
yields N candidates, never one."""

from dataclasses import replace

from app.gmail.dto import NormalizedEmail
from app.job_alerts.dto.normalized_job import NormalizedJob
from app.job_alerts.parsers.base_parser import BaseJobAlertParser


class GenericParser(BaseJobAlertParser):
    slug = "generic"

    def supports(self, email: NormalizedEmail) -> bool:
        return True  # fallback — never blocks a future specialized parser from being added

    def parse_jobs(self, email: NormalizedEmail) -> list[NormalizedJob]:
        """EVERY recognized job link in the email becomes its own candidate
        (spec section 3) via the shared per-job block segmentation — the
        fallback parser never collapses a multi-job email into one job."""
        jobs: list[NormalizedJob] = []
        for block, link in self._job_blocks(email):
            fields = self._fields_from_block(block)
            title = fields.title or self._guess_title(email.subject, block)
            if title is None:
                continue
            candidate = self._candidate(fields, link, email)
            jobs.append(replace(candidate, title=title))
        if jobs:
            return jobs

        # No link matched the shared job-posting patterns. Keep the classic
        # conservative single-URL inference ONLY for emails that point at a
        # direct job posting on an unusual domain (careers site, job board
        # not in the known patterns) — otherwise every broad-query email
        # (newsletter, social digest, account notice) would become a junk row.
        best = self._url_extractor.extract(email.links)
        if best is None or not best.direct_job_url:
            return []

        block = email.plain_text or ""
        fields = self._fields_from_block(block)
        title = self._guess_title(email.subject, block) or fields.title
        if title is None:
            return []

        candidate = self._candidate(fields, None, email)
        return [replace(candidate, job_url=best.url, title=title)]

    def _guess_title(self, subject: str, plain_text: str) -> str | None:
        if subject.strip():
            return subject.strip()
        return self._first_line(plain_text)

