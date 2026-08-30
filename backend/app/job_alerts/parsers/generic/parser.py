"""GenericParser (spec section 11) — fallback for unrecognized platforms.
Always supports() == True so it must be registered LAST in the registry.

Uses the same BaseJobAlertParser scaffolding as every platform parser: it
only contributes the fallback *strategy* (trust the best single job URL,
guess the title from the subject). All shared behavior — multi-link
handling, field reading, date extraction, URL canonicalization, defaults —
comes from the base class and the centralized services.
"""

from dataclasses import replace

from app.gmail.dto import NormalizedEmail
from app.job_alerts.dto.normalized_job import NormalizedJob
from app.job_alerts.parsers.base_parser import BaseJobAlertParser


class GenericParser(BaseJobAlertParser):
    slug = "generic"

    def supports(self, email: NormalizedEmail) -> bool:
        return True  # fallback — never blocks a future specialized parser from being added

    def parse_jobs(self, email: NormalizedEmail) -> list[NormalizedJob]:
        # The fallback parser only trusts emails containing a link to an
        # actual job posting — otherwise every broad-query email (newsletter,
        # social digest, account notice) would become a junk job row.
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

