"""
Thin wrapper around the Gmail API (spec section 19 — GmailClient
responsibilities: search, retrieve, extract, apply label).

Credential refresh is handled by the caller (GmailIngestionService) so this
class stays a dumb, testable transport layer.
"""

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build

from app.gmail.oauth import GMAIL_READONLY_SCOPE


class GmailClient:
    def __init__(self, access_token: str) -> None:
        credentials = Credentials(token=access_token, scopes=[GMAIL_READONLY_SCOPE])
        self._service: Resource = build(
            "gmail", "v1", credentials=credentials, cache_discovery=False
        )

    def search_message_ids(self, query: str, max_results: int = 100) -> list[str]:
        """Returns Gmail message IDs matching `query`, paginating as needed.
        Never loads the whole mailbox — the query itself scopes the window
        (spec section 21)."""
        message_ids: list[str] = []
        page_token: str | None = None

        while True:
            request = (
                self._service.users()
                .messages()
                .list(userId="me", q=query, pageToken=page_token, maxResults=max_results)
            )
            response = request.execute()
            message_ids.extend(m["id"] for m in response.get("messages", []))

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return message_ids

    def get_message(self, message_id: str) -> dict:
        """Returns the full raw Gmail message payload for normalization."""
        return (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

    def ensure_label(self, label_name: str) -> str:
        """Returns the label ID for `label_name`, creating it if it doesn't
        already exist."""
        labels = self._service.users().labels().list(userId="me").execute().get("labels", [])
        for label in labels:
            if label["name"] == label_name:
                return label["id"]

        created = (
            self._service.users()
            .labels()
            .create(
                userId="me",
                body={
                    "name": label_name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        return created["id"]

    def apply_label(self, message_id: str, label_id: str) -> None:
        self._service.users().messages().modify(
            userId="me", id=message_id, body={"addLabelIds": [label_id]}
        ).execute()


def build_lookback_query(
    lookback_hours: int,
    excluded_domains: list[str] | None = None,
    gmail_category: str = "updates",
) -> str:
    """Builds a Gmail search query scoped to the configured lookback window
    and Gmail's own update-notifications category (where job alerts land) —
    deliberately NOT restricted to a sender-domain whitelist, so job alerts
    from any platform are found (spec sections 20-21). `excluded_domains`
    become `-from:` negations so unwanted sources (e.g. glassdoor.com) never
    even surface in the search results.
    """
    import time

    after_epoch_seconds = int(time.time() - lookback_hours * 3600)
    query = f"after:{after_epoch_seconds}"

    if gmail_category:
        query = f"{query} category:{gmail_category}"

    for domain in excluded_domains or []:
        query = f"{query} -from:{domain}"

    return query
