from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GmailAccountOut(BaseModel):
    """Deliberately omits access_token_encrypted / refresh_token_encrypted —
    tokens must never be exposed through API responses (spec section 34)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    connected_at: datetime
    token_expires_at: datetime


class JobEmailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    gmail_message_id: str
    source: str | None
    sender: str
    subject: str
    received_at: datetime
    status: str


class AuthorizationUrlOut(BaseModel):
    authorization_url: str
    state: str


class SyncResultOut(BaseModel):
    account_email: str
    messages_found: int
    messages_ingested: int
    messages_skipped_duplicate: int
    messages_failed: int


class BackfillResultOut(BaseModel):
    account_email: str
    candidates: int
    processed: int
    failed: int
