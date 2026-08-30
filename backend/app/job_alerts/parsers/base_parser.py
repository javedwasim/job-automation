"""BaseJobAlertParser (spec section 14) — shared scaffolding for every
platform parser.

The division of responsibility this architecture enforces:

  Platform parsers (subclasses) answer ONLY:
    "How does THIS platform structure its alert emails?" — i.e. which links
    are job links, and how to read title/company/location/... from one
    per-job block of the email.

  This base class + the centralized services answer everything else:
    date extraction, URL canonicalization, job-ID extraction, validation,
    defaults, promotion detection.

Adding a new platform (spec section 43) means writing a small subclass that
implements `supports()` and `parse_jobs()` — no core logic is duplicated.
"""

import re
from dataclasses import dataclass, replace
from html import unescape

from app.gmail.dto import EmailLink, NormalizedEmail
from app.job_alerts.dto.normalized_job import NormalizedJob
from app.job_alerts.extraction.job_posted_date_extractor import JobPostedDateExtractor
from app.job_alerts.extraction.url_extractor import UrlExtractor
from app.job_alerts.extraction.url_normalizer import JobUrlNormalizer

_TITLE_AT_COMPANY_RE = re.compile(
    r"([A-Za-z0-9 /,&()+\-']{3,80}?)\s+at\s+([A-Za-z0-9 .,&()\-']{2,80})"
)
_REMOTE_TYPE_RE = re.compile(r"\b(remote|hybrid|on-?site)\b", re.IGNORECASE)
_EMPLOYMENT_TYPE_RE = re.compile(
    r"\b(full[\s-]?time|part[\s-]?time|contract(?:or)?|temporary|temp\b|"
    r"internship|intern\b|permanent|freelance)\b",
    re.IGNORECASE,
)
# "$120,000 - $150,000 a year", "$45/hr", "€50K - €70K per year", "PKR 80,000"
_SALARY_CURRENCY_RE = re.compile(
    r"(?:[$€£]|USD|EUR|GBP|PKR|Rs\.?)\s?\d[\d,.]*\s*[KkMm]?"
    r"(?:\s*[-–—]\s*(?:[$€£]|USD|EUR|GBP|PKR|Rs\.?)?\s?\d[\d,.]*\s*[KkMm]?)?"
    r"(?:\s*(?:a|per|/)\s*(?:year|yr|month|mo\b|week|wk\b|day|hour|hr))?",
)
# "120,000 - 150,000 a year" (no currency symbol)
_SALARY_PLAIN_RE = re.compile(
    r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\s*[-–—]\s*\d{1,3}(?:,\d{3})+(?:\.\d+)?"
    r"(?:\s*(?:a|per|/)\s*(?:year|yr|month|week|day|hour|hr))?",
)
# Raw relative posting phrase as the email words it ("Posted 3 hours ago",
# "Just now", "2 weeks ago"); the shared date extractor resolves it later.
_POSTED_TEXT_RE = re.compile(
    r"(?:posted\s*:?\s*)?(just\s+now|\d+\s*(?:minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?)\s+ago)",
    re.IGNORECASE,
)
_DIGEST_HEADER_RE = re.compile(
    r"(\d+\s+new\s+(?:jobs?|roles?|openings)|\bjobs?\b\s+(?:match|for)\b|"
    r"match(?:es)?\s+your\s+alert|new\s+jobs?\s+for\s+you|job\s+alerts?)",
    re.IGNORECASE,
)
# Card action labels that must never become a job title (a digest whose
# blocks are split on "Apply now" anchors would otherwise mint "Apply Now"
# pseudo-jobs — spec section 22: never fabricate).
_ACTION_PHRASE_RE = re.compile(
    r"^(apply\s+now?|apply\s+on\s+company\s+site|easy\s+apply|view\s+job|"
    r"view\s+details?|see\s+job|see\s+more|show\s+more|save\s+job|"
    r"not\s+interested|dismiss)$",
    re.IGNORECASE,
)
_PROMOTED_RE = re.compile(r"\b(promoted|sponsored)\b", re.IGNORECASE)
# A line that is ONLY a promoted/sponsored badge — never a title.
_PROMOTED_BADGE_RE = re.compile(r"(?:promoted|sponsored)", re.IGNORECASE)
# Quick pre-filter so salary ranges are never mistaken for identity lines.
_SALARY_LINE_HINT_RE = re.compile(r"(?:[$€£]|USD|EUR|GBP|PKR|Rs\.?|\d{1,3}(?:,\d{3})+)", re.IGNORECASE)
_LOCATION_LINE_RE = re.compile(
    r"^([A-Za-z][A-Za-z .'-]*,\s*[A-Za-z][A-Za-z .'-]*"
    r"|(?:remote|hybrid|on-site|onsite)\b.*)$",
    re.IGNORECASE,
)
# Indeed-style "Company - Location" line (e.g. "TechCorp - Lahore, Pakistan",
# "DataSoft - Remote"). The company part is digits/symbol-free, which keeps
# salary lines ("$150,000 - $180,000 a year", "PKR 350,000 - 450,000") out;
# _split_company_location additionally requires the location side to actually
# look like a location.
_COMPANY_LOCATION_LINE_RE = re.compile(
    r"^(?P<company>[A-Za-z][A-Za-z0-9 .,&()'/-]*?)\s+[-–—]\s+(?P<loc>[A-Za-z][A-Za-z .,'-]*)$"
)


@dataclass(frozen=True)
class BlockFields:
    """Fields read from ONE per-job block of an email (never shared across
    jobs — spec section 10)."""

    title: str | None = None
    company: str | None = None
    location: str | None = None
    remote_type: str | None = None
    salary: str | None = None
    employment_type: str | None = None
    posted_date: str | None = None
    is_promoted: bool = False


class BaseJobAlertParser:
    slug = "base"

    def __init__(self) -> None:
        self._date_extractor = JobPostedDateExtractor()
        self._url_extractor = UrlExtractor()
        self._url_normalizer = JobUrlNormalizer()

    # --- contract ---------------------------------------------------------

    def supports(self, email: NormalizedEmail) -> bool:
        raise NotImplementedError

    def parse_jobs(self, email: NormalizedEmail) -> list[NormalizedJob]:
        """Platform-specific: extracts ZERO or more job candidates from one
        email. Must never stop at the first job (spec section 3)."""
        raise NotImplementedError

    def parse(self, email: NormalizedEmail) -> list[NormalizedJob]:
        """Finalizes every candidate with shared defaults — the ONLY place
        where defaults are applied (source, received_at, job ID, date)."""
        finalized: list[NormalizedJob] = []
        for job in self.parse_jobs(email):
            finalized.append(self._finalize(job, email))
        return finalized

    def _candidate(
        self, fields: BlockFields, link: EmailLink | None, email: NormalizedEmail
    ) -> NormalizedJob:
        """Builds a raw candidate from ONE block's fields. source slug,
        received_at, job_posted_at resolution and platform job-ID extraction
        are applied uniformly later by _finalize — every platform gets
        identical default handling (spec sections 3, 10)."""
        return NormalizedJob(
            title=fields.title or "Unknown Title",
            company=fields.company,
            location=fields.location,
            source=self.slug,
            platform_job_id=None,  # extracted from the URL during finalization
            job_url=link.url if link else None,
            application_url=None,
            job_posted_at=None,  # resolved from posted_date during finalization
            received_at=email.received_at,
            description=None,
            source_email_id=email.gmail_message_id,
            remote_type=fields.remote_type,
            salary=fields.salary,
            employment_type=fields.employment_type,
            is_promoted=fields.is_promoted,
            posted_date=fields.posted_date,
        )

    # --- shared helpers available to subclasses ----------------------------

    def _job_links(self, email: NormalizedEmail) -> list[EmailLink]:
        """ALL genuine job-posting links in the email (spec section 9)."""
        return self._url_extractor.extract_job_links(email.links)

    def _job_blocks(self, email: NormalizedEmail) -> list[tuple[str, EmailLink | None]]:
        """Segments the email into per-job blocks, each associated with at
        most one job link (spec section 10 — fields are never copied across
        jobs). Each block starts at its link's anchor text so the fields read
        from the block belong to that block's job."""
        links = self._job_links(email)
        if not links:
            return []

        text = email.plain_text or ""
        anchors: list[tuple[int, EmailLink]] = []
        used_positions: set[int] = set()
        cursor = 0
        for link in links:
            probe = link.anchor_text.strip()
            if len(probe) < 4:  # too generic to locate ("Apply", "View")
                continue
            pos = text.find(probe, cursor)
            if pos == -1 or pos in used_positions:
                pos = next(
                    (p for p in self._all_occurrences(text, probe) if p not in used_positions),
                    -1,
                )
            if pos == -1:
                continue
            used_positions.add(pos)
            cursor = pos + len(probe)
            anchors.append((pos, link))

        if anchors and len(anchors) == len(links):
            blocks: list[tuple[str, EmailLink | None]] = []
            for i, (pos, link) in enumerate(anchors):
                end = anchors[i + 1][0] if i + 1 < len(anchors) else len(text)
                blocks.append((text[pos:end], link))
            return blocks

        if len(links) == 1:
            # Single-job email: the whole body belongs to that job.
            return [(text, links[0])]

        # Not every link could be anchored in the text — try blank-line
        # paragraphs paired in body order (common for HTML-only layouts).
        paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
        if len(paragraphs) == len(links):
            return list(zip(paragraphs, links))

        # HTML digests often render link anchors ("View Job: …", "Apply")
        # that never appear in the plain-text body. If the body contains
        # exactly one inline "Title at Company" header per link (LinkedIn
        # digest layout), segment on those title headers instead — each
        # segment then belongs to its same-position link.
        title_matches = list(_TITLE_AT_COMPANY_RE.finditer(text))
        if len(links) > 1 and len(title_matches) == len(links):
            blocks = []
            for i, match in enumerate(title_matches):
                end = title_matches[i + 1].start() if i + 1 < len(title_matches) else len(text)
                blocks.append((text[match.start() : end], links[i]))
            return blocks

        # Last resort: never mis-associate fields — one conservative block.
        return [(text, links[0])]

    def _fields_from_block(self, block: str) -> BlockFields:
        """Reads the shared field vocabulary (title/company/location/remote/
        salary/employment type/posting phrase/promotion) from one block.
        Platform parsers may override individual extractors for genuinely
        platform-specific formats, but the defaults here cover the common
        line-per-field digest layout."""
        lines = [self._clean_line(line) for line in block.splitlines()]
        lines = [line for line in lines if line]

        title, company, location, remote_type = self._title_company_location(lines)

        return BlockFields(
            title=title,
            company=company,
            location=location,
            remote_type=remote_type or self._extract_remote_type(block),
            salary=self._extract_salary(block),
            employment_type=self._extract_employment_type(block),
            posted_date=self._extract_posted_text(block),
            is_promoted=bool(_PROMOTED_RE.search(block)),
        )

    def _title_company_location(
        self, lines: list[str]
    ) -> tuple[str | None, str | None, str | None, str | None]:
        body_lines = [line for line in lines if not _DIGEST_HEADER_RE.search(line)]
        # Action labels ("Apply now", "View job") open some blocks when a
        # digest is segmented on action anchors — they are not titles.
        while body_lines and _ACTION_PHRASE_RE.match(body_lines[0]):
            body_lines = body_lines[1:]
        if not body_lines:
            return None, None, None, None

        # Layout A — inline "Title at Company(- Location)" (LinkedIn style).
        # Scanned over the first few body lines, not just the first, because
        # digests often lead with a header line that is not the job title.
        for i, line in enumerate(body_lines[:8]):
            if match := _TITLE_AT_COMPANY_RE.search(line):
                title = match.group(1).strip()
                # Trim a trailing " - Remote"/" - Hybrid" suffix and keep it
                # as the location/remote signal instead.
                parts = match.group(2).split(" - ")
                company = parts[0].strip()
                location = parts[1].strip() if len(parts) > 1 else None
                remote_type = self._normalize_remote(location)
                if location is None:
                    # Inline layout still often puts location on the next line.
                    location, remote_type = self._location_from_following(body_lines[i + 1 :])
                return title, company, location, remote_type

        # Layout B — one field per line ("Title", "Company", "Lahore, ...").
        title = body_lines[0]
        company = location = None
        for line in body_lines[1:]:
            # Indeed-style "Company - Location" line carries both fields.
            # Checked FIRST: "DataSoft - Remote" must split into
            # company="DataSoft" + location="Remote", not be swallowed whole
            # by the bare-remote branch below.
            if split := self._split_company_location(line):
                company, location = split
                continue
            if _REMOTE_TYPE_RE.search(line) and "," not in line:
                location = line
                return title, company, location, self._normalize_remote(line)
            if _LOCATION_LINE_RE.match(line):
                location = line
                continue
            if company is None and "," not in line and "$" not in line and "ago" not in line:
                company = line
                continue
            break
        return title, company, location, self._normalize_remote(location)

    def _split_company_location(self, line: str) -> tuple[str, str] | None:
        """Splits an Indeed-style "Company - Location" line into its two
        fields. Guarded so salary lines ("PKR 350,000 - 450,000 a month")
        and titles never match: the company part must be digits-free and the
        location part must actually look like a location."""
        match = _COMPANY_LOCATION_LINE_RE.match(line)
        if not match:
            return None
        location = match.group("loc").strip()
        if not ("," in location or _REMOTE_TYPE_RE.search(location)):
            return None
        return match.group("company").strip(), location

    def _location_from_following(self, lines: list[str]) -> tuple[str | None, str | None]:
        for line in lines[:3]:
            if _REMOTE_TYPE_RE.search(line) or _LOCATION_LINE_RE.match(line):
                return line, self._normalize_remote(line)
        return None, None

    def _extract_remote_type(self, text: str) -> str | None:
        if match := _REMOTE_TYPE_RE.search(text):
            return self._normalize_remote(match.group(1))
        return None

    def _extract_salary(self, text: str) -> str | None:
        for pattern in (_SALARY_CURRENCY_RE, _SALARY_PLAIN_RE):
            if match := pattern.search(text):
                return self._clean_line(match.group(0))
        return None

    def _extract_employment_type(self, text: str) -> str | None:
        if match := _EMPLOYMENT_TYPE_RE.search(text):
            return match.group(1).lower().replace(" ", "-").replace("contractor", "contract")
        return None

    def _extract_posted_text(self, text: str) -> str | None:
        if match := _POSTED_TEXT_RE.search(text):
            return self._clean_line(match.group(0))
        return None

    def _first_line(self, text: str) -> str | None:
        for line in text.splitlines():
            cleaned = self._clean_line(line)
            if cleaned:
                return cleaned
        return None

    def _clean_line(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = re.sub(r"\s+", " ", unescape(value)).strip()
        return cleaned or None

    @staticmethod
    def _normalize_remote(value: str | None) -> str | None:
        if not value:
            return None
        lowered = value.lower()
        if "remote" in lowered:
            return "remote"
        if "hybrid" in lowered:
            return "hybrid"
        if re.search(r"on-?site", lowered):
            return "onsite"
        return None

    # --- finalization ------------------------------------------------------

    def _finalize(self, job: NormalizedJob, email: NormalizedEmail) -> NormalizedJob:
        """Applies the shared defaults every platform gets for free:
        source slug, email's received_at, email id, canonical job URL,
        platform job ID from the URL, and job_posted_at resolved from the
        raw posted_date phrase. URL canonicalization and job-ID extraction
        happen HERE (spec section 8) — never duplicated per platform."""
        job_url = job.job_url
        if job_url:
            job_url = self._url_normalizer.canonical(job_url, self.slug)

        job_posted_at = job.job_posted_at
        if job_posted_at is None and job.posted_date:
            job_posted_at = self._date_extractor.extract(job.posted_date, email.received_at)

        platform_job_id = job.platform_job_id
        if platform_job_id is None and job_url:
            platform_job_id = self._url_normalizer.extract_job_id(job_url, self.slug)

        return replace(
            job,
            source=self.slug,
            received_at=email.received_at,
            source_email_id=email.gmail_message_id,
            job_url=job_url or None,  # canonical form (tracking params stripped)
            job_posted_at=job_posted_at,
            platform_job_id=platform_job_id,
        )

    @staticmethod
    def _all_occurrences(text: str, probe: str) -> list[int]:
        positions: list[int] = []
        start = 0
        while (found := text.find(probe, start)) != -1:
            positions.append(found)
            start = found + len(probe)
        return positions

