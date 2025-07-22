"""
Shared utility functions for the GitHub Dashboard application.

This module contains common functionality used across multiple files to eliminate code duplication.
"""

from datetime import datetime, timezone, timedelta
from typing import Tuple


def format_timestamp_to_local(utc_timestamp: str) -> str:
    """
    Convert UTC timestamp to local timezone formatted string.
    
    Args:
        utc_timestamp: UTC timestamp string in ISO format (e.g., "2025-07-20T10:00:00Z")
        
    Returns:
        Formatted timestamp string in local timezone (e.g., "2025-07-20 03:00 PM EST")
    """
    utc_dt = datetime.fromisoformat(utc_timestamp.replace('Z', '+00:00'))
    local_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone()
    return local_dt.strftime('%Y-%m-%d %I:%M %p EST')


def is_timestamp_today_local(utc_timestamp: str) -> bool:
    """
    Check if UTC timestamp is today in local timezone.
    
    Args:
        utc_timestamp: UTC timestamp string in ISO format
        
    Returns:
        True if the timestamp is from today, False otherwise
    """
    utc_dt = datetime.fromisoformat(utc_timestamp.replace('Z', '+00:00'))
    local_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone()
    return local_dt.date() == datetime.now().date()


def get_date_color_and_emoji(utc_timestamp: str) -> Tuple[str, str]:
    """
    Get color coding and emoji for dates based on recency.
    
    Args:
        utc_timestamp: UTC timestamp string in ISO format
        
    Returns:
        Tuple of (color_hex_code, emoji) based on how recent the timestamp is
    """
    from constants import DATE_COLORS, TIMELINE_EMOJIS
    
    utc_dt = datetime.fromisoformat(utc_timestamp.replace('Z', '+00:00'))
    local_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone()
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    
    item_date = local_dt.date()
    
    if item_date == today:
        return DATE_COLORS["today"], TIMELINE_EMOJIS["today"]
    elif item_date == yesterday:
        return DATE_COLORS["yesterday"], TIMELINE_EMOJIS["yesterday"]
    elif item_date >= week_ago:
        return DATE_COLORS["this_week"], TIMELINE_EMOJIS["this_week"]
    else:
        return DATE_COLORS["older"], TIMELINE_EMOJIS["older"]


def get_repository_display_name(repo_full_name: str) -> str:
    """
    Extract the repository name from a full repository path.
    
    Args:
        repo_full_name: Full repository name (e.g., "owner/repository-name")
        
    Returns:
        Just the repository name (e.g., "repository-name")
    """
    return repo_full_name.split("/")[-1]


def safe_get_commit_field(commit: dict, field: str, default: str = "Unknown") -> str:
    """
    Safely get a field from commit data with fallback to default.
    
    Args:
        commit: Commit data dictionary
        field: Field name to retrieve
        default: Default value if field is missing or None
        
    Returns:
        Field value or default if not found
    """
    return commit.get(field, default) or default


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length with optional suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length before truncation
        suffix: Suffix to add if text is truncated
        
    Returns:
        Truncated text with suffix if needed
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def calculate_days_ago(utc_timestamp: str) -> int:
    """
    Calculate how many days ago a timestamp was from today.
    
    Args:
        utc_timestamp: UTC timestamp string in ISO format
        
    Returns:
        Number of days ago (0 for today, 1 for yesterday, etc.)
    """
    utc_dt = datetime.fromisoformat(utc_timestamp.replace('Z', '+00:00'))
    local_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone()
    today = datetime.now().date()
    return (today - local_dt.date()).days