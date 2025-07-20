import unittest
from unittest.mock import patch, MagicMock
import os
import json
from datetime import datetime, timedelta, timezone

# Assuming dashboard_app_graphql.py is in the root directory
from dashboard_app_graphql import _get_github_data, _display_recent_commits, _display_recent_prs, _display_pull_requests_section, _display_commits_section


class TestDashboardAppGraphQLNew(unittest.TestCase):

    @patch('dashboard_app_graphql.st')
    @patch('dashboard_app_graphql.get_all_accessible_repo_names')
    @patch('dashboard_app_graphql.get_bulk_data')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('json.load')
    def test_get_github_data_no_token(self, mock_json_load, mock_open, mock_exists, mock_get_bulk_data, mock_get_all_accessible_repo_names, mock_st):
        commits, open_prs, merged_prs, this_week_commits, this_week_prs = _get_github_data(
            None, False, "/fake/path/data.json", [], None
        )
        self.assertEqual(commits, [])
        self.assertEqual(open_prs, [])
        self.assertEqual(merged_prs, [])
        self.assertEqual(this_week_commits, [])
        self.assertEqual(this_week_prs, [])
        mock_st.error.assert_called_once_with("GITHUB_TOKEN environment variable not set.")
        mock_get_all_accessible_repo_names.assert_not_called()
        mock_get_bulk_data.assert_not_called()

    @patch('dashboard_app_graphql.st')
    @patch('dashboard_app_graphql.get_all_accessible_repo_names')
    @patch('dashboard_app_graphql.get_bulk_data')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('json.load')
    def test_get_github_data_debug_mode_file_exists(self, mock_json_load, mock_open, mock_exists, mock_get_bulk_data, mock_get_all_accessible_repo_names, mock_st):
        mock_exists.return_value = True
        mock_json_load.return_value = {
            "commits": [{"message": "debug commit"}],
            "open_prs": [{"title": "debug pr"}],
            "merged_prs": [],
            "this_week_commits": [{"message": "debug this week commit"}],
            "this_week_prs": [{"title": "debug this week pr"}]
        }

        commits, open_prs, merged_prs, this_week_commits, this_week_prs = _get_github_data(
            "fake_token", True, "/fake/path/data.json", [], None
        )

        self.assertEqual(commits[0]['message'], "debug commit")
        self.assertEqual(open_prs[0]['title'], "debug pr")
        self.assertEqual(this_week_commits[0]['message'], "debug this week commit")
        self.assertEqual(this_week_prs[0]['title'], "debug this week pr")
        mock_exists.assert_called_once_with("/fake/path/data.json")
        mock_open.assert_called_once_with("/fake/path/data.json", 'r')
        mock_json_load.assert_called_once()
        mock_get_all_accessible_repo_names.assert_not_called()
        mock_get_bulk_data.assert_not_called()

    @patch('dashboard_app_graphql.st')
    @patch('dashboard_app_graphql.get_all_accessible_repo_names')
    @patch('dashboard_app_graphql.get_bulk_data')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('json.dump')
    def test_get_github_data_debug_mode_file_not_exists(self, mock_json_dump, mock_open, mock_exists, mock_get_bulk_data, mock_get_all_accessible_repo_names, mock_st):
        mock_exists.return_value = False
        mock_get_all_accessible_repo_names.return_value = ['owner/repo1']
        mock_get_bulk_data.return_value = (
            [{"repo": "owner/repo1", "message": "Test commit", "date": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}],
            [],
            []
        )

        commits, open_prs, merged_prs, this_week_commits, this_week_prs = _get_github_data(
            "fake_token", True, "/fake/path/data.json", [], None
        )

        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0]['message'], "Test commit")
        self.assertEqual(len(this_week_commits), 1)
        mock_exists.assert_called_once_with("/fake/path/data.json")
        mock_get_all_accessible_repo_names.assert_called_once()
        mock_get_bulk_data.assert_called_once()
        mock_open.assert_called_once_with("/fake/path/data.json", 'w')
        mock_json_dump.assert_called_once()

    @patch('dashboard_app_graphql.st')
    @patch('dashboard_app_graphql.get_all_accessible_repo_names')
    @patch('dashboard_app_graphql.get_bulk_data')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('json.dump')
    def test_get_github_data_repo_fetch_limit(self, mock_json_dump, mock_open, mock_exists, mock_get_bulk_data, mock_get_all_accessible_repo_names, mock_st):
        mock_exists.return_value = False # Simulate file not existing for debug mode write
        mock_get_all_accessible_repo_names.return_value = [f'owner/repo{i}' for i in range(50)]
        mock_get_bulk_data.return_value = ([], [], [])

        _get_github_data(
            "fake_token", True, "/fake/path/data.json", [], 10
        )

        mock_get_bulk_data.assert_called_once()
        self.assertEqual(mock_get_bulk_data.call_args[0][1], [f'owner/repo{i}' for i in range(10)])
        mock_open.assert_called_once_with("/fake/path/data.json", 'w')
        mock_json_dump.assert_called_once()

    @patch('dashboard_app_graphql.st')
    def test_display_recent_commits_empty(self, mock_st):
        _display_recent_commits([])
        mock_st.subheader.assert_called_once_with("Recent Commits (0)")
        mock_st.info.assert_called_once_with("No commits this week.")

    @patch('dashboard_app_graphql.st')
    def test_display_recent_prs_empty(self, mock_st):
        _display_recent_prs([])
        mock_st.subheader.assert_called_once_with("Recent Pull Requests (0)")
        mock_st.info.assert_called_once_with("No pull requests opened or merged this week.")

    @patch('dashboard_app_graphql.st')
    def test_display_pull_requests_section_empty(self, mock_st):
        _display_pull_requests_section([], [])
        mock_st.header.assert_called_once_with("Pull Requests")
        mock_st.info.assert_called_with("No pull requests found.")

    @patch('dashboard_app_graphql.st')
    def test_display_commits_section_empty(self, mock_st):
        _display_commits_section([])
        mock_st.header.assert_called_once_with("Commits")
        mock_st.info.assert_called_with("No commits found.")

if __name__ == '__main__':
    unittest.main()
