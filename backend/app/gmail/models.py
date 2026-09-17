from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class GmailAccount(Base):
    """A connected Gmail account. Tokens are stored encrypted (see
    app.security.token_encryption) and must never be exposed via the API.
    """

    __tablename__ = "gmail_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    access_token_encrypted: Mapped[str] = mapped_column(String(2048), nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(String(2048), nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Gmail history ID — reserved for incremental sync in a later hardening pass.
    history_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"<GmailAccount id={self.id} email={self.email}>"
