"""ParserRegistry (spec section 6) — tries each registered parser in order
and returns the first that supports() the email. GenericParser must always
be registered last since it supports everything."""

from app.gmail.dto import NormalizedEmail
from app.job_alerts.contracts.job_platform_parser import JobPlatformParser
from app.job_alerts.parsers.generic.parser import GenericParser
from app.job_alerts.parsers.glassdoor.parser import GlassdoorParser
from app.job_alerts.parsers.indeed.parser import IndeedParser
from app.job_alerts.parsers.linkedin.parser import LinkedInParser
from app.job_alerts.parsers.wellfound.parser import WellfoundParser


class ParserRegistry:
    def __init__(self, parsers: list[JobPlatformParser] | None = None) -> None:
        # Order matters: specific parsers first, GenericParser last.
        self._parsers: list[JobPlatformParser] = parsers or [
            LinkedInParser(),
            IndeedParser(),
            WellfoundParser(),
            GlassdoorParser(),
            GenericParser(),
        ]

    def get_parser(self, email: NormalizedEmail) -> JobPlatformParser:
        for parser in self._parsers:
            if parser.supports(email):
                return parser
        # Unreachable while GenericParser is registered, but keeps mypy/callers honest.
        raise RuntimeError("No parser (not even GenericParser) matched this email")

    def register(self, parser: JobPlatformParser, *, before: str | None = None) -> None:
        """Adds a new platform parser (spec section 43 — additive, not a
        rewrite). By default appends before GenericParser so it still runs
        last."""
        if before is None:
            self._parsers.insert(len(self._parsers) - 1, parser)
        else:
            index = next(i for i, p in enumerate(self._parsers) if p.slug == before)
            self._parsers.insert(index, parser)
