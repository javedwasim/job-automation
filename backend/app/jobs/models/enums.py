import enum


class JobEmailStatus(enum.StrEnum):
    """Status of a discovered job-alert email as it moves through the
    pipeline. Additional statuses arrive in later phases; this enum only
    needs the ones Phase 1 (ingestion) actually sets or reads.
    """

    NEW = "NEW"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class JobStatus(enum.StrEnum):
    """Status of a persisted Job (spec section 24)."""

    NEW = "NEW"
    PROCESSING = "PROCESSING"
    RELEVANT = "RELEVANT"
    EXPORTED = "EXPORTED"
    DUPLICATE = "DUPLICATE"
    IRRELEVANT = "IRRELEVANT"
    FAILED = "FAILED"
