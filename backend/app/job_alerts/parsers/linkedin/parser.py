"""LinkedIn job-alert parser (spec section 11).

Platform-specific knowledge ONLY — how LinkedIn structures its alert
emails: inline "Title at Company - Location" lines, /jobs/view/<id> links,
optional "Promoted" badges. Multi-job segmentation, field reading, date
resolution, URL canonicalization, job-ID extraction and defaults are all
inherited from BaseJobAlertParser and the centralized services (spec
section 14). Promoted jobs are flagged, never auto-rejected — their actual
job_posted_at decides freshness (spec section 11).

LinkedIn-specific guarantees on top of the shared scaffolding:

  * ONE record per job_id — a single job card carries several links to the
    same posting (the jobcard_body title link, the job_posting CTA, the
    company_logo image link, /comm/ aliases, country subdomains). They are
    all the SAME job: candidates are deduplicated by the job_id taken from
    the /jobs/view/<job_id> URL before anything reaches the dashboard, and
    the jobcard_body link is preferred as the primary job link.
  * Title/Company are mapped to their correct values: the job-title
    anchor's visible text is the authoritative title, so a company line
    that precedes the title line in the card can never be minted as the
    title (and the real title can never end up in the company field).
"""

import re
from dataclasses import replace

from app.gmail.dto import EmailLink, NormalizedEmail
from app.job_alerts.dto.normalized_job import NormalizedJob
from app.job_alerts.parsers.base_parser import BaseJobAlertParser, BlockFields

# The trk/marketing value LinkedIn puts on the main job-card link
# (…/jobs/view/<id>?trk=eml-job_digest-jobcard_body). Preferred as the
# primary job link for a job_id.
_JOBCARD_BODY_RE = re.compile(r"jobcard[-_]?body", re.IGNORECASE)

# Fields considered when scoring which candidate of one job_id is richest.
_MERGEABLE_FIELDS = (
    "company",
    "location",
    "remote_type",
    "salary",
    "employment_type",
    "posted_date",
)


class LinkedInParser(BaseJobAlertParser):
    slug = "linkedin"

    def supports(self, email: NormalizedEmail) -> bool:
        return "linkedin.com" in email.sender.lower()

    def parse_jobs(self, email: NormalizedEmail) -> list[NormalizedJob]:
        """EVERY job card in the email becomes one candidate (spec sections
        3, 9) — a digest with 8 jobs yields 8 candidates — then exactly ONE
        candidate survives per /jobs/view/<job_id> (multiple links for the
        same job are one job, never multiple records)."""
        entries: list[tuple[BlockFields, EmailLink | None]] = []
        for block, link in self._job_blocks(email):
            fields = self._fields_from_block(block)
            fields = self._resolve_fields(fields, block, link)
            if fields.title is None:
                # No job-like content in this block — never fabricate a
                # pseudo-job from header/footer noise.
                continue
            entries.append((fields, link))
        return [
            self._candidate(fields, link, email)
            for fields, link in self._one_record_per_job_id(entries)
        ]

    # --- LinkedIn title/company mapping ------------------------------------

    def _resolve_fields(
        self, fields: BlockFields, block: str, link: EmailLink | None
    ) -> BlockFields:
        """The job-title anchor's visible text is the authoritative title.

        Guards the mapping bugs real digests produce: a company line rendered
        ABOVE the title line is picked by the shared block reader as the
        "first title-like line" — the anchor text (the actual job title,
        e.g. "Senior Machine Learning Engineer (Remote)") overrides it and
        company/location are re-derived from the card lines without the
        title line, so company text never becomes the Title and the real
        title never ends up in the Company field.
        """
        if link is None:
            return fields
        anchor = self._clean_line(link.anchor_text)
        if not anchor or not self._is_title_like(anchor):
            # Empty logo anchors and action labels ("View job") are not
            # titles — keep the block-derived fields untouched.
            return fields
        if fields.title is None:
            return replace(fields, title=anchor)
        if anchor.lower() == fields.title.lower():
            return fields
        if fields.title.lower() in anchor.lower():
            # Block title is the front of an inline
            # "Title at Company - Location" anchor — the shared Layout A
            # split already produced the correct fields.
            return fields
        return self._rederive_fields_around_title(fields, block, anchor)

    def _rederive_fields_around_title(
        self, fields: BlockFields, block: str, anchor: str
    ) -> BlockFields:
        """Rebuilds company/location from the card lines once the REAL title
        (the anchor text) replaced the block's first title-like line."""
        lines = [line for line in (self._clean_line(l) for l in block.splitlines()) if line]
        idx = next(
            (i for i, line in enumerate(lines) if line.lower() == anchor.lower()), None
        )
        if idx is None:
            # The anchor text is not part of this block's text — keep the
            # block fields but drop a company that merely duplicated the
            # displaced title (displacement artifact).
            company = fields.company
            if company and fields.title and company.lower() == fields.title.lower():
                company = None
            return replace(fields, title=anchor, company=company)

        rest = lines[:idx] + lines[idx + 1 :]
        sub_title, sub_company, sub_location, sub_remote = self._title_company_location(rest)
        # The first standalone line of a card IS the company whether it was
        # rendered above or below the title line.
        company = sub_company or sub_title
        if company is not None and not self._is_title_like(company):
            company = None
        if company is not None and company.lower() == anchor.lower():
            company = None
        return replace(
            fields,
            title=anchor,
            company=company,
            location=sub_location,
            remote_type=fields.remote_type or sub_remote,
        )

    # --- one record per job_id ----------------------------------------------

    def _one_record_per_job_id(
        self, entries: list[tuple[BlockFields, EmailLink | None]]
    ) -> list[tuple[BlockFields, EmailLink | None]]:
        """Collapses every candidate carrying the same /jobs/view/<job_id>
        into ONE record — the jobcard_body link wins as the primary job
        link, ties broken by field richness and anchor length. Fields the
        winner is missing are merged in from the same job's other links
        (never from a different job), so a repeated card can't leave Posted
        or Company empty when the email states them. Candidates without a
        job_id have no identity to dedupe on and pass through untouched."""
        best: dict[str, tuple[tuple[int, int, int], BlockFields, EmailLink | None]] = {}
        order: list[str] = []
        passthrough: list[tuple[BlockFields, EmailLink | None]] = []

        for fields, link in entries:
            job_id = self._url_normalizer.extract_job_id(
                link.url if link else None, self.slug
            )
            if not job_id:
                passthrough.append((fields, link))
                continue
            rank = self._rank(fields, link)
            current = best.get(job_id)
            if current is None:
                order.append(job_id)
                best[job_id] = (rank, fields, link)
            elif rank > current[0]:
                best[job_id] = (rank, fields, link)

        deduped: list[tuple[BlockFields, EmailLink | None]] = []
        for job_id in order:
            _, fields, link = best[job_id]
            # Merge (never overwrite) fields from the same job_id's other
            # links — same job only, spec section 10 respected.
            for candidate_fields, candidate_link in entries:
                candidate_id = self._url_normalizer.extract_job_id(
                    candidate_link.url if candidate_link else None, self.slug
                )
                if candidate_id != job_id:
                    continue
                if candidate_link is not link and candidate_fields is not fields:
                    fields = self._merge_fields(fields, candidate_fields)
            deduped.append((fields, link))
        deduped.extend(passthrough)
        return deduped

    @staticmethod
    def _merge_fields(base: BlockFields, extra: BlockFields) -> BlockFields:
        """Fills only fields `base` is missing (spec: never overwrite a known
        value, never fabricate). is_promoted is a card flag — true if ANY
        card for this job shows it."""
        updates = {
            name: getattr(extra, name)
            for name in _MERGEABLE_FIELDS
            if getattr(base, name) is None and getattr(extra, name) is not None
        }
        promoted = base.is_promoted or extra.is_promoted
        if not updates and promoted == base.is_promoted:
            return base
        return replace(base, is_promoted=promoted, **updates)

    def _rank(self, fields: BlockFields, link: EmailLink | None) -> tuple[int, int, int]:
        """Preference order within one job_id:
        1. the jobcard_body link (LinkedIn's primary job-card link),
        2. the candidate with the most extracted fields,
        3. the link with the most anchor text (the job-title link)."""
        url = (link.url if link else "") or ""
        anchor_len = len((link.anchor_text or "").strip()) if link else 0
        filled = sum(1 for name in _MERGEABLE_FIELDS if getattr(fields, name) is not None)
        return (1 if _JOBCARD_BODY_RE.search(url) else 0, filled, anchor_len)

