"""Tests for connectors/github_connector.py, mocking the GitHub REST API."""

from unittest.mock import MagicMock, patch

from connectors.github_connector import GitHubConnector


def make_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status.return_value = None
    return resp


def test_is_configured_reflects_settings_token():
    connector = GitHubConnector()
    with patch("connectors.github_connector.settings") as mock_settings:
        mock_settings.github_token = "tok"
        assert connector.is_configured() is True
        mock_settings.github_token = None
        assert connector.is_configured() is False


def test_tool_specs_shape():
    connector = GitHubConnector()
    specs = connector.tool_specs()
    names = {s["name"] for s in specs}
    assert names == {"get_my_github_activity", "get_github_repo_status"}
    repo_spec = next(s for s in specs if s["name"] == "get_github_repo_status")
    assert repo_spec["parameters"]["required"] == ["repo"]


def test_call_tool_my_activity():
    connector = GitHubConnector()
    user_resp = make_response(200, {"login": "octocat"})
    prs_resp = make_response(200, {"total_count": 1, "items": [{"title": "Fix bug", "html_url": "http://pr"}]})
    issues_resp = make_response(200, {"total_count": 0, "items": []})

    mock_client = MagicMock()
    mock_client.get.side_effect = [user_resp, prs_resp, issues_resp]
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False

    with patch.object(connector, "_client", return_value=mock_client):
        text, source = connector.call_tool("get_my_github_activity", {})

    assert "octocat" in text
    assert "Fix bug" in text
    assert source == {"platform": "github", "title": "GitHub"}


def test_call_tool_repo_status_subtracts_pr_count_from_issue_count():
    connector = GitHubConnector()
    repo_resp = make_response(200, {
        "description": "A test repo",
        "open_issues_count": 5,
        "default_branch": "main",
        "html_url": "http://repo",
    })
    prs_resp = make_response(200, {"total_count": 2})

    mock_client = MagicMock()
    mock_client.get.side_effect = [repo_resp, prs_resp]
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False

    with patch.object(connector, "_client", return_value=mock_client):
        text, source = connector.call_tool("get_github_repo_status", {"repo": "octocat/hello-world"})

    assert "Open issues: 3" in text  # 5 - 2, not the raw 5
    assert "Open pull requests: 2" in text
    assert source == {"platform": "github", "title": "GitHub"}


def test_call_tool_repo_status_missing_repo_argument():
    connector = GitHubConnector()
    text, source = connector.call_tool("get_github_repo_status", {})
    assert "specify a repo" in text.lower()
    assert source["title"] == "GitHub (missing argument)"


def test_call_tool_invalid_token():
    connector = GitHubConnector()
    user_resp = make_response(401, {})

    mock_client = MagicMock()
    mock_client.get.side_effect = [user_resp]
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False

    with patch.object(connector, "_client", return_value=mock_client):
        text, source = connector.call_tool("get_my_github_activity", {})

    assert "invalid or expired" in text.lower()


def test_call_tool_repo_not_found():
    connector = GitHubConnector()
    repo_resp = make_response(404, {})

    mock_client = MagicMock()
    mock_client.get.side_effect = [repo_resp]
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = False

    with patch.object(connector, "_client", return_value=mock_client):
        text, source = connector.call_tool("get_github_repo_status", {"repo": "a/b"})

    assert "not found" in text.lower()


def test_call_tool_unexpected_error_returns_error_source():
    connector = GitHubConnector()
    with patch.object(connector, "_client", side_effect=RuntimeError("network down")):
        text, source = connector.call_tool("get_my_github_activity", {})

    assert "Could not reach GitHub API" in text
    assert source["title"] == "GitHub (error)"
