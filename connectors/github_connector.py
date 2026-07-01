"""GitHub connector: surfaces the user's open issues/PRs and repo status."""

import re
from typing import Any, Dict, Tuple

import httpx

from config.settings import settings
from connectors.base import Connector
from utils.logger import logger

_KEYWORDS = ("github", "issue", "pull request", " pr ", " prs", "repo")
_REPO_PATTERN = re.compile(r"\b[\w.-]+/[\w.-]+\b")


class GitHubConnector(Connector):
    """Fetches open PRs, assigned issues, and repo status from the GitHub API."""

    name = "github"
    _BASE_URL = "https://api.github.com"

    def is_configured(self) -> bool:
        return bool(settings.github_token)

    def should_handle(self, query: str) -> bool:
        q = f" {query.lower()} "
        return any(kw in q for kw in _KEYWORDS) or bool(_REPO_PATTERN.search(query))

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.github_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10.0,
        )

    def fetch_context(self, query: str) -> Tuple[str, Dict[str, Any]]:
        try:
            with self._client() as client:
                repo_match = _REPO_PATTERN.search(query)
                if repo_match:
                    text = self._repo_status(client, repo_match.group(0))
                else:
                    text = self._my_activity(client)

            return text, {"platform": "github", "title": "GitHub"}
        except Exception as e:
            logger.exception(f"GitHub connector failed: {e}")
            return (
                f"[Source: GITHUB]\nCould not reach GitHub API: {e}",
                {"platform": "github", "title": "GitHub (error)"},
            )

    def _my_activity(self, client: httpx.Client) -> str:
        user_resp = client.get("/user")
        if user_resp.status_code == 401:
            return "[Source: GITHUB]\nGitHub token is invalid or expired. Update GITHUB_TOKEN and retry."
        user_resp.raise_for_status()
        user = user_resp.json()["login"]

        prs_resp = client.get(
            "/search/issues", params={"q": f"is:open is:pr author:{user}"}
        )
        prs_resp.raise_for_status()
        prs = prs_resp.json()

        issues_resp = client.get(
            "/search/issues", params={"q": f"is:open is:issue assignee:{user}"}
        )
        issues_resp.raise_for_status()
        issues = issues_resp.json()

        pr_lines = [f"- {i['title']} ({i['html_url']})" for i in prs.get("items", [])[:10]]
        issue_lines = [f"- {i['title']} ({i['html_url']})" for i in issues.get("items", [])[:10]]

        return (
            f"[Source: GITHUB - {user}]\n"
            f"Open pull requests ({prs.get('total_count', 0)}):\n"
            + ("\n".join(pr_lines) or "(none)")
            + f"\n\nOpen issues assigned to you ({issues.get('total_count', 0)}):\n"
            + ("\n".join(issue_lines) or "(none)")
        )

    def _repo_status(self, client: httpx.Client, repo: str) -> str:
        repo_resp = client.get(f"/repos/{repo}")
        if repo_resp.status_code == 404:
            return f"[Source: GITHUB]\nRepo '{repo}' not found or not accessible."
        repo_resp.raise_for_status()
        repo_data = repo_resp.json()

        open_prs_resp = client.get(
            "/search/issues", params={"q": f"is:open is:pr repo:{repo}"}
        )
        open_prs_resp.raise_for_status()
        pr_count = open_prs_resp.json().get("total_count", 0)

        # GitHub's open_issues_count counts issues AND pull requests together;
        # subtract the PR count to report issues-only, matching the PR line below.
        issue_count = max(repo_data.get("open_issues_count", 0) - pr_count, 0)

        return (
            f"[Source: GITHUB - {repo}]\n"
            f"{repo_data.get('description') or '(no description)'}\n"
            f"Open issues: {issue_count}\n"
            f"Open pull requests: {pr_count}\n"
            f"Default branch: {repo_data.get('default_branch')}\n"
            f"URL: {repo_data.get('html_url')}"
        )
