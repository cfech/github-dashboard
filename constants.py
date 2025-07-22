"""
Constants for the GitHub Dashboard application.

This module contains all hardcoded values, configuration, and magic numbers
to improve maintainability and make configuration easier.
"""

import os
from typing import Dict, List

# =============================================================================
# Application Configuration
# =============================================================================

# Debug and file settings
DEBUG_MODE: bool = True
DEBUG_DATA_FILENAME: str = "github_data.json"
COMMIT_STREAM_DEBUG_FILENAME: str = "cs_debug.json"
DEBUG_DATA_FILE: str = os.path.join(os.getcwd(), DEBUG_DATA_FILENAME)
COMMIT_STREAM_DEBUG_FILE: str = os.path.join(os.getcwd(), COMMIT_STREAM_DEBUG_FILENAME)

# Default organization settings
_org_env = os.getenv("TARGET_ORGANIZATIONS", "")
DEFAULT_TARGET_ORGANIZATIONS: List[str] = [org.strip() for org in _org_env.split(",") if org.strip()] if _org_env else []

# Repository and data limits
DEFAULT_REPO_FETCH_LIMIT: int = 25
COMMIT_STREAM_REPO_LIMIT: int = 30
COMMITS_PER_REPO_DEFAULT: int = 10
MAX_REPOS_FOR_COMMIT_STREAM: int = 5

# =============================================================================
# API and Network Configuration
# =============================================================================

# Timeout settings (in seconds)
REQUEST_TIMEOUT: int = 30
GRAPHQL_QUERY_TIMEOUT: int = 45

# GitHub API settings
GITHUB_API_URL: str = os.getenv("GITHUB_API_URL", "https://api.github.com/graphql")

# Time periods
DAYS_IN_WEEK: int = 7
HOURS_IN_DAY: int = 24

# =============================================================================
# UI and Display Configuration
# =============================================================================

# Date colors for timeline indicators
DATE_COLORS: Dict[str, str] = {
    "today": "#9C27B0",      # Nice purple for today
    "yesterday": "#43A047",   # Green for yesterday  
    "this_week": "#FB8C00",   # Orange for this week
    "older": "#FFFFFF"        # White for older items
}

# Timeline emojis for different time periods
TIMELINE_EMOJIS: Dict[str, str] = {
    "today": "🌟",       # Shining star for today
    "yesterday": "🌙",   # Moon for yesterday
    "this_week": "☄️",   # Comet for this week
    "older": "⭐"        # Distant star for older
}

# Stream and container settings
STREAM_CONTAINER_HEIGHT: int = 900
TABLE_CONTAINER_HEIGHT: int = 350

# =============================================================================
# Text and Display Limits
# =============================================================================

# Text formatting
COMMIT_MESSAGE_MAX_LENGTH: int = 100
PR_TITLE_MAX_LENGTH: int = 100
DEFAULT_TEXT_TRUNCATION_SUFFIX: str = "..."

# Default display counts
DEFAULT_DISPLAY_COUNT: int = 10
MIN_DISPLAY_COUNT: int = 1
MAX_DISPLAY_COUNT: int = 50

# =============================================================================
# Status and Emoji Mappings
# =============================================================================

# PR status indicators
PR_STATUS_EMOJIS: Dict[str, str] = {
    "Open": "🔄",
    "Merged": "✅",
    "Closed": "❌"
}

# Repository activity indicators  
ACTIVITY_EMOJIS: Dict[str, str] = {
    "commit": "📝",
    "pr": "🔀", 
    "repo": "📦",
    "branch": "🌿",
    "author": "👤",
    "date": "📅"
}

# =============================================================================
# CSS and Styling
# =============================================================================

# CSS class names
CSS_CLASSES: Dict[str, str] = {
    "today_badge": "today-badge",
    "today_date": "today-date", 
    "table_container": "table-container",
    "status_open": "status-open",
    "status_merged": "status-merged"
}

# CSS colors for badges and highlights
BADGE_COLORS: Dict[str, str] = {
    "today_gradient_start": "#ff8f00",
    "today_gradient_end": "#f57c00",
    "open_bg": "#e3f2fd",
    "open_text": "#1565c0",
    "merged_bg": "#e8f5e8", 
    "merged_text": "#2e7d32"
}

# =============================================================================
# Error Messages and Logging
# =============================================================================

ERROR_MESSAGES: Dict[str, str] = {
    "no_token": "GITHUB_TOKEN environment variable not set.",
    "no_repos": "No repositories found.",
    "no_commits": "No commits found.",
    "no_prs": "No pull requests found.",
    "api_error": "Error communicating with GitHub API.",
    "timeout_error": "Request timed out.",
    "file_not_found": "Debug file not found.",
    "invalid_data": "Invalid data format received."
}

INFO_MESSAGES: Dict[str, str] = {
    "debug_mode_on": "Debug Mode is ON. Using local data.",
    "debug_mode_off": "Debug Mode is OFF. Fetching live data.",
    "no_commits_this_week": "No commits this week.",
    "no_prs_this_week": "No pull requests opened or merged this week.",
    "refresh_data": "Refresh Live Data"
}

# =============================================================================
# Environment Variables
# =============================================================================

ENV_VARS: Dict[str, str] = {
    "github_token": "GITHUB_TOKEN",
    "repo_fetch_limit": "REPO_FETCH_LIMIT",
    "debug_mode": "DEBUG_MODE",
    "target_organizations": "TARGET_ORGANIZATIONS"
}

# =============================================================================
# GraphQL Query Fragments
# =============================================================================

# Common GraphQL fragments for reuse
GRAPHQL_FRAGMENTS: Dict[str, str] = {
    "repository_fields": """
        name
        nameWithOwner
        url
        pushedAt
        isPrivate
        defaultBranchRef {
            name
        }
    """,
    
    "commit_fields": """
        oid
        message
        committedDate
        author {
            name
            email
            user {
                login
            }
        }
        url
    """,
    
    "pull_request_fields": """
        number
        title
        url
        createdAt
        mergedAt
        state
        author {
            login
        }
        repository {
            nameWithOwner
            url
        }
    """
}