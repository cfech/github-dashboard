import unittest
from unittest.mock import patch, MagicMock, mock_open
import pandas as pd
import os
import json
import tempfile
from datetime import datetime, timezone, timedelta
from dashboard_app_graphql import (
    get_application_config, create_user_stats_table, format_pr_for_stream,
    filter_data_by_timeframe, prepare_pr_data_with_status, load_debug_data,
    save_debug_data, format_item_with_today_highlighting
)

# Mock streamlit caching globally to avoid interference
patch('dashboard_app_graphql.st.cache_data', lambda ttl=None: lambda func: func).start()


class TestDashboardAppComprehensive(unittest.TestCase):
    """Comprehensive tests for dashboard app functions."""

    @patch.dict('os.environ', {
        'GITHUB_TOKEN': 'test_token',
        'REPO_FETCH_LIMIT': '50'
    })
    def test_get_application_config(self):
        """Test application configuration retrieval."""
        config = get_application_config()
        
        self.assertEqual(config['github_token'], 'test_token')
        self.assertEqual(config['repo_fetch_limit'], 50)
        self.assertIsInstance(config['debug_mode'], bool)
        self.assertIsInstance(config['target_organizations'], list)

    def test_create_user_stats_table_commits(self):
        """Test user stats table creation for commits."""
        commits_data = [
            {"author": "user1", "repo": "repo1"},
            {"author": "user1", "repo": "repo2"},
            {"author": "user2", "repo": "repo1"},
            {"author": "user1", "repo": "repo1"}
        ]
        
        result = create_user_stats_table(commits_data, "commits")
        
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 2)
        self.assertEqual(result.iloc[0]['User'], 'user1')
        self.assertEqual(result.iloc[0]['Count'], 3)
        self.assertEqual(result.iloc[1]['User'], 'user2')
        self.assertEqual(result.iloc[1]['Count'], 1)

    def test_create_user_stats_table_prs(self):
        """Test user stats table creation for PRs."""
        prs_data = [
            {"author": "user1", "repo": "repo1"},
            {"author": "user2", "repo": "repo1"},
            {"author": "user1", "repo": "repo2"}
        ]
        
        result = create_user_stats_table(prs_data, "prs")
        
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 2)
        self.assertEqual(result.iloc[0]['User'], 'user1')
        self.assertEqual(result.iloc[0]['Count'], 2)

    def test_create_user_stats_table_empty(self):
        """Test user stats table creation with empty data."""
        result = create_user_stats_table([], "commits")
        
        self.assertIsInstance(result, pd.DataFrame)
        self.assertTrue(result.empty)

    def test_format_pr_for_stream(self):
        """Test PR data formatting for stream."""
        pr = {
            "repo": "owner/test-repo",
            "repo_url": "https://github.com/owner/test-repo",
            "pr_number": 123,
            "title": "Test PR",
            "author": "testuser",
            "date": "2025-01-01T12:00:00Z",
            "url": "https://github.com/owner/test-repo/pull/123"
        }
        
        result = format_pr_for_stream(pr)
        
        self.assertIsInstance(result, str)
        self.assertIn("test-repo", result)
        self.assertIn("Test PR", result)
        self.assertIn("testuser", result)
        self.assertIn("#123", result)

    def test_filter_data_by_timeframe(self):
        """Test data filtering by timeframe."""
        now = datetime.now(timezone.utc)
        recent_date = (now - timedelta(days=3)).isoformat()
        old_date = (now - timedelta(days=20)).isoformat()
        
        data = [
            {"date": recent_date, "item": "recent"},
            {"date": old_date, "item": "old"}
        ]
        
        result = filter_data_by_timeframe(data, weeks=1)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["item"], "recent")

    def test_prepare_pr_data_with_status(self):
        """Test PR data preparation with status."""
        recent_date = datetime.now(timezone.utc).isoformat()
        open_prs = [{"pr_number": 1, "title": "Open PR", "date": recent_date}]
        merged_prs = [{"pr_number": 2, "title": "Merged PR", "date": recent_date}]
        
        open_result, merged_result = prepare_pr_data_with_status(open_prs, merged_prs)
        
        self.assertEqual(len(open_result), 1)
        self.assertEqual(len(merged_result), 1)
        self.assertEqual(open_result[0]["status"], "Open")
        self.assertEqual(merged_result[0]["status"], "Merged")

    def test_load_debug_data_existing_file(self):
        """Test loading debug data from existing file."""
        debug_data = {
            "commits": [{"id": 1}],
            "open_prs": [{"id": 2}],
            "merged_prs": [{"id": 3}],
            "this_week_commits": [{"id": 4}],
            "this_week_prs": [{"id": 5}]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(debug_data, f)
            temp_file = f.name
        
        try:
            result = load_debug_data(temp_file)
            
            self.assertEqual(len(result), 5)
            self.assertEqual(result[0], [{"id": 1}])  # commits
            self.assertEqual(result[1], [{"id": 2}])  # open_prs
            self.assertEqual(result[2], [{"id": 3}])  # merged_prs
            self.assertEqual(result[3], [{"id": 4}])  # this_week_commits
            self.assertEqual(result[4], [{"id": 5}])  # this_week_prs
        finally:
            os.unlink(temp_file)

    def test_load_debug_data_nonexistent_file(self):
        """Test loading debug data from nonexistent file."""
        result = load_debug_data("/nonexistent/file.json")
        
        self.assertEqual(result, ([], [], [], [], []))

    def test_save_debug_data(self):
        """Test saving debug data to file."""
        commits = [{"id": 1}]
        open_prs = [{"id": 2}]
        merged_prs = [{"id": 3}]
        this_week_commits = [{"id": 4}]
        this_week_prs = [{"id": 5}]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        
        try:
            save_debug_data(temp_file, commits, open_prs, merged_prs, this_week_commits, this_week_prs)
            
            # Verify file was created and contains correct data
            with open(temp_file, 'r') as f:
                saved_data = json.load(f)
            
            self.assertEqual(saved_data["commits"], commits)
            self.assertEqual(saved_data["open_prs"], open_prs)
            self.assertEqual(saved_data["merged_prs"], merged_prs)
            self.assertEqual(saved_data["this_week_commits"], this_week_commits)
            self.assertEqual(saved_data["this_week_prs"], this_week_prs)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def test_format_item_with_today_highlighting(self):
        """Test item formatting with today highlighting."""
        # Create a pandas Series with today's date
        today_date = datetime.now(timezone.utc).isoformat()
        row = pd.Series({
            'date': today_date,
            'repo': 'owner/test-repo',
            'repo_url': 'https://github.com/owner/test-repo',
            'title': 'Test PR',
            'author': 'testuser',
            'pr_number': 123,
            'url': 'https://github.com/owner/test-repo/pull/123'
        })
        
        result = format_item_with_today_highlighting(row, "pr")
        
        self.assertIsInstance(result, dict)
        self.assertIn('Repository', result)
        self.assertIn('PR Number', result)
        self.assertIn('Title', result)
        self.assertIn('Author', result)
        # Should contain today highlighting
        self.assertIn('TODAY', result['Repository'])


if __name__ == '__main__':
    unittest.main()