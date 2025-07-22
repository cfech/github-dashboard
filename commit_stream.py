"""
Commit Stream Module

This module handles fetching and displaying a live stream of commits from GitHub repositories.
It provides functionality for getting recent commits across multiple repositories and branches.
"""

import os
import requests
import streamlit as st
import time
import json
from datetime import datetime, timezone, timedelta
from operator import itemgetter
from typing import List, Dict, Any, Optional, Tuple

# Import shared modules
from constants import (
    GITHUB_API_URL, REQUEST_TIMEOUT, GRAPHQL_QUERY_TIMEOUT, COMMIT_STREAM_DEBUG_FILE,
    COMMIT_STREAM_REPO_LIMIT, MAX_REPOS_FOR_COMMIT_STREAM, COMMITS_PER_REPO_DEFAULT,
    STREAM_CONTAINER_HEIGHT, ERROR_MESSAGES, INFO_MESSAGES, CSS_CLASSES,
    DAYS_IN_WEEK, LOOK_BACK_DAYS
)
from utils import (
    format_timestamp_to_local, is_timestamp_today_local, get_date_color_and_emoji,
    get_repository_display_name, safe_get_commit_field, calculate_days_ago
)


# =============================================================================
# GraphQL Query Functions
# =============================================================================

def run_graphql_query_with_timeout(token: str, query: str, variables: Optional[Dict] = None, 
                                  timeout: int = REQUEST_TIMEOUT) -> Optional[Dict]:
    """
    Execute a GraphQL query with timeout handling and error management.
    
    Args:
        token: GitHub personal access token
        query: GraphQL query string
        variables: Optional query variables
        timeout: Request timeout in seconds
        
    Returns:
        Query result dictionary or None if failed
    """
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    
    try:
        response = requests.post(GITHUB_API_URL, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error(f"Request timed out after {timeout} seconds")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"GraphQL request failed: {str(e)}")
        return None


# =============================================================================
# Repository Activity Functions
# =============================================================================

def filter_recently_active_repos(repo_data_with_dates: List[Tuple[str, str]], 
                                days_back: int = LOOK_BACK_DAYS) -> List[str]:
    """
    Filter repositories to get those that have been pushed to recently.
    
    Args:
        repo_data_with_dates: List of (repo_name, push_date) tuples
        days_back: Number of days to look back for activity
        
    Returns:
        List of repository names that have been active recently
    """
    print(f"🔍 [COMMIT STREAM] Filtering {len(repo_data_with_dates)} repos for recent activity (past {days_back} days)")
    
    now_utc = datetime.now(timezone.utc)
    cutoff_date = now_utc - timedelta(days=days_back)
    recent_repos = []
    
    for repo_name, pushed_at in repo_data_with_dates:
        if not pushed_at:  # Skip repos with no push date
            continue
            
        try:
            push_date = datetime.fromisoformat(pushed_at.replace('Z', '+00:00'))
            
            if push_date >= cutoff_date:
                recent_repos.append(repo_name)
                days_ago = calculate_days_ago(pushed_at)
                hours_ago = (now_utc - push_date).total_seconds() / 3600
                
                if hours_ago < 24:
                    print(f"  ✅ {repo_name}: pushed {hours_ago:.1f} hours ago")
                else:
                    print(f"  ✅ {repo_name}: pushed {days_ago} days ago")
            else:
                days_ago = calculate_days_ago(pushed_at)
                print(f"  ❌ {repo_name}: pushed {days_ago} days ago (too old)")
                
        except Exception as e:
            print(f"  ⚠️  {repo_name}: Error parsing push date '{pushed_at}': {e}")
    
    print(f"📋 [COMMIT STREAM] Found {len(recent_repos)} repos pushed to in the last {days_back} days")
    if recent_repos:
        print(f"📋 [COMMIT STREAM] Recent repos: {recent_repos[:5]}{'...' if len(recent_repos) > 5 else ''}")
    
    return recent_repos


def get_recently_active_repos_via_api(token: str, days_back: int = DAYS_IN_WEEK, 
                                     limit: int = COMMIT_STREAM_REPO_LIMIT) -> List[str]:
    """
    Get repositories that have been updated recently via direct GraphQL API call.
    
    Args:
        token: GitHub personal access token
        days_back: Number of days to look back
        limit: Maximum number of repositories to fetch
        
    Returns:
        List of repository names that have been active recently
    """
    print(f"🔍 [COMMIT STREAM] Fetching recently active repos (past {days_back} days, limit {limit})")
    
    if not token:
        print("❌ [COMMIT STREAM] No token provided")
        return []
    
    since_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
    print(f"📅 [COMMIT STREAM] Looking for repos updated since: {since_date}")
    
    query = """
    query($since: DateTime!, $first: Int!) {
      viewer {
        repositories(
          first: $first
          orderBy: {field: PUSHED_AT, direction: DESC}
          affiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER]
        ) {
          nodes {
            nameWithOwner
            pushedAt
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    }
    """
    
    variables = {"since": since_date, "first": limit}
    result = run_graphql_query_with_timeout(token, query, variables)
    
    if not result or "data" not in result:
        print("❌ [COMMIT STREAM] No data returned from GraphQL query")
        return []
    
    repos = result.get("data", {}).get("viewer", {}).get("repositories", {}).get("nodes", [])
    print(f"📊 [COMMIT STREAM] Got {len(repos)} total repos from API")
    
    # Filter repos that were actually updated in the timeframe
    active_repos = []
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
    
    for repo in repos:
        if repo.get("pushedAt"):
            pushed_at = datetime.fromisoformat(repo["pushedAt"].replace('Z', '+00:00'))
            days_since = calculate_days_ago(repo["pushedAt"])
            print(f"  📦 {repo['nameWithOwner']}: pushed {days_since} days ago ({repo['pushedAt']})")
            
            if pushed_at >= cutoff_date:
                active_repos.append(repo["nameWithOwner"])
                print(f"    ✅ Added to active repos")
            else:
                print(f"    ❌ Too old, skipping")
        else:
            print(f"  📦 {repo.get('nameWithOwner', 'Unknown')}: No push date")
    
    print(f"🎯 [COMMIT STREAM] Found {len(active_repos)} recently active repos: {active_repos}")
    return active_repos


# =============================================================================
# Commit Fetching Functions
# =============================================================================

def build_commits_query(repo_names: List[str], commits_per_repo: int = COMMITS_PER_REPO_DEFAULT) -> str:
    """
    Build a GraphQL query to fetch commits from multiple repositories.
    
    Args:
        repo_names: List of repository names in "owner/name" format
        commits_per_repo: Number of commits to fetch per repository
        
    Returns:
        GraphQL query string
    """
    repo_queries = []
    
    for i, repo_name in enumerate(repo_names):
        try:
            owner, name = repo_name.split('/', 1)
        except ValueError:
            print(f"⚠️  [COMMIT STREAM] Invalid repo name format: {repo_name}")
            continue
            
        print(f"  📦 {repo_name}: requesting {commits_per_repo} commits per branch")
        
        repo_queries.append(f"""
        repo{i}: repository(owner: "{owner}", name: "{name}") {{
          nameWithOwner
          url
          refs(refPrefix: "refs/heads/", first: 10, orderBy: {{field: TAG_COMMIT_DATE, direction: DESC}}) {{
            nodes {{
              name
              target {{
                ... on Commit {{
                  history(first: {commits_per_repo}) {{
                    nodes {{
                      oid
                      messageHeadline
                      committedDate
                      author {{
                        name
                        email
                      }}
                      url
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """)
    
    return f"""
    query {{
      {' '.join(repo_queries)}
    }}
    """


def parse_commits_from_query_result(result: Dict) -> List[Dict[str, Any]]:
    """
    Parse commit data from GraphQL query result.
    
    Args:
        result: GraphQL query result dictionary
        
    Returns:
        List of commit dictionaries with standardized fields
    """
    all_commits = []
    
    for repo_key, repo_data in result.get("data", {}).items():
        if not repo_data:
            print(f"  📦 {repo_key}: No data (access denied or not found)")
            continue
            
        if not repo_data.get("refs"):
            print(f"  📦 {repo_data.get('nameWithOwner', repo_key)}: No refs/branches found")
            continue
            
        repo_name = repo_data["nameWithOwner"]
        repo_url = repo_data["url"]
        branch_count = len(repo_data["refs"]["nodes"])
        print(f"  📦 {repo_name}: Found {branch_count} branches")
        
        for branch_ref in repo_data["refs"]["nodes"]:
            branch_name = branch_ref["name"]
            branch_url = f"{repo_url}/tree/{branch_name}"
            
            if branch_ref.get("target") and branch_ref["target"].get("history"):
                commits_in_branch = len(branch_ref["target"]["history"]["nodes"])
                print(f"    🌿 {branch_name}: {commits_in_branch} commits")
                
                for commit in branch_ref["target"]["history"]["nodes"]:
                    commit_data = {
                        "repo": repo_name,
                        "repo_url": repo_url,
                        "branch_name": branch_name,
                        "branch_url": branch_url,
                        "sha": commit["oid"][:7],
                        "message": safe_get_commit_field(commit, "messageHeadline", "No message"),
                        "author": safe_get_commit_field(commit.get("author", {}), "name", "Unknown"),
                        "date": commit["committedDate"],
                        "url": commit["url"]
                    }
                    all_commits.append(commit_data)
            else:
                print(f"    🌿 {branch_name}: No commit history available")
    
    return all_commits


def fetch_commits_for_repositories(token: str, repo_names: List[str], 
                                  commit_limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetch all commits from specified repositories using GraphQL.
    
    Args:
        token: GitHub personal access token
        repo_names: List of repository names
        commit_limit: Total commit limit across all repositories
        
    Returns:
        List of commit dictionaries sorted by date (newest first)
    """
    print(f"🔍 [COMMIT STREAM] Fetching commits for {len(repo_names)} repos, limit {commit_limit}")
    
    if not token or not repo_names:
        print("❌ [COMMIT STREAM] No token or no repos provided")
        return []
    
    # Limit repositories to avoid timeout
    limited_repos = repo_names[:MAX_REPOS_FOR_COMMIT_STREAM]
    print(f"📋 [COMMIT STREAM] Limited to {len(limited_repos)} repos: {limited_repos}")
    
    # Calculate commits per repository
    commits_per_repo = min(commit_limit // len(limited_repos), COMMITS_PER_REPO_DEFAULT)
    
    # Build and execute query
    query = build_commits_query(limited_repos, commits_per_repo)
    
    print(f"🔄 [COMMIT STREAM] Executing GraphQL query with {GRAPHQL_QUERY_TIMEOUT}s timeout...")
    start_time = time.time()
    result = run_graphql_query_with_timeout(token, query, timeout=GRAPHQL_QUERY_TIMEOUT)
    query_time = time.time() - start_time
    print(f"⏱️  [COMMIT STREAM] GraphQL query completed in {query_time:.2f}s")
    
    if not result or "data" not in result:
        print("❌ [COMMIT STREAM] No data returned from commits query")
        return []
    
    # Parse commits from result
    all_commits = parse_commits_from_query_result(result)
    print(f"📊 [COMMIT STREAM] Collected {len(all_commits)} total commits from all branches")
    
    # Sort by date (most recent first)
    sorted_commits = sorted(all_commits, key=lambda x: x["date"], reverse=True)
    
    print(f"🎯 [COMMIT STREAM] Returning ALL {len(sorted_commits)} commits (no limit)")
    if sorted_commits:
        print(f"  📅 Newest: {sorted_commits[0]['repo']}/{sorted_commits[0]['branch_name']} - {sorted_commits[0]['date']}")
        print(f"  📅 Oldest: {sorted_commits[-1]['repo']}/{sorted_commits[-1]['branch_name']} - {sorted_commits[-1]['date']}")
    
    return sorted_commits


# =============================================================================
# Debug Data Management
# =============================================================================

def load_debug_commits(debug_file_path: str) -> List[Dict[str, Any]]:
    """Load commit data from debug file."""
    if not os.path.exists(debug_file_path):
        return []
        
    try:
        with open(debug_file_path, 'r') as f:
            debug_data = json.load(f)
        return debug_data.get("commits", [])
    except Exception as e:
        print(f"❌ [COMMIT STREAM] Error reading debug file: {str(e)}")
        return []


def save_debug_commits(debug_file_path: str, commits: List[Dict[str, Any]]) -> None:
    """Save commit data to debug file."""
    try:
        save_start = time.time()
        debug_data = {"commits": commits}
        with open(debug_file_path, 'w') as f:
            json.dump(debug_data, f, indent=4)
        save_time = time.time() - save_start
        print(f"💾 [COMMIT STREAM] Saved {len(commits)} commits to {debug_file_path} in {save_time:.3f}s")
    except Exception as e:
        print(f"❌ [COMMIT STREAM] Error saving debug file: {str(e)}")


# =============================================================================
# Commit Stream Formatting
# =============================================================================

def format_commit_for_stream(commit: Dict[str, Any]) -> str:
    """
    Format a single commit for stream display with color coding and TODAY badge.
    
    Args:
        commit: Commit data dictionary
        
    Returns:
        Formatted markdown string for display
    """
    formatted_date = format_timestamp_to_local(commit["date"])
    date_part = formatted_date.split()[0]  # Just the date part (YYYY-MM-DD)
    time_part = " ".join(formatted_date.split()[1:3])  # Time and AM/PM
    
    # Get color and emoji based on date
    date_color, badge = get_date_color_and_emoji(commit["date"])
    
    # Check if this commit is from today for the TODAY badge
    is_today = is_timestamp_today_local(commit["date"])
    
    # Extract commit details safely
    message = safe_get_commit_field(commit, "message", "No message")
    repo_name = get_repository_display_name(safe_get_commit_field(commit, "repo", "Unknown"))
    branch_name = safe_get_commit_field(commit, "branch_name", "main")
    author = safe_get_commit_field(commit, "author", "Unknown")
    sha = safe_get_commit_field(commit, "sha", "unknown")
    repo_url = safe_get_commit_field(commit, "repo_url", "#")
    commit_url = safe_get_commit_field(commit, "url", "#")
    
    # Add TODAY badge if it's from today
    repo_display = f"**[{repo_name}]({repo_url})**"
    if is_today:
        repo_display = f'<span class="{CSS_CLASSES["today_badge"]}">TODAY</span> {repo_display}'
    
    return f"""{badge} {repo_display} `{branch_name}`  
*{message}*  
**[`{sha}`]({commit_url})** {author}  
📅 <span style="color: {date_color};">{date_part} {time_part}</span>"""


# =============================================================================
# Main Data Fetching Functions
# =============================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_commit_stream_data_standalone(token: str, days_back: int = DAYS_IN_WEEK, 
                                     commit_limit: int = 100, debug_mode: bool = False) -> List[Dict[str, Any]]:
    """
    Get commit stream data independently (without repo data from main dashboard).
    
    Args:
        token: GitHub personal access token
        days_back: Number of days to look back for activity
        commit_limit: Maximum number of commits to fetch
        debug_mode: Whether to use debug mode
        
    Returns:
        List of commit dictionaries
    """
    # Try debug mode first
    if debug_mode:
        debug_start_time = time.time()
        print(f"🔄 [COMMIT STREAM] DEBUG MODE: Reading from {COMMIT_STREAM_DEBUG_FILE}")
        commits = load_debug_commits(COMMIT_STREAM_DEBUG_FILE)
        if commits:
            debug_time = time.time() - debug_start_time
            print(f"📊 [COMMIT STREAM] DEBUG MODE: Loaded {len(commits)} commits in {debug_time:.3f}s from debug file")
            return commits
    
    if not token:
        return []
    
    try:
        # Get recently active repositories
        active_repos = get_recently_active_repos_via_api(token, days_back)
        if not active_repos:
            return []
        
        # Get all commits from these repositories
        commits = fetch_commits_for_repositories(token, active_repos, commit_limit)
        
        # Save to debug file if not in debug mode
        if not debug_mode:
            save_debug_commits(COMMIT_STREAM_DEBUG_FILE, commits)
        
        return commits
        
    except Exception as e:
        st.error(f"Error fetching commit stream: {str(e)}")
        return []


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_commit_stream_data_from_repos(token: str, repo_data_with_dates: List[Tuple[str, str]], 
                                     commit_limit: int = 100, debug_mode: bool = False) -> List[Dict[str, Any]]:
    """
    Get commit stream data using repository data with push dates from main dashboard.
    
    Args:
        token: GitHub personal access token
        repo_data_with_dates: List of (repo_name, push_date) tuples
        commit_limit: Maximum number of commits to fetch
        debug_mode: Whether to use debug mode
        
    Returns:
        List of commit dictionaries
    """
    # Try debug mode first
    if debug_mode:
        debug_start_time = time.time()
        print(f"🔄 [COMMIT STREAM] DEBUG MODE: Reading from {COMMIT_STREAM_DEBUG_FILE}")
        commits = load_debug_commits(COMMIT_STREAM_DEBUG_FILE)
        if commits:
            debug_time = time.time() - debug_start_time
            print(f"📊 [COMMIT STREAM] DEBUG MODE: Loaded {len(commits)} commits in {debug_time:.3f}s from debug file")
            return commits
    
    print(f"🔄 [COMMIT STREAM] Starting commit stream data fetch with repo push date filtering")
    start_time = time.time()
    
    if not token and not debug_mode:
        print("❌ [COMMIT STREAM] No token provided")
        return []
    
    if not repo_data_with_dates:
        print("❌ [COMMIT STREAM] No repo data provided")
        return []
    
    try:
        # Filter repos to get only those pushed to recently
        active_repos = filter_recently_active_repos(repo_data_with_dates)
        if not active_repos:
            print("❌ [COMMIT STREAM] No repos found that were pushed to in the last week")
            return []
        
        # Get all commits from these recently active repositories
        commits = fetch_commits_for_repositories(token, active_repos, commit_limit)
        
        total_time = time.time() - start_time
        print(f"⏱️  [COMMIT STREAM] LIVE DATA: GitHub GraphQL API queries completed in {total_time:.2f}s")
        print(f"📊 [COMMIT STREAM] LIVE DATA: Final result: {len(commits)} commits from {len(active_repos)} recently active repos")
        
        # Save to debug file if not in debug mode
        if not debug_mode:
            save_debug_commits(COMMIT_STREAM_DEBUG_FILE, commits)
        
        return commits
        
    except Exception as e:
        total_time = time.time() - start_time
        print(f"❌ [COMMIT STREAM] Error after {total_time:.2f}s: {str(e)}")
        st.error(f"Error fetching commit stream: {str(e)}")
        return []


# =============================================================================
# Display Functions
# =============================================================================

def display_commit_stream(token: str, repo_data_with_dates: Optional[List[Tuple[str, str]]] = None, 
                         debug_mode: bool = False) -> List[Dict[str, Any]]:
    """
    Display the commit stream with proper formatting and controls.
    
    Args:
        token: GitHub personal access token
        repo_data_with_dates: Optional list of (repo_name, push_date) tuples from main dashboard
        debug_mode: Whether to use debug mode

    Returns:
        List of commit dictionaries that are being displayed in the stream
    """
    if not token and not debug_mode:
        st.warning("GitHub token required for commit stream")
        return []
    
    # Get commit data with timing
    fetch_start_time = time.time()
    
    if repo_data_with_dates:
        print(f"🔄 [COMMIT STREAM] Using {len(repo_data_with_dates)} repos with push dates from main dashboard")
        commits = get_commit_stream_data_from_repos(token, repo_data_with_dates, debug_mode=debug_mode)
    else:
        print(f"🔄 [COMMIT STREAM] No repo data provided, fetching independently")
        commits = get_commit_stream_data_standalone(token, debug_mode=debug_mode)
    
    fetch_time = time.time() - fetch_start_time
    
    print(f"🔄 [COMMIT STREAM] Retrieved {len(commits)} commits for display")
    if commits:
        first_commit = commits[0]
        repo_name = safe_get_commit_field(first_commit, 'repo', 'unknown')
        branch_name = safe_get_commit_field(first_commit, 'branch_name', 'unknown')
        message = safe_get_commit_field(first_commit, 'message', 'no message')
        print(f"🔄 [COMMIT STREAM] First commit sample: {repo_name}/{branch_name} - {message[:30]}...")
    
    if not commits:
        print(f"❌ [COMMIT STREAM] No commits found, showing info message")
        st.info(INFO_MESSAGES['no_commits_this_week'])
        return []

    # Filter commits to only show those from the LOOK_BACK_DAYS period
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=LOOK_BACK_DAYS)
    recent_commits = []
    
    for commit in commits:
        try:
            commit_date = datetime.fromisoformat(commit["date"].replace('Z', '+00:00'))
            if commit_date >= cutoff_date:
                recent_commits.append(commit)
        except Exception as e:
            print(f"Error parsing commit date '{commit.get('date', 'unknown')}': {e}")

    # Sort commits by date to ensure newest first
    commits_sorted = sorted(recent_commits, key=lambda x: x["date"], reverse=True)

    # Display header and stats on one line (using filtered count)
    debug_text = " *[DEBUG]*" if debug_mode else ""
    st.markdown(f"**🔄 Commits{debug_text} • {len(commits_sorted)} commits**")

    print(f"📅 [COMMIT STREAM] Filtered to {len(commits_sorted)} commits from last {LOOK_BACK_DAYS} days")
    if commits_sorted:
        print(f"📅 [COMMIT STREAM] Newest: {commits_sorted[0]['date']} | Oldest: {commits_sorted[-1]['date']}")
    
    # Create scrollable container
    container = st.container(height=STREAM_CONTAINER_HEIGHT)
    
    with container:
        for i, commit in enumerate(commits_sorted):
            commit_markdown = format_commit_for_stream(commit)
            st.markdown(commit_markdown, unsafe_allow_html=True)
            
            # Add separator except for last item
            if i < len(commits_sorted) - 1:
                st.markdown("---")

    # Return the commits data for use in charts
    return commits_sorted