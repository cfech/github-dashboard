import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import pandas as pd

from dashboard_app_graphql import (
    get_application_config, filter_data_by_timeframe, prepare_pr_data_with_status,
    create_user_stats_table, format_pr_for_stream
)


class TestDashboardFunctions(unittest.TestCase):
    """Test key dashboard functions."""
    
    @patch.dict('os.environ', {'GITHUB_TOKEN': 'test_token', 'REPO_FETCH_LIMIT': '50'})
    def test_get_application_config(self):
        """Test application configuration loading."""
        config = get_application_config()
        
        self.assertIsInstance(config, dict)
        self.assertIn('github_token', config)
        self.assertIn('debug_mode', config)
        self.assertIn('target_organizations', config)
        self.assertIn('repo_fetch_limit', config)
        
        self.assertEqual(config['github_token'], 'test_token')
        self.assertEqual(config['repo_fetch_limit'], 50)
        self.assertIsInstance(config['debug_mode'], bool)
        self.assertIsInstance(config['target_organizations'], list)
    
    def test_filter_data_by_timeframe(self):
        """Test data filtering by timeframe."""
        now = datetime.now(timezone.utc)
        old_date = (now - timedelta(weeks=2)).isoformat()
        recent_date = (now - timedelta(days=3)).isoformat()
        
        test_data = [
            {"date": old_date, "title": "Old item"},
            {"date": recent_date, "title": "Recent item"}
        ]
        
        filtered = filter_data_by_timeframe(test_data, weeks=1)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["title"], "Recent item")
        
        # Test with empty data
        self.assertEqual(filter_data_by_timeframe([]), [])
    
    def test_prepare_pr_data_with_status(self):
        """Test PR data preparation with status."""
        now = datetime.now(timezone.utc)
        recent_date = (now - timedelta(days=3)).isoformat()
        
        open_prs = [{"date": recent_date, "title": "Open PR"}]
        merged_prs = [{"date": recent_date, "title": "Merged PR"}]
        
        open_result, merged_result = prepare_pr_data_with_status(open_prs, merged_prs)
        
        self.assertEqual(len(open_result), 1)
        self.assertEqual(len(merged_result), 1)
        self.assertEqual(open_result[0]["status"], "Open")
        self.assertEqual(merged_result[0]["status"], "Merged")
    
    def test_create_user_stats_table(self):
        """Test user statistics table creation."""
        test_data = [
            {"author": "user1", "title": "Commit 1"},
            {"author": "user1", "title": "Commit 2"},
            {"author": "user2", "title": "Commit 3"},
            {"author": "Unknown", "title": "Commit 4"}
        ]
        
        stats_df = create_user_stats_table(test_data, "commits")
        
        self.assertIsInstance(stats_df, pd.DataFrame)
        if not stats_df.empty:
            self.assertIn("User", stats_df.columns)
            self.assertIn("Count", stats_df.columns)
            
            # Should be sorted by count descending
            counts = stats_df["Count"].tolist()
            self.assertEqual(counts, sorted(counts, reverse=True))
        
        # Test with empty data
        empty_stats = create_user_stats_table([], "commits")
        self.assertTrue(empty_stats.empty)
    
    def test_format_pr_for_stream(self):
        """Test PR formatting for stream display."""
        test_pr = {
            "date": datetime.now().isoformat() + "Z",
            "title": "Test PR",
            "repo": "owner/test-repo",
            "repo_url": "https://github.com/owner/test-repo",
            "author": "testuser",
            "pr_number": 123,
            "url": "https://github.com/owner/test-repo/pull/123",
            "status": "Open"
        }
        
        formatted = format_pr_for_stream(test_pr)
        
        self.assertIsInstance(formatted, str)
        self.assertIn("test-repo", formatted)
        self.assertIn("Test PR", formatted)
        self.assertIn("testuser", formatted)
        self.assertIn("#123", formatted)
        self.assertIn("Open", formatted)


if __name__ == '__main__':
    unittest.main()