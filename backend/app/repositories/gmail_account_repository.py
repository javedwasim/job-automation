from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.gmail.models import GmailAccount
from app.security.token_encryption import decrypt_token, encrypt_token


class GmailAccountRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_email(self, email: str) -> GmailAccount | None:
        return self._db.scalar(select(GmailAccount).where(GmailAccount.email == email))

    def get_by_id(self, account_id: int) -> GmailAccount | None:
        return self._db.get(GmailAccount, account_id)

    def list_all(self) -> list[GmailAccount]:
        return list(self._db.scalars(select(GmailAccount)))

    def upsert(
        self,
        *,
        user_id: int,
        email: str,
        access_token: str,
        refresh_token: str,
        token_expires_at: datetime,
    ) -> GmailAccount:
        """Creates or updates the account, encrypting tokens before storage.
        Never store or return a plaintext token beyond this call."""
        now = datetime.now(UTC)
        account = self.get_by_email(email)

        if account is None:
            account = GmailAccount(
                user_id=user_id,
                email=email,
                access_token_encrypted=encrypt_token(access_token),
                refresh_token_encrypted=encrypt_token(refresh_token),
                token_expires_at=token_expires_at,
                connected_at=now,
                created_at=now,
                updated_at=now,
            )
            self._db.add(account)
        else:
            account.access_token_encrypted = encrypt_token(access_token)
            account.refresh_token_encrypted = encrypt_token(refresh_token)
            account.token_expires_at = token_expires_at
            account.updated_at = now

        self._db.commit()
        self._db.refresh(account)
        return account

    def update_access_token(
        self, account: GmailAccount, access_token: str, expires_at: datetime
    ) -> None:
        account.access_token_encrypted = encrypt_token(access_token)
        account.token_expires_at = expires_at
        account.updated_at = datetime.now(UTC)
        self._db.commit()

    @staticmethod
    def decrypt_access_token(account: GmailAccount) -> str:
        return decrypt_token(account.access_token_encrypted)

    @staticmethod
    def decrypt_refresh_token(account: GmailAccount) -> str:
        return decrypt_token(account.refresh_token_encrypted)
