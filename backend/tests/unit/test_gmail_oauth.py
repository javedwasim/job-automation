import base64
import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from oauthlib.oauth2 import InvalidGrantError
from oauthlib.oauth2.rfc6749.tokens import OAuth2Token

import app.api.routes.gmail as gmail_routes
import app.gmail.oauth as gmail_oauth
from app.gmail.oauth import ExchangedTokens, build_authorization_url, exchange_code_for_tokens

_SETTINGS_STUB = SimpleNamespace(
    google_client_id="test-client-id",
    google_client_secret="test-client-secret",
    google_redirect_uri="http://localhost:8000/api/gmail/oauth/callback",
)


@pytest.fixture(autouse=True)
def oauth_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deterministic OAuth client config + a clean state store per test."""
    monkeypatch.setattr(gmail_oauth, "get_settings", lambda: _SETTINGS_STUB)
    gmail_routes._PENDING_STATES.clear()
    yield
    gmail_routes._PENDING_STATES.clear()


def _s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _query_param(url: str, name: str) -> str:
    return parse_qs(urlparse(url).query)[name][0]


_REQUESTED_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]


def _scope_changed_warning(granted_scopes: list[str]) -> Warning:
    """Recreate the Warning oauthlib *raises* when granted != requested scopes.

    Mirrors oauthlib.oauth2.rfc6749.parameters.validate_token_parameters,
    including the `.token` attribute requests-oauthlib relies on.
    """
    token = OAuth2Token(
        {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 3600,
            "scope": " ".join(granted_scopes),
        },
        old_scope=" ".join(_REQUESTED_SCOPES),
    )
    warning = Warning(f'Scope has changed from "{token.old_scope}" to "{token.scope}".')
    warning.token = token
    return warning


class _StubOAuthSession:
    """Stands in for requests_oauthlib.OAuth2Session (token attribute only)."""

    def __init__(self) -> None:
        self.token: dict[str, object] = {}


class _StubFlow:
    """Flow whose fetch_token raises oauthlib's scope-changed Warning."""

    def __init__(self, warning: Warning) -> None:
        self._warning = warning
        self.oauth2session = _StubOAuthSession()

    def fetch_token(self, code: str) -> None:
        raise self._warning

    @property
    def credentials(self) -> SimpleNamespace:
        return SimpleNamespace(
            token=self.oauth2session.token["access_token"],
            refresh_token=self.oauth2session.token.get("refresh_token"),
            expiry=datetime.now(UTC).replace(tzinfo=None),
        )


def test_build_authorization_url_binds_challenge_to_verifier() -> None:
    authorization_url, state, code_verifier = build_authorization_url()

    # PKCE verifier constraints (RFC 7636 section 4.1).
    assert 43 <= len(code_verifier) <= 128
    assert all(c.isalnum() or c in "-._~" for c in code_verifier)
    assert state

    # The consent URL must carry the S256 challenge derived from OUR verifier.
    assert _query_param(authorization_url, "code_challenge_method") == "S256"
    assert _query_param(authorization_url, "code_challenge") == _s256(code_verifier)
    # The verifier must never leak into the consent URL, and we must not ask
    # Google to re-attach historical grants (include_granted_scopes): that
    # violates least privilege and breaks oauthlib's strict
    # requested-vs-granted scope check.
    assert code_verifier not in authorization_url
    assert "include_granted_scopes" not in authorization_url


def test_exchange_code_for_tokens_requires_code_verifier() -> None:
    with pytest.raises(ValueError, match="code_verifier"):
        exchange_code_for_tokens(code="some-code")


def test_authorize_endpoint_stores_verifier_for_state(client: TestClient) -> None:
    response = client.get("/api/gmail/oauth/authorize")

    assert response.status_code == 200
    body = response.json()
    state = body["state"]
    stored_verifier = gmail_routes._PENDING_STATES[state][1]
    assert _s256(stored_verifier) == _query_param(body["authorization_url"], "code_challenge")
    # The verifier is never exposed through the API response.
    assert stored_verifier not in body["authorization_url"]


def test_exchange_accepts_superset_scope_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    granted = [*_REQUESTED_SCOPES, "https://www.googleapis.com/auth/gmail.modify"]
    flow = _StubFlow(_scope_changed_warning(granted))
    monkeypatch.setattr(gmail_oauth, "_build_flow", lambda **_: flow)
    monkeypatch.setattr(gmail_oauth, "_fetch_account_email", lambda _creds: "me@example.com")

    tokens = exchange_code_for_tokens(code="auth-code", state="state", code_verifier="v" * 43)

    # The token requests-oauthlib skipped assigning is rehydrated on the session.
    assert flow.oauth2session.token["access_token"] == "access-token"
    assert tokens.access_token == "access-token"
    assert tokens.refresh_token == "refresh-token"
    assert tokens.email == "me@example.com"
    assert tokens.token_expires_at.tzinfo is not None


def test_exchange_rejects_narrower_scope_grant(monkeypatch: pytest.MonkeyPatch) -> None:
    # gmail.readonly missing from the grant -> must fail loudly, not 500.
    granted = ["openid", "https://www.googleapis.com/auth/userinfo.email"]
    flow = _StubFlow(_scope_changed_warning(granted))
    monkeypatch.setattr(gmail_oauth, "_build_flow", lambda **_: flow)

    with pytest.raises(ValueError, match="narrower scope"):
        exchange_code_for_tokens(code="auth-code", state="state", code_verifier="v" * 43)


def test_callback_with_unknown_state_returns_400(client: TestClient) -> None:
    response = client.get("/api/gmail/oauth/callback", params={"code": "x", "state": "unknown"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired OAuth state"


def test_callback_replays_stored_code_verifier(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_exchange(
        code: str, state: str | None = None, code_verifier: str | None = None
    ) -> ExchangedTokens:
        captured.update(code=code, state=state, code_verifier=code_verifier)
        return ExchangedTokens(
            email="me@example.com",
            access_token="access-token",
            refresh_token="refresh-token",
            token_expires_at=datetime.now(UTC),
        )

    class FakeRepository:
        def __init__(self, db: object) -> None:
            self.db = db

        def upsert(self, **kwargs: object) -> SimpleNamespace:
            captured["upsert_email"] = kwargs["email"]
            return SimpleNamespace(
                id=1,
                email=kwargs["email"],
                connected_at=datetime.now(UTC),
                token_expires_at=datetime.now(UTC),
            )

    monkeypatch.setattr(gmail_routes, "exchange_code_for_tokens", fake_exchange)
    monkeypatch.setattr(gmail_routes, "GmailAccountRepository", FakeRepository)

    authorize_body = client.get("/api/gmail/oauth/authorize").json()
    stored_verifier = gmail_routes._PENDING_STATES[authorize_body["state"]][1]
    response = client.get(
        "/api/gmail/oauth/callback",
        params={"code": "auth-code", "state": authorize_body["state"]},
    )

    assert response.status_code == 200
    assert captured["code"] == "auth-code"
    assert captured["state"] == authorize_body["state"]
    # The verifier stored at authorize time is replayed at exchange time —
    # this is what prevents Google's "Missing code verifier" invalid_grant.
    assert captured["code_verifier"] == stored_verifier
    assert captured["upsert_email"] == "me@example.com"
    assert response.json()["email"] == "me@example.com"


def test_callback_maps_oauth_error_to_400(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing_exchange(
        code: str, state: str | None = None, code_verifier: str | None = None
    ) -> ExchangedTokens:
        raise InvalidGrantError(description="Missing code verifier.")

    monkeypatch.setattr(gmail_routes, "exchange_code_for_tokens", failing_exchange)

    state = client.get("/api/gmail/oauth/authorize").json()["state"]
    response = client.get("/api/gmail/oauth/callback", params={"code": "auth-code", "state": state})

    assert response.status_code == 400
    assert "Missing code verifier" in response.json()["detail"]
