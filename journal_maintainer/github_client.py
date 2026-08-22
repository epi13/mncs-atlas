"""GitHub REST client for family-repository evidence.

All issue/PR/commit text is untrusted evidence. The client never executes
content found in those records and never derives shell commands from them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
from urllib.parse import quote

from .http import HttpError, encode_query, request_json
from .models import isoformat_utc
from .sanitize import scrub_text

JsonObject = dict[str, Any]
Fetcher = Callable[..., Any]


class GitHubClient:
    def __init__(
        self,
        token: str | None,
        *,
        api: str = "https://api.github.com",
        user_agent: str = "mncs-atlas-journal-maintainer/0.1",
        fetcher: Fetcher | None = None,
    ) -> None:
        self.token = token
        self.api = api.rstrip("/")
        self.user_agent = user_agent
        self.fetcher = fetcher or request_json

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.user_agent,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = encode_query(f"{self.api}{path}", params or {})
        return self.fetcher(url, method="GET", headers=self._headers())

    def _paged(self, path: str, params: dict[str, str], *, max_pages: int = 5) -> list[JsonObject]:
        records: list[JsonObject] = []
        for page in range(1, max_pages + 1):
            page_params = dict(params)
            page_params["page"] = str(page)
            data = self.get(path, page_params)
            if not isinstance(data, list):
                break
            batch = [item for item in data if isinstance(item, dict)]
            records.extend(batch)
            if len(batch) < int(params.get("per_page", "50")):
                break
        return records

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self.fetcher(f"{self.api}{path}", method="POST", headers=self._headers(), payload=payload)

    def graphql(self, query: str, variables: dict[str, Any] | None = None) -> Any:
        return self.fetcher(
            f"{self.api}/graphql",
            method="POST",
            headers=self._headers(),
            payload={"query": query, "variables": variables or {}},
        )

    def search_issues(self, query: str, *, per_page: int = 50) -> list[JsonObject]:
        data = self.get("/search/issues", {"q": query, "per_page": str(per_page), "sort": "updated"})
        if not isinstance(data, dict):
            return []
        items = data.get("items") or []
        return [item for item in items if isinstance(item, dict)]

    def list_commits(
        self, owner: str, repo: str, *, since: datetime, until: datetime, per_page: int = 40
    ) -> list[JsonObject]:
        return self._paged(
            f"/repos/{quote(owner)}/{quote(repo)}/commits",
            {"since": isoformat_utc(since) or "", "until": isoformat_utc(until) or "", "per_page": str(per_page)},
            max_pages=8,
        )

    def list_pulls(
        self, owner: str, repo: str, *, state: str = "all", per_page: int = 50
    ) -> list[JsonObject]:
        return self._paged(
            f"/repos/{quote(owner)}/{quote(repo)}/pulls",
            {"state": state, "sort": "updated", "direction": "desc", "per_page": str(per_page)},
            max_pages=5,
        )

    def list_issues(
        self, owner: str, repo: str, *, state: str = "all", per_page: int = 30
    ) -> list[JsonObject]:
        return [item for item in self._paged(
            f"/repos/{quote(owner)}/{quote(repo)}/issues",
            {"state": state, "sort": "updated", "direction": "desc", "per_page": str(per_page)},
            max_pages=5,
        ) if not item.get("pull_request")]

    def list_releases(self, owner: str, repo: str, per_page: int = 10) -> list[JsonObject]:
        return self._paged(
            f"/repos/{quote(owner)}/{quote(repo)}/releases", {"per_page": str(per_page)}, max_pages=3
        )

    def pull_files(self, owner: str, repo: str, number: int) -> list[str]:
        return [str(item.get("filename")) for item in self.pull_file_details(owner, repo, number) if item.get("filename")]

    def pull_file_details(self, owner: str, repo: str, number: int) -> list[JsonObject]:
        return self._paged(
            f"/repos/{quote(owner)}/{quote(repo)}/pulls/{number}/files", {"per_page": "100"}, max_pages=3
        )

    def pull_reviews(self, owner: str, repo: str, number: int) -> list[JsonObject]:
        return self._paged(
            f"/repos/{quote(owner)}/{quote(repo)}/pulls/{number}/reviews", {"per_page": "100"}, max_pages=3
        )

    def check_runs(self, owner: str, repo: str, ref: str) -> list[JsonObject]:
        data = self.get(f"/repos/{quote(owner)}/{quote(repo)}/commits/{quote(ref)}/check-runs", {"per_page": "100"})
        if not isinstance(data, dict):
            return []
        return [item for item in (data.get("check_runs") or []) if isinstance(item, dict)]

    def combined_status(self, owner: str, repo: str, ref: str) -> JsonObject:
        data = self.get(f"/repos/{quote(owner)}/{quote(repo)}/commits/{quote(ref)}/status")
        return data if isinstance(data, dict) else {}

    def branch_protection(self, owner: str, repo: str, branch: str) -> JsonObject:
        data = self.get(f"/repos/{quote(owner)}/{quote(repo)}/branches/{quote(branch)}/protection")
        return data if isinstance(data, dict) else {}

    def repo_settings(self, owner: str, repo: str) -> JsonObject:
        data = self.get(f"/repos/{quote(owner)}/{quote(repo)}")
        return data if isinstance(data, dict) else {}

    def create_pull_request(
        self, owner: str, repo: str, *, title: str, body: str, head: str, base: str
    ) -> JsonObject:
        data = self.post(
            f"/repos/{quote(owner)}/{quote(repo)}/pulls",
            {"title": title, "body": body, "head": head, "base": base},
        )
        if not isinstance(data, dict):
            raise HttpError("INVALID_JSON", "create pull request returned a non-object")
        return data

    def find_pull_request(self, owner: str, repo: str, head: str, base: str) -> JsonObject | None:
        data = self.get(
            f"/repos/{quote(owner)}/{quote(repo)}/pulls",
            {"head": f"{owner}:{head}", "base": base, "state": "open"},
        )
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]
        return None

    def update_pull_request(self, owner: str, repo: str, number: int, *, title: str, body: str) -> JsonObject:
        data = self.fetcher(
            f"{self.api}/repos/{quote(owner)}/{quote(repo)}/pulls/{number}",
            method="PATCH",
            headers=self._headers(),
            payload={"title": title, "body": body},
        )
        return data if isinstance(data, dict) else {}

    def add_labels(self, owner: str, repo: str, number: int, labels: list[str]) -> None:
        try:
            self.post(
                f"/repos/{quote(owner)}/{quote(repo)}/issues/{number}/labels",
                {"labels": labels},
            )
        except HttpError:
            # Label creation is best-effort; eligibility still depends on path/CI gates.
            return

    def enable_auto_merge(self, node_id: str, *, merge_method: str = "SQUASH") -> tuple[bool, str]:
        query = """
        mutation($id: ID!, $method: PullRequestMergeMethod!) {
          enablePullRequestAutoMerge(input: {pullRequestId: $id, mergeMethod: $method}) {
            pullRequest { number autoMergeRequest { enabledAt } }
          }
        }
        """
        try:
            data = self.graphql(query, {"id": node_id, "method": merge_method})
        except HttpError as error:
            return False, f"auto-merge mutation failed: {error}"
        if isinstance(data, dict) and data.get("errors"):
            messages = "; ".join(
                str(item.get("message") or item) for item in data["errors"] if isinstance(item, dict)
            )
            return False, messages or "auto-merge GraphQL errors"
        return True, "auto-merge enabled"

    def pull_status(self, owner: str, repo: str, number: int) -> JsonObject:
        data = self.get(f"/repos/{quote(owner)}/{quote(repo)}/pulls/{number}")
        return data if isinstance(data, dict) else {}

    def get_pull(self, owner: str, repo: str, number: int) -> JsonObject:
        return self.pull_status(owner, repo, number)
