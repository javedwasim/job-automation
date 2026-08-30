"""
Google OAuth 2.0 flow for connecting a Gmail account, scoped to
`gmail.readonly` only (spec sections 4 and 34 — "do not request
unnecessary Gmail permissions").
"""

import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app.config.settings import get_settings

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


@dataclass(frozen=True)
class ExchangedTokens:
    email: str
    access_token: str
    refresh_token: str
    token_expires_at: datetime


def _generate_code_verifier() -> str:
    """PKCE code_verifier per RFC 7636: 43-128 chars from the unreserved
    set. `secrets.token_urlsafe(64)` yields ~86 URL-safe characters."""
    return secrets.token_urlsafe(64)


def _build_flow(state: str | None = None, code_verifier: str | None = None) -> Flow:
    settings = get_settings()
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=[GMAIL_READONLY_SCOPE, "openid", "https://www.googleapis.com/auth/userinfo.email"],
        state=state,
        redirect_uri=settings.google_redirect_uri,
        code_verifier=code_verifier,
        # We own the verifier lifecycle: it is generated here, stashed
        # server-side with the state, and replayed in the callback. Turning
        # off autogeneration guarantees the challenge in the consent URL is
        # always derived from *our* verifier (autogeneration is also the
        # default in google-auth-oauthlib >= 1.4).
        autogenerate_code_verifier=False,
    )


def build_authorization_url() -> tuple[str, str, str]:
    """Returns (authorization_url, state, code_verifier).

    The consent URL carries a PKCE `code_challenge` (S256 of the verifier);
    Google refuses the token exchange unless the matching `code_verifier` is
    replayed — otherwise it fails with `invalid_grant: Missing code verifier`.
    The verifier must therefore be stashed server-side next to `state` and
    passed to `exchange_code_for_tokens()` when the callback arrives. It must
    never be sent to the client.
    """
    code_verifier = _generate_code_verifier()
    flow = _build_flow(code_verifier=code_verifier)
    # include_granted_scopes is deliberately NOT set: it makes Google append
    # every scope the account has ever granted to this client into the grant
    # (e.g. gmail.modify/compose from earlier experiments), which both
    # violates least privilege (spec sections 4/34) and trips oauthlib's
    # strict requested-vs-granted scope check ("Scope has changed" -> 500).
    authorization_url, state = flow.authorization_url(
        access_type="offline",  # required to receive a refresh_token
        prompt="consent",  # ensures a refresh_token is issued even on repeat consent
    )
    return authorization_url, state, code_verifier


def exchange_code_for_tokens(
    code: str, state: str | None = None, code_verifier: str | None = None
) -> ExchangedTokens:
    """Exchanges an OAuth authorization code for access/refresh tokens and
    the connected account's email address. `code_verifier` is the PKCE
    verifier stored with the state when `build_authorization_url()` ran."""
    if not code_verifier:
        raise ValueError(
            "Missing PKCE code_verifier for the OAuth callback. Restart the "
            "connection flow (the verifier is issued together with the state "
            "by /gmail/oauth/authorize)."
        )
    flow = _build_flow(state=state, code_verifier=code_verifier)
    try:
        flow.fetch_token(code=code)
    except Warning as exc:
        # oauthlib *raises* a Warning (not an error) when the scopes Google
        # granted differ from the requested ones — and requests-oauthlib
        # never assigns the parsed token in that case. Accept the grant when
        # it covers everything we asked for (e.g. Google re-attaching scopes
        # the account already holds, or scope aliases like `email` vs
        # `.../userinfo.email`); fail loudly when anything is missing.
        token_params = getattr(exc, "token", None)
        missing = (
            list(getattr(token_params, "missing_scopes", None) or [])
            if token_params is not None
            else ["<grant could not be parsed>"]
        )
        if missing:
            raise ValueError(
                "Google granted a narrower scope than requested. Reconnect and "
                f"approve all requested permissions ({exc})"
            ) from exc
        # Superset grant: rehydrate the session token that requests-oauthlib
        # skipped assigning, then continue down the normal credentials path.
        # flow.credentials requires `expires_at`; the parse path normally adds
        # it from `expires_in`, but guard anyway so rehydration can't KeyError.
        token = dict(token_params)
        if token.get("expires_at") is None and token.get("expires_in") is not None:
            token["expires_at"] = time.time() + int(token["expires_in"])
        flow.oauth2session.token = token
    credentials = flow.credentials

    if not credentials.refresh_token:
        raise ValueError(
            "Google did not return a refresh_token. This happens if the user has "
            "already granted consent before without revoking it — have them revoke "
            "access at https://myaccount.google.com/permissions and reconnect."
        )

    email = _fetch_account_email(credentials)

    expires_at = credentials.expiry
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    return ExchangedTokens(
        email=email,
        access_token=credentials.token,
        refresh_token=credentials.refresh_token,
        token_expires_at=expires_at or datetime.now(UTC),
    )


def _fetch_account_email(credentials: Credentials) -> str:
    from googleapiclient.discovery import build

    oauth2_service = build("oauth2", "v2", credentials=credentials, cache_discovery=False)
    userinfo = oauth2_service.userinfo().get().execute()
    email = userinfo.get("email")
    if not email:
        raise ValueError("Could not determine the connected account's email address")
    return email


def refresh_access_token(refresh_token: str) -> tuple[str, datetime]:
    """Returns (new_access_token, new_expiry) using a stored refresh_token."""
    settings = get_settings()
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=[GMAIL_READONLY_SCOPE],
    )
    request = _google_auth_request()
    credentials.refresh(request)
    expiry = credentials.expiry
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    return credentials.token, expiry or datetime.now(UTC)


def _google_auth_request():
    from google.auth.transport.requests import Request

    return Request()
