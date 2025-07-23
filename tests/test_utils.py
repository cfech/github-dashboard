import unittest
from datetime import datetime, timezone, timedelta
from utils import (
    format_timestamp_to_local, is_timestamp_today_local, get_date_color_and_emoji,
    get_repository_display_name, safe_get_commit_field, truncate_text, calculate_days_ago
)


class TestUtils(unittest.TestCase):
    """Test the utils module."""
    
    def test_format_timestamp_to_local(self):
        """Test timestamp formatting."""
        utc_timestamp = "2025-01-15T12:00:00Z"
        result = format_timestamp_to_local(utc_timestamp)
        self.assertIsInstance(result, str)
        self.assertIn("2025-01-15", result)
        self.assertIn("EST", result)
    
    def test_is_timestamp_today_local(self):
        """Test today timestamp detection."""
        # Test with today's timestamp in UTC
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertTrue(is_timestamp_today_local(today_utc))
        
        # Test with yesterday's timestamp in UTC
        yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertFalse(is_timestamp_today_local(yesterday_utc))
    
    def test_get_date_color_and_emoji(self):
        """Test date color and emoji assignment."""
        # Test with today's timestamp in UTC
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        color, emoji = get_date_color_and_emoji(today_utc)
        self.assertIsInstance(color, str)
        self.assertIsInstance(emoji, str)
        self.assertTrue(color.startswith("#"))
        
        # Test with yesterday's timestamp in UTC
        yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        color, emoji = get_date_color_and_emoji(yesterday_utc)
        self.assertTrue(color.startswith("#"))
        self.assertIsInstance(emoji, str)
        
        # Test with this week's timestamp (3 days ago)
        this_week_utc = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        color, emoji = get_date_color_and_emoji(this_week_utc)
        self.assertTrue(color.startswith("#"))
        self.assertIsInstance(emoji, str)
        
        # Test with older timestamp (2 weeks ago)
        older_utc = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
        color, emoji = get_date_color_and_emoji(older_utc)
        self.assertTrue(color.startswith("#"))
        self.assertIsInstance(emoji, str)
    
    def test_get_repository_display_name(self):
        """Test repository name extraction."""
        self.assertEqual(get_repository_display_name("owner/repo-name"), "repo-name")
        self.assertEqual(get_repository_display_name("complex-org/my-awesome-project"), "my-awesome-project")
        self.assertEqual(get_repository_display_name("simple"), "simple")
    
    def test_safe_get_commit_field(self):
        """Test safe field extraction from commit data."""
        commit = {"author": "John Doe", "message": "Test commit"}
        
        self.assertEqual(safe_get_commit_field(commit, "author"), "John Doe")
        self.assertEqual(safe_get_commit_field(commit, "message"), "Test commit")
        self.assertEqual(safe_get_commit_field(commit, "missing_field", "default"), "default")
        self.assertEqual(safe_get_commit_field(commit, "missing_field"), "Unknown")
        
        # Test with None value
        commit_with_none = {"author": None}
        self.assertEqual(safe_get_commit_field(commit_with_none, "author", "fallback"), "fallback")
    
    def test_truncate_text(self):
        """Test text truncation functionality."""
        self.assertEqual(truncate_text("short", 10), "short")
        self.assertEqual(truncate_text("this is a very long text", 10), "this is...")
        self.assertEqual(truncate_text("exactly ten", 11), "exactly ten")
        self.assertEqual(truncate_text("test", 10, "***"), "test")
        self.assertEqual(truncate_text("long text here", 8, "***"), "long ***")
    
    def test_calculate_days_ago(self):
        """Test days ago calculation."""
        # Test with today's timestamp in UTC
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(calculate_days_ago(today_utc), 0)
        
        # Test with yesterday's timestamp in UTC
        yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(calculate_days_ago(yesterday_utc), 1)
        
        # Test with a week ago in UTC
        week_ago_utc = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(calculate_days_ago(week_ago_utc), 7)


if __name__ == '__main__':
    unittest.main()