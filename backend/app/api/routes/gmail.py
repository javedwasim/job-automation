import time

from fastapi import APIRouter, Depends, HTTPException
from oauthlib.oauth2 import OAuth2Error
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from app.config.settings import get_settings
from app.database.session import get_db
from app.gmail.oauth import build_authorization_url, exchange_code_for_tokens
from app.gmail.service import GmailIngestionService
from app.repositories.gmail_account_repository import GmailAccountRepository
from app.repositories.job_email_repository import JobEmailRepository
from app.schemas.gmail import (
    AuthorizationUrlOut,
    BackfillResultOut,
    GmailAccountOut,
    JobEmailOut,
    SyncResultOut,
)

router = APIRouter(prefix="/gmail", tags=["gmail"])

# In-memory OAuth state + PKCE code_verifier store, single-process only.
# Move to Redis before running multiple API workers (tracked for the Phase 8
# security audit).
_PENDING_STATES: dict[str, tuple[float, str]] = {}
_STATE_TTL_SECONDS = 600


def _remember_state(state: str, code_verifier: str) -> None:
    _PENDING_STATES[state] = (time.time(), code_verifier)


def _consume_state(state: str) -> str | None:
    """Pops the stored entry and returns its PKCE code_verifier, or None when
    the state is unknown or expired."""
    entry = _PENDING_STATES.pop(state, None)
    if entry is None:
        return None
    issued_at, code_verifier = entry
    if (time.time() - issued_at) > _STATE_TTL_SECONDS:
        return None
    return code_verifier


@router.get("/oauth/authorize", response_model=AuthorizationUrlOut)
def gmail_oauth_authorize() -> AuthorizationUrlOut:
    """Returns the Google consent URL for the dashboard to redirect the user to."""
    authorization_url, state, code_verifier = build_authorization_url()
    _remember_state(state, code_verifier)
    return AuthorizationUrlOut(authorization_url=authorization_url, state=state)


@router.get("/oauth/callback", response_model=GmailAccountOut)
def gmail_oauth_callback(code: str, state: str, db: Session = Depends(get_db)) -> GmailAccountOut:
    """Google redirects here after the user grants (or denies) consent.
    
    Returns account info as JSON. The frontend can poll /gmail/accounts after
    detecting it's been redirected here to fetch the newly connected account.
    """
    code_verifier = _consume_state(state)
    if code_verifier is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    try:
        tokens = exchange_code_for_tokens(code=code, state=state, code_verifier=code_verifier)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OAuth2Error as exc:
        # InvalidGrantError ("Missing code verifier"), MismatchingStateError,
        # MissingCodeError, ... — Google-side rejections become 400s instead
        # of unhandled 500s.
        raise HTTPException(status_code=400, detail=f"OAuth token exchange failed: {exc}") from exc

    accounts = GmailAccountRepository(db)
    account = accounts.upsert(
        user_id=1,  # single-user for now; multi-user auth is out of scope for this phase
        email=tokens.email,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_expires_at=tokens.token_expires_at,
    )
    return GmailAccountOut.model_validate(account)


@router.get("/accounts", response_model=list[GmailAccountOut])
def list_gmail_accounts(db: Session = Depends(get_db)) -> list[GmailAccountOut]:
    accounts = GmailAccountRepository(db).list_all()
    return [GmailAccountOut.model_validate(a) for a in accounts]


@router.post("/sync", response_model=list[SyncResultOut])
def sync_gmail(db: Session = Depends(get_db)) -> list[SyncResultOut]:
    """Manually triggers ingestion for every connected account. The
    scheduled version of this runs as a Celery Beat task (Phase 8)."""
    service = GmailIngestionService(db)
    results = service.sync_all_accounts()
    return [SyncResultOut(**r.__dict__) for r in results]


@router.get("/emails", response_model=list[JobEmailOut])
def list_job_emails(limit: int = 50, db: Session = Depends(get_db)) -> list[JobEmailOut]:
    """Lets the dashboard show discovered emails (spec section 30/Phase 1
    verification: 'Display discovered emails')."""
    emails = JobEmailRepository(db).list_recent(limit=limit)
    return [JobEmailOut.model_validate(e) for e in emails]


@router.post("/backfill", response_model=list[BackfillResultOut])
def backfill_jobs(db: Session = Depends(get_db)) -> list[BackfillResultOut]:
    """Re-fetches and reprocesses any already-ingested emails that never
    produced a Job row — e.g. ones synced before the extraction/
    classification pipeline existed. Safe to call repeatedly; emails that
    already have a Job are skipped."""
    service = GmailIngestionService(db)
    results = service.backfill_all_accounts()
    return [BackfillResultOut(**r.__dict__) for r in results]
