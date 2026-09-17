"""Glassdoor job-alert parser (spec section 13, added per section 43 —
new platforms are additive parser modules, never pipeline edits).

Platform-specific knowledge ONLY — Glassdoor digest emails list one job
per block with company/title-link/location/salary/date/action structure.
The CRITICAL FORMAT: company name comes BEFORE the title anchor
(<a href="...">Title</a>), followed by location/salary/posting info.
Everything else — field vocabulary, date resolution, URL canonicalization,
_JO job-ID extraction, defaults — is inherited from BaseJobAlertParser and
the centralized services. Never assumes one job per email.
"""

import re

from bs4 import BeautifulSoup

from app.gmail.dto import NormalizedEmail
from app.job_alerts.dto.normalized_job import NormalizedJob
from app.job_alerts.parsers.base_parser import BaseJobAlertParser, BlockFields

# Regex patterns (imported concept from base_parser).
_ACTION_PHRASE_RE = re.compile(
    r"^(apply\s+now?|apply\s+on\s+company\s+site|easy\s+apply|view\s+job|"
    r"view\s+details?|see\s+job|see\s+more|show\s+more|save\s+job|"
    r"not\s+interested|dismiss)$",
    re.IGNORECASE,
)


class GlassdoorParser(BaseJobAlertParser):
    slug = "glassdoor"

    def supports(self, email: NormalizedEmail) -> bool:
        return "glassdoor.com" in email.sender.lower()

    def parse_jobs(self, email: NormalizedEmail) -> list[NormalizedJob]:
        """EVERY job block in the email becomes one candidate (spec sections
        3, 9) — a digest with 6 jobs yields 6 candidates. Glassdoor also
        sends review/salary/interview digests; blocks without job-like
        content produce no candidate (no pseudo-jobs).
        
        Glassdoor-specific: Title is the clickable link; company may appear
        before the title in the HTML. Extract directly from HTML structure.
        """
        jobs: list[NormalizedJob] = []
        
        # Use HTML-based extraction if available (real Glassdoor format).
        if email.html:
            html_jobs = self._parse_jobs_from_html(email)
            if html_jobs:
                return html_jobs
        
        # Fallback to base parser strategy for plain-text or non-standard formats.
        for block, link in self._job_blocks(email):
            fields = self._fields_from_block(block)
            if fields.title is None:
                continue
            jobs.append(self._candidate(fields, link, email))
        return jobs

    def _parse_jobs_from_html(self, email: NormalizedEmail) -> list[NormalizedJob]:
        """Extract jobs directly from HTML structure, matching title anchors
        with company/location content. Glassdoor format: company line before
        title anchor, location/salary after."""
        jobs: list[NormalizedJob] = []
        links = self._job_links(email)
        
        if not links:
            return []
        
        soup = BeautifulSoup(email.html or "", "html.parser")
        root = soup.body or soup
        
        for link in links:
            # Find the title anchor in HTML.
            title_anchor = self._best_html_anchor(root, link.url)
            if title_anchor is None:
                continue
            
            # Extract company/title/location from this anchor's context.
            fields = self._extract_glassdoor_fields(title_anchor)
            
            if fields.title is None:
                continue
            
            jobs.append(self._candidate(fields, link, email))
        
        return jobs

    def _extract_glassdoor_fields(self, title_anchor) -> BlockFields:
        """Extract company/title/location from the title anchor and its context.
        
        Glassdoor format: <p>Company</p> <a>Title</a> <p>Location</p> ...
        
        Strategy:
        1. Title = anchor text (must not be an action phrase)
        2. Company = nearest preceding <p> tag with meaningful content
        3. Location/salary/posting = extract from following content
        """
        # Title is the anchor text.
        title = title_anchor.get_text(strip=True)
        if not title or len(title) < 3:
            return BlockFields(title=None)
        
        # Filter out action phrases ("Easy Apply", "View Job", etc.).
        if _ACTION_PHRASE_RE.match(title):
            return BlockFields(title=None)
        
        # Company: find preceding sibling <p> tags.
        company = None
        node = title_anchor.previous_sibling
        while node is not None:
            if hasattr(node, 'name') and node.name == 'p':
                text = node.get_text(strip=True)
                if text and len(text) > 2:
                    company = text
                    break
            node = node.previous_sibling
        
        # Location/salary/posting/remote: extract from following content.
        # Collect text after title anchor up to next job anchor or section boundary.
        following_text = self._collect_following_text(title_anchor)
        
        # Use base parser's field extraction on the collected text.
        location = None
        remote_type = None
        salary = None
        employment_type = None
        posted_date = None
        is_promoted = False
        
        # Parse location from following lines.
        for line in following_text.splitlines():
            line = self._clean_line(line)
            if not line:
                continue
            
            # Check if this looks like a location.
            if self._is_location_line(line):
                location = line
                break
        
        # Extract other fields using base parser methods.
        salary = self._extract_salary(following_text)
        employment_type = self._extract_employment_type(following_text)
        posted_date = self._extract_posted_text(following_text)
        remote_type = self._extract_remote_type(following_text)
        is_promoted = self._is_promoted(following_text)
        
        return BlockFields(
            title=title,
            company=company,
            location=location,
            remote_type=remote_type,
            salary=salary,
            employment_type=employment_type,
            posted_date=posted_date,
            is_promoted=is_promoted,
        )

    def _collect_following_text(self, anchor, max_lines: int = 10) -> str:
        """Collect text from siblings following the anchor until the next
        job anchor or 'Easy Apply' action link is encountered."""
        lines = []
        node = anchor.next_sibling
        line_count = 0
        
        while node is not None and line_count < max_lines:
            if hasattr(node, 'name'):
                if node.name == 'a':
                    # Stop at next anchor (likely an action link or next job).
                    # But preserve the text we have so far.
                    break
                elif node.name in ('p', 'div', 'span', 'td', 'li'):
                    text = node.get_text(strip=True)
                    if text:
                        lines.append(text)
                        line_count += 1
            elif isinstance(node, str):
                text = str(node).strip()
                if text and len(text) > 2:
                    lines.append(text)
                    line_count += 1
            
            node = node.next_sibling
        
        return '\n'.join(lines)

    def _is_location_line(self, line: str) -> bool:
        """Check if a line looks like a location."""
        import re
        location_pattern = re.compile(
            r"^([A-Za-z][A-Za-z .'-]*,\s*[A-Za-z][A-Za-z .'-]*"
            r"|(?:remote|hybrid|on-site|onsite)\b.*)$",
            re.IGNORECASE,
        )
        return bool(location_pattern.match(line))

    def _is_promoted(self, text: str) -> bool:
        """Check if job is promoted/sponsored."""
        import re
        promoted_pattern = re.compile(r"\b(promoted|sponsored)\b", re.IGNORECASE)
        return bool(promoted_pattern.search(text))
