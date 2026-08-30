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

from bs4 import BeautifulSoup

from app.gmail.dto import EmailLink, NormalizedEmail
from app.gmail.html_text import render_block_text
from app.job_alerts.dto.normalized_job import NormalizedJob
from app.job_alerts.extraction.job_posted_date_extractor import JobPostedDateExtractor
from app.job_alerts.extraction.url_extractor import UrlExtractor
from app.job_alerts.extraction.url_normalizer import JobUrlNormalizer

_TITLE_AT_COMPANY_RE = re.compile(
    r"([A-Za-z0-9 ./,&()+\-']{3,80}?)\s+at\s+([A-Za-z0-9 .,&()\-']{2,80})"
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
_SALARY_LINE_HINT_RE = re.compile(
    r"(?:[$€£]|USD|EUR|GBP|PKR|Rs\.?|\d{1,3}(?:,\d{3})+)", re.IGNORECASE
)
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
            # NEVER fabricate a title (spec: a URL plus arbitrary surrounding
            # text is not a job). A block without a reliable title yields no
            # candidate — parsers skip before reaching here, and the
            # centralized normalizer rejects any empty title anyway.
            title=fields.title or "",
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
        """Segments the email into per-job blocks, each paired with at most
        one JOB link (spec section 10 — fields are never copied across jobs).
        Every link has already passed job-link classification (a URL is
        necessary but never sufficient — nav/footer/"saved jobs"/tracking
        links never reach here).

        Strategies, in priority order:
          A. Structured HTML job containers (real digest card markup).
          C. Plain-text "Title at Company" blocks (LinkedIn digest layout).
          B. Anchor-local context (text between located anchor positions).
          D. Safe fallback — a link that cannot be associated with job
             content gets an EMPTY block and the parser drops it (no title
             -> no candidate -> no garbage job).

        The earlier "divide the text evenly across N links" fallback is
        deliberately GONE — it manufactured garbage jobs from arbitrary
        fragments ("ailable.", "still av", ...): 10 links can legitimately
        produce 4 jobs, and 4 correct jobs are better than 4 correct + 9
        garbage."""
        links = self._job_links(email)
        if not links:
            return []
        text = email.plain_text or ""

        # Strategy A — structured HTML job containers (only when the email
        # actually has per-job card structure; flat layouts abort this).
        if email.html:
            container_blocks = self._blocks_from_html_containers(email, links)
            if container_blocks:
                return container_blocks

        # Strategy C — exactly one inline "Title at Company" header per job
        # link (LinkedIn digest layout): each segment belongs to its
        # same-position link.
        title_matches = list(_TITLE_AT_COMPANY_RE.finditer(text))
        if len(links) > 1 and len(title_matches) == len(links):
            blocks = []
            for i, match in enumerate(title_matches):
                end = title_matches[i + 1].start() if i + 1 < len(title_matches) else len(text)
                blocks.append((text[match.start() : end], links[i]))
            return blocks

        # Strategy B — anchor-local context (text between located anchors).
        anchor_blocks = self._anchor_blocks(text, links)
        if anchor_blocks:
            return anchor_blocks

        # Strategy D — safe fallback.
        if len(links) == 1:
            # Single-job email: the whole body belongs to that job.
            return [(text, links[0])]
        return [("", link) for link in links]

    def _anchor_blocks(
        self, text: str, links: list[EmailLink]
    ) -> list[tuple[str, EmailLink]] | None:
        """Pairs each link with the text from its located anchor up to the
        next anchor. Unanchored links get an EMPTY block — never an arbitrary
        slice (arbitrary text splitting is exactly how garbage jobs were
        minted)."""
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

        if not anchors:
            return None

        anchored_ids = {id(link) for _, link in anchors}
        blocks: list[tuple[str, EmailLink]] = []
        for i, (pos, link) in enumerate(anchors):
            end = anchors[i + 1][0] if i + 1 < len(anchors) else len(text)
            blocks.append((text[pos:end], link))
        for link in links:
            if id(link) not in anchored_ids:
                blocks.append(("", link))
        return blocks

    # --- Strategy A helpers: HTML per-job containers -----------------------

    # Elements that may wrap a single job card in digest markup.
    _JOB_CONTAINER_TAGS = ("table", "tr", "td", "li", "div", "p", "section", "article", "ul", "ol")
    _MAX_CONTAINER_CHARS = 900

    def _blocks_from_html_containers(
        self, email: NormalizedEmail, links: list[EmailLink]
    ) -> list[tuple[str, EmailLink]] | None:
        """Pairs every job link with the text of its nearest self-contained
        job-card element in the HTML. Aborts (returns None) when the email
        has no real card structure so lower strategies can try."""
        soup = BeautifulSoup(email.html or "", "html.parser")
        root = soup.body or soup
        blocks: list[tuple[str, EmailLink]] = []
        any_resolved = False
        for link in links:
            anchor = self._best_html_anchor(root, link.url)
            if anchor is None:
                blocks.append(("", link))
                continue
            container = self._nearest_job_container(anchor)
            if container is None:
                blocks.append(("", link))
                continue
            any_resolved = True
            blocks.append((render_block_text(container), link))
        return blocks if any_resolved else None

    def _best_html_anchor(self, root, url: str):
        """The <a> element for a job URL with the richest anchor text (the
        job-title link is preferred over the empty logo link / generic
        "Apply now" button sharing the same canonical URL)."""
        target = self._url_normalizer.canonical(url, self.slug)
        best = None
        best_len = -1
        for anchor in root.find_all("a", href=True):
            href = anchor.get("href")
            if not isinstance(href, str):
                continue
            href = href.strip()
            if not href.startswith(("http://", "https://")):
                continue
            if self._url_normalizer.canonical(href, self.slug) != target:
                continue
            text = anchor.get_text(strip=True)
            if len(text) > best_len:
                best, best_len = anchor, len(text)
        return best

    def _nearest_job_container(self, anchor):
        """Closest ancestor element that looks like a job card: block content
        with at least two lines and a bounded size. The <body>/<html> roots
        are never containers (the whole email is not one job)."""
        node = anchor.parent
        while node is not None:
            name = getattr(node, "name", None)
            if name in (None, "html", "body"):
                return None
            if name in self._JOB_CONTAINER_TAGS:
                text = render_block_text(node)
                lines = [ln for ln in text.splitlines() if ln.strip()]
                total = sum(len(ln) for ln in lines)
                if len(lines) >= 2 and 0 < total <= self._MAX_CONTAINER_CHARS:
                    return node
            node = node.parent
        return None

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
        # Lines that are ONLY a promoted/sponsored badge ("Promoted") are a
        # card flag, never a title/company.
        body_lines = [
            line for line in body_lines if not _PROMOTED_BADGE_RE.fullmatch(line)
        ]
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
        # The title is the first *title-like* line — never a promoted badge,
        # a location, a remote-type word, a salary or a posting date. This
        # also means a card whose "title" slot is empty produces NO job
        # instead of minting a pseudo-title from surrounding text.
        title = None
        start = 0
        for i, line in enumerate(body_lines):
            if self._is_title_like(line):
                title = line
                start = i + 1
                break
        if title is None:
            return None, None, None, None

        company = location = None
        for line in body_lines[start:]:
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

    def _is_title_like(self, line: str | None) -> bool:
        """True when a block line can plausibly be a job title. Rejects the
        card-level noise that the old blocker picked up as titles: promoted
        badges, remote/location-only lines, salary lines, posting-date lines
        and bare fragments (too short / no alphanumerics / ends in lone
        punctuation suggesting a text split)."""
        line = (line or "").strip()
        if not line or len(line) < 3:
            return False
        if _ACTION_PHRASE_RE.match(line):
            return False
        if not any(ch.isalnum() for ch in line):
            return False
        if _PROMOTED_BADGE_RE.fullmatch(line):
            return False
        if _REMOTE_TYPE_RE.fullmatch(line):
            return False
        if _POSTED_TEXT_RE.fullmatch(line):
            return False
        if _LOCATION_LINE_RE.fullmatch(line):
            return False
        if _SALARY_CURRENCY_RE.fullmatch(line) or _SALARY_PLAIN_RE.fullmatch(line):
            return False
        # Reject fragments that look like they were cut mid-word: a line that
        # ends with punctuation but no trailing alnum (e.g. "ailable.",
        # "ners is.", "ved") is almost certainly a text-split artifact.
        if line[-1] in ".,;:" and not line[-2:].isalnum():
            return False
        # A single word of fewer than 6 chars with no space is not a title
        # (e.g. "job", "ved", "ogy", "Equi").  Legitimate one-word titles
        # (Engineer, Developer, Backend) are long enough to survive.
        if " " not in line and len(line) < 6:
            return False
        # Reject multi-word fragments where the final word is a 1-2 char
        # stub — e.g. "still av", "ners is" — classic text-split artifacts
        # where a word was chopped in the middle.
        words = line.split()
        if len(words) >= 2 and len(words[-1]) <= 2:
            return False
        # Also reject if the FIRST word is a 1-2 char stub (e.g. "ty Part",
        # "at Developer") — another classic text-split artifact.
        if len(words) >= 2 and len(words[0]) <= 2:
            return False
        # Reject fragments that end with a consonant-only stub (no vowel),
        # suggesting a mid-word cut: "ners", "ology", "Tril", "t Par".
        if not any(c in "aeiouAEIOU" for c in words[-1]) and len(words[-1]) < 4:
            return False
        return True

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

