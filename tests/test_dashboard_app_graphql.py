import os
import unittest
from unittest.mock import patch

from dashboard_app_graphql import _get_github_data


class TestDashboardAppGraphQL(unittest.TestCase):

# Fixed test to use correct function names
    @patch('dashboard_app_graphql.get_all_accessible_repo_data')
    @patch('dashboard_app_graphql.get_bulk_data')
    @patch('dashboard_app_graphql.st')
    @patch('dashboard_app_graphql.DEBUG_MODE', False)
    def test_load_github_data(self, mock_st, mock_get_bulk_data, mock_get_all_accessible_repo_data):
        # Mock the github_service functions
        mock_get_all_accessible_repo_data.return_value = [('owner/repo1', '2025-07-20T10:00:00Z')]
        mock_get_bulk_data.return_value = (
            [{"repo": "owner/repo1", "message": "Test commit", "date": "2025-07-20T10:00:00Z"}],
            [],
            []
        )

        # Mock streamlit functions
        mock_st.cache_data.return_value = lambda func: func
        mock_st.write = lambda x: None  # Mock st.write to avoid output

        # Run the function
        commits, open_prs, merged_prs, this_week_commits, this_week_prs, repo_data = _get_github_data('fake_token', False, os.getcwd() +"/github_data.json", [], None)

        # Assertions
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0]['message'], 'Test commit')
        self.assertEqual(len(this_week_commits), 1)
        self.assertEqual(len(repo_data), 1)
        # Ensure that the mocked functions were called
        mock_get_all_accessible_repo_data.assert_called_once()
        mock_get_bulk_data.assert_called_once()


if __name__ == '__main__':
    unittest.main()
