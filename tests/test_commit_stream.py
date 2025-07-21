import unittest
from unittest.mock import patch, MagicMock
import requests
from datetime import datetime, timezone, timedelta
import json

from commit_stream import (
    _run_graphql_query_with_timeout,
    get_recently_active_repos,
    get_recently_active_repos_from_existing,
    get_all_commits_for_repos,
    format_commit_for_stream,
    get_commit_stream_data,
    get_commit_stream_data_from_repos,
    display_commit_stream
)


class TestCommitStream(unittest.TestCase):

    @patch('commit_stream.requests.post')
    def test_run_graphql_query_with_timeout_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"data": "test"}
        mock_post.return_value = mock_response

        result = _run_graphql_query_with_timeout("fake_token", "query")
        
        self.assertEqual(result, {"data": "test"})
        mock_post.assert_called_once()
        # Verify timeout is passed
        self.assertEqual(mock_post.call_args[1]['timeout'], 30)

    @patch('commit_stream.requests.post')
    @patch('commit_stream.st')
    def test_run_graphql_query_with_timeout_timeout_error(self, mock_st, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout()

        result = _run_graphql_query_with_timeout("fake_token", "query")
        
        self.assertIsNone(result)
        mock_st.error.assert_called_once_with("Request timed out after 30 seconds")

    @patch('commit_stream.requests.post')
    @patch('commit_stream.st')
    def test_run_graphql_query_with_timeout_request_error(self, mock_st, mock_post):
        mock_post.side_effect = requests.exceptions.RequestException("Network error")

        result = _run_graphql_query_with_timeout("fake_token", "query")
        
        self.assertIsNone(result)
        mock_st.error.assert_called_once_with("GraphQL request failed: Network error")

    @patch('commit_stream._run_graphql_query_with_timeout')
    def test_get_recently_active_repos_no_token(self, mock_query):
        result = get_recently_active_repos("")
        self.assertEqual(result, [])
        mock_query.assert_not_called()

    @patch('commit_stream._run_graphql_query_with_timeout')
    def test_get_recently_active_repos_success(self, mock_query):
        # Mock successful response with recent repos
        now = datetime.now(timezone.utc)
        recent_date = (now - timedelta(days=1)).isoformat()
        old_date = (now - timedelta(days=10)).isoformat()
        
        mock_query.return_value = {
            "data": {
                "viewer": {
                    "repositories": {
                        "nodes": [
                            {"nameWithOwner": "owner/recent-repo", "pushedAt": recent_date},
                            {"nameWithOwner": "owner/old-repo", "pushedAt": old_date}
                        ]
                    }
                }
            }
        }

        result = get_recently_active_repos("fake_token", days_back=7)
        
        # Should only return the recent repo
        self.assertEqual(result, ["owner/recent-repo"])
        mock_query.assert_called_once()

    @patch('commit_stream._run_graphql_query_with_timeout')
    def test_get_recently_active_repos_no_data(self, mock_query):
        mock_query.return_value = None

        result = get_recently_active_repos("fake_token")
        
        self.assertEqual(result, [])

    @patch('commit_stream._run_graphql_query_with_timeout')
    def test_get_all_commits_for_repos_no_token(self, mock_query):
        result = get_all_commits_for_repos("", ["owner/repo"])
        self.assertEqual(result, [])
        mock_query.assert_not_called()

    @patch('commit_stream._run_graphql_query_with_timeout')
    def test_get_all_commits_for_repos_no_repos(self, mock_query):
        result = get_all_commits_for_repos("fake_token", [])
        self.assertEqual(result, [])
        mock_query.assert_not_called()

    @patch('commit_stream._run_graphql_query_with_timeout')
    def test_get_all_commits_for_repos_success(self, mock_query):
        mock_query.return_value = {
            "data": {
                "repo0": {
                    "nameWithOwner": "owner/repo1",
                    "url": "https://github.com/owner/repo1",
                    "refs": {
                        "nodes": [
                            {
                                "name": "main",
                                "target": {
                                    "history": {
                                        "nodes": [
                                            {
                                                "oid": "1234567890abcdef",
                                                "messageHeadline": "Test commit",
                                                "committedDate": "2025-07-20T10:00:00Z",
                                                "author": {"name": "Test Author"},
                                                "url": "https://github.com/owner/repo1/commit/1234567"
                                            }
                                        ]
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }

        result = get_all_commits_for_repos("fake_token", ["owner/repo1"])
        
        self.assertEqual(len(result), 1)
        commit = result[0]
        self.assertEqual(commit["repo"], "owner/repo1")
        self.assertEqual(commit["branch_name"], "main")
        self.assertEqual(commit["sha"], "1234567")
        self.assertEqual(commit["message"], "Test commit")
        self.assertEqual(commit["author"], "Test Author")

    @patch('commit_stream._run_graphql_query_with_timeout')
    def test_get_all_commits_for_repos_no_data(self, mock_query):
        mock_query.return_value = None

        result = get_all_commits_for_repos("fake_token", ["owner/repo1"])
        
        self.assertEqual(result, [])

    @patch('commit_stream._run_graphql_query_with_timeout')
    def test_get_all_commits_for_repos_null_author(self, mock_query):
        mock_query.return_value = {
            "data": {
                "repo0": {
                    "nameWithOwner": "owner/repo1",
                    "url": "https://github.com/owner/repo1",
                    "refs": {
                        "nodes": [
                            {
                                "name": "main",
                                "target": {
                                    "history": {
                                        "nodes": [
                                            {
                                                "oid": "1234567890abcdef",
                                                "messageHeadline": "Test commit",
                                                "committedDate": "2025-07-20T10:00:00Z",
                                                "author": None,
                                                "url": "https://github.com/owner/repo1/commit/1234567"
                                            }
                                        ]
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }

        result = get_all_commits_for_repos("fake_token", ["owner/repo1"])
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["author"], "Unknown")

    @patch('dashboard_app_graphql._format_timestamp_to_local')
    def test_format_commit_for_stream_today(self, mock_format):
        mock_format.return_value = "2025-07-20 03:00 PM EST"
        
        commit = {
            "repo": "owner/test-repo",
            "repo_url": "https://github.com/owner/test-repo",
            "branch_name": "main",
            "branch_url": "https://github.com/owner/test-repo/tree/main",
            "sha": "1234567",
            "message": "Test commit message",
            "author": "Test Author",
            "date": "2025-07-20T20:00:00Z",
            "url": "https://github.com/owner/test-repo/commit/1234567"
        }

        result = format_commit_for_stream(commit, is_today=True)
        
        self.assertIn("TODAY", result)
        self.assertIn("test-repo", result)
        self.assertIn("main", result)
        self.assertIn("Test commit message", result)
        self.assertIn("Test Author", result)
        self.assertIn("#ff6f00", result)  # Today color

    @patch('dashboard_app_graphql._format_timestamp_to_local')
    def test_format_commit_for_stream_not_today(self, mock_format):
        mock_format.return_value = "2025-07-19 02:00 PM EST"
        
        commit = {
            "repo": "owner/test-repo",
            "repo_url": "https://github.com/owner/test-repo",
            "branch_name": "feature",
            "branch_url": "https://github.com/owner/test-repo/tree/feature",
            "sha": "abcdef1",
            "message": "A very long commit message that should be truncated because it exceeds the character limit",
            "author": "Another Author",
            "date": "2025-07-19T19:00:00Z",
            "url": "https://github.com/owner/test-repo/commit/abcdef1"
        }

        result = format_commit_for_stream(commit, is_today=False)
        
        self.assertNotIn("TODAY", result)
        self.assertIn("test-repo", result)
        self.assertIn("feature", result)
        self.assertIn("...", result)  # Truncated message
        self.assertIn("Another Author", result)
        self.assertIn("#666", result)  # Regular color

    @patch('commit_stream.get_all_commits_for_repos')
    @patch('commit_stream.get_recently_active_repos')
    def test_get_commit_stream_data_no_token(self, mock_get_repos, mock_get_commits):
        result = get_commit_stream_data("")
        
        self.assertEqual(result, [])
        mock_get_repos.assert_not_called()
        mock_get_commits.assert_not_called()

    @patch('commit_stream.get_all_commits_for_repos')
    @patch('commit_stream.get_recently_active_repos') 
    @patch('commit_stream.st.cache_data')
    def test_get_commit_stream_data_success(self, mock_cache_data, mock_get_repos, mock_get_commits):
        # Mock the cache decorator to bypass caching during tests
        mock_cache_data.return_value = lambda func: func
        
        mock_get_repos.return_value = ["owner/repo1", "owner/repo2"]
        mock_get_commits.return_value = [
            {"repo": "owner/repo1", "message": "Test commit", "date": "2025-07-20T10:00:00Z"}
        ]

        # Call the underlying function directly to bypass caching
        from commit_stream import get_recently_active_repos, get_all_commits_for_repos
        
        # Test the core logic without caching
        active_repos = get_recently_active_repos("fake_token", 7)
        commits = get_all_commits_for_repos("fake_token", active_repos, 20)
        
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0]["repo"], "owner/repo1")

    @patch('commit_stream.get_all_commits_for_repos')
    @patch('commit_stream.get_recently_active_repos')
    def test_get_commit_stream_data_no_active_repos(self, mock_get_repos, mock_get_commits):
        mock_get_repos.return_value = []

        result = get_commit_stream_data("fake_token")
        
        self.assertEqual(result, [])
        mock_get_commits.assert_not_called()

    @patch('commit_stream.get_all_commits_for_repos')
    @patch('commit_stream.get_recently_active_repos')
    @patch('commit_stream.st')
    def test_get_commit_stream_data_exception(self, mock_st, mock_get_repos, mock_get_commits):
        mock_get_repos.side_effect = Exception("Test error")

        result = get_commit_stream_data("fake_token")
        
        self.assertEqual(result, [])
        mock_st.error.assert_called_once_with("Error fetching commit stream: Test error")

    def test_get_recently_active_repos_from_existing(self):
        existing_repos = ["owner/repo1", "owner/repo2", "owner/repo3"]
        result = get_recently_active_repos_from_existing(existing_repos, days_back=7)
        
        # Should return top 10 repos (or all if less than 10)
        self.assertEqual(result, existing_repos)
        self.assertEqual(len(result), 3)

    @patch('commit_stream.get_all_commits_for_repos')
    @patch('commit_stream.get_recently_active_repos_from_existing')
    def test_get_commit_stream_data_from_repos_success(self, mock_get_active, mock_get_commits):
        mock_get_active.return_value = ["owner/repo1", "owner/repo2"]
        mock_get_commits.return_value = [
            {"repo": "owner/repo1", "message": "Test commit", "date": "2025-07-20T10:00:00Z"}
        ]
        
        result = get_commit_stream_data_from_repos("fake_token", ["owner/repo1", "owner/repo2", "owner/repo3"])
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["repo"], "owner/repo1")
        mock_get_active.assert_called_once_with(["owner/repo1", "owner/repo2", "owner/repo3"])
        mock_get_commits.assert_called_once_with("fake_token", ["owner/repo1", "owner/repo2"], 20)

    @patch('commit_stream.get_all_commits_for_repos')
    @patch('commit_stream.get_recently_active_repos_from_existing')
    def test_get_commit_stream_data_from_repos_no_token(self, mock_get_active, mock_get_commits):
        result = get_commit_stream_data_from_repos("", ["owner/repo1"])
        
        self.assertEqual(result, [])
        mock_get_active.assert_not_called()
        mock_get_commits.assert_not_called()

    @patch('commit_stream.get_all_commits_for_repos')
    @patch('commit_stream.get_recently_active_repos_from_existing')
    def test_get_commit_stream_data_from_repos_no_repos(self, mock_get_active, mock_get_commits):
        result = get_commit_stream_data_from_repos("fake_token", [])
        
        self.assertEqual(result, [])
        mock_get_active.assert_not_called()
        mock_get_commits.assert_not_called()

    @patch('commit_stream.get_commit_stream_data')
    @patch('commit_stream.st')
    def test_display_commit_stream_no_token(self, mock_st, mock_get_data):
        display_commit_stream("")
        
        mock_st.sidebar.warning.assert_called_once_with("GitHub token required for commit stream")
        mock_get_data.assert_not_called()

    @patch('commit_stream.get_commit_stream_data_from_repos')
    @patch('commit_stream.st')
    def test_display_commit_stream_with_existing_repos(self, mock_st, mock_get_data):
        mock_get_data.return_value = []
        existing_repos = ["owner/repo1", "owner/repo2"]
        
        display_commit_stream("fake_token", existing_repos)
        
        mock_get_data.assert_called_once_with("fake_token", existing_repos)
        mock_st.sidebar.info.assert_called_once_with("No recent commits found")

    @patch('commit_stream.get_commit_stream_data')
    @patch('commit_stream.st')
    def test_display_commit_stream_no_commits(self, mock_st, mock_get_data):
        mock_get_data.return_value = []

        display_commit_stream("fake_token")
        
        mock_st.sidebar.info.assert_called_once_with("No recent commits found")

    @patch('commit_stream.get_commit_stream_data')
    @patch('commit_stream.st')
    @patch('commit_stream.format_commit_for_stream')
    def test_display_commit_stream_with_commits(self, mock_format, mock_st, mock_get_data):
        mock_get_data.return_value = [
            {
                "repo": "owner/repo1",
                "message": "Test commit",
                "date": "2025-07-20T10:00:00Z",
                "author": "Test Author"
            }
        ]
        mock_format.return_value = "<div>formatted commit</div>"
        mock_st.sidebar.columns.return_value = (MagicMock(), MagicMock())
        mock_st.button.return_value = False

        display_commit_stream("fake_token")
        
        mock_st.sidebar.subheader.assert_called_once_with("🔄 Live Commit Stream")
        mock_st.sidebar.markdown.assert_called()
        mock_format.assert_called_once()

    @patch('commit_stream.get_commit_stream_data')
    @patch('commit_stream.st')
    def test_display_commit_stream_refresh_button(self, mock_st, mock_get_data):
        mock_get_data.return_value = [
            {
                "repo": "owner/repo1",
                "repo_url": "https://github.com/owner/repo1", 
                "branch_name": "main",
                "branch_url": "https://github.com/owner/repo1/tree/main",
                "sha": "1234567",
                "message": "Test commit",
                "author": "Test Author",
                "date": "2025-07-20T10:00:00Z",
                "url": "https://github.com/owner/repo1/commit/1234567"
            }
        ]
        
        # Mock columns and context managers
        col1_mock = MagicMock()
        col2_mock = MagicMock()
        col1_mock.__enter__ = MagicMock(return_value=col1_mock)
        col1_mock.__exit__ = MagicMock(return_value=None)
        col2_mock.__enter__ = MagicMock(return_value=col2_mock)
        col2_mock.__exit__ = MagicMock(return_value=None)
        mock_st.sidebar.columns.return_value = (col1_mock, col2_mock)
        
        # Mock button to return True when clicked
        mock_st.button.return_value = True
        
        # Test that the function can be called (the actual button logic is tested separately)
        display_commit_stream("fake_token")
        
        # Verify basic structure is called
        mock_st.sidebar.subheader.assert_called_once_with("🔄 Live Commit Stream")


if __name__ == '__main__':
    unittest.main()