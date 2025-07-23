import unittest
from constants import (
    LOOK_BACK_DAYS, DEFAULT_REPO_FETCH_LIMIT, COMMIT_STREAM_REPO_LIMIT,
    DATE_COLORS, TIMELINE_EMOJIS, ERROR_MESSAGES, INFO_MESSAGES,
    GRAPHQL_FRAGMENTS, ENV_VARS
)


class TestConstants(unittest.TestCase):
    """Test the constants module."""
    
    def test_look_back_days_is_integer(self):
        """Test that LOOK_BACK_DAYS is an integer."""
        self.assertIsInstance(LOOK_BACK_DAYS, int)
        self.assertGreater(LOOK_BACK_DAYS, 0)
    
    def test_repo_limits_are_positive(self):
        """Test that repository limits are positive integers."""
        self.assertIsInstance(DEFAULT_REPO_FETCH_LIMIT, int)
        self.assertIsInstance(COMMIT_STREAM_REPO_LIMIT, int)
        self.assertGreater(DEFAULT_REPO_FETCH_LIMIT, 0)
        self.assertGreater(COMMIT_STREAM_REPO_LIMIT, 0)
    
    def test_date_colors_dict(self):
        """Test that DATE_COLORS contains required keys."""
        required_keys = ["today", "yesterday", "this_week", "older"]
        for key in required_keys:
            self.assertIn(key, DATE_COLORS)
            self.assertTrue(DATE_COLORS[key].startswith("#"))
    
    def test_timeline_emojis_dict(self):
        """Test that TIMELINE_EMOJIS contains required keys."""
        required_keys = ["today", "yesterday", "this_week", "older"]
        for key in required_keys:
            self.assertIn(key, TIMELINE_EMOJIS)
            self.assertIsInstance(TIMELINE_EMOJIS[key], str)
    
    def test_error_messages_dict(self):
        """Test that ERROR_MESSAGES contains required keys."""
        required_keys = ["no_token", "no_repos", "no_commits", "no_prs"]
        for key in required_keys:
            self.assertIn(key, ERROR_MESSAGES)
            self.assertIsInstance(ERROR_MESSAGES[key], str)
    
    def test_info_messages_dict(self):
        """Test that INFO_MESSAGES contains required keys."""
        required_keys = ["debug_mode_on", "debug_mode_off", "no_commits_this_week"]
        for key in required_keys:
            self.assertIn(key, INFO_MESSAGES)
            self.assertIsInstance(INFO_MESSAGES[key], str)
    
    def test_graphql_fragments_dict(self):
        """Test that GRAPHQL_FRAGMENTS contains required fragments."""
        required_keys = ["repository_fields", "commit_fields", "pull_request_fields"]
        for key in required_keys:
            self.assertIn(key, GRAPHQL_FRAGMENTS)
            self.assertIsInstance(GRAPHQL_FRAGMENTS[key], str)
            self.assertGreater(len(GRAPHQL_FRAGMENTS[key].strip()), 0)
    
    def test_env_vars_dict(self):
        """Test that ENV_VARS contains required environment variable names."""
        required_keys = ["github_token", "repo_fetch_limit", "debug_mode"]
        for key in required_keys:
            self.assertIn(key, ENV_VARS)
            self.assertIsInstance(ENV_VARS[key], str)


if __name__ == '__main__':
    unittest.main()