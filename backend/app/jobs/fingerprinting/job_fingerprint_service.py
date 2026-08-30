"""JobFingerprintService (spec section 25) — deterministic, centralized
dedup key shared by every platform (spec section 16).

The preferred identity is `platform + canonical job URL` — canonicalization
(tracking stripped, /comm/ aliases collapsed, params sorted) is delegated to
the ONE shared JobUrlNormalizer, so LinkedIn/Indeed/Glassdoor/future parsers
never reimplement it. For LinkedIn-style URLs the canonical URL inherently
encodes the platform job ID, so `linkedin + 123456789` identifies the same
job no matter which email delivered it.

The title+company basis exists ONLY for candidates without any URL. It is
namespaced under `title:` and never used when a URL exists, so two genuinely
different jobs that merely share a title (spec section 16) can never merge.
"""

import hashlib

from app.job_alerts.extraction.url_normalizer import JobUrlNormalizer


def normalize_job_url(url: str) -> str:
    """Backwards-compatible module-level helper — now delegates to the
    centralized platform-aware normalizer (single source of truth)."""
    return JobUrlNormalizer().canonical(url)


class JobFingerprintService:
    def __init__(self, url_normalizer: JobUrlNormalizer | None = None) -> None:
        self._urls = url_normalizer or JobUrlNormalizer()

    def fingerprint(
        self,
        *,
        platform: str,
        job_url: str | None,
        title: str,
        company: str | None,
        platform_job_id: str | None = None,
    ) -> str:
        if job_url:
            # Preferred identity (spec section 16): platform + canonical URL —
            # the canonical form inherently encodes the platform job ID for
            # LinkedIn (/jobs/view/<id>), Indeed (jk=/vjk=) and Glassdoor
            # (_JO<id>.htm).
            basis = f"{platform}:url:{self._urls.canonical(job_url, platform)}"
        elif platform_job_id:
            # No URL but a real platform ID: still a stable cross-email
            # identity — strictly better than a text basis.
            basis = f"{platform}:id:{platform_job_id.strip().lower()}"
        else:
            # Last-resort text basis, namespaced so it can never collide with
            # URL/ID identities. Two different jobs sharing title+company are
            # rare and, without ANY anchor, indistinguishable by design.
            basis = f"{platform}:title:{title.strip().lower()}:{(company or '').strip().lower()}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()

