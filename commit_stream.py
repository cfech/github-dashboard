import os
import requests
import streamlit as st
import time
from datetime import datetime, timezone, timedelta
from operator import itemgetter
from typing import List, Dict, Any, Optional

GRAPHQL_URL = os.getenv("GITHUB_GRAPHQL_URL", "https://api.github.com/graphql")
REQUEST_TIMEOUT = 30  # seconds


def _run_graphql_query_with_timeout(token: str, query: str, variables: dict = None, timeout: int = REQUEST_TIMEOUT):
    """Run a GraphQL query with timeout handling."""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    
    try:
        response = requests.post(GRAPHQL_URL, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error(f"Request timed out after {timeout} seconds")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"GraphQL request failed: {str(e)}")
        return None


def get_recently_active_repos_from_existing(repo_data_with_dates: List[tuple], days_back: int = 7) -> List[str]:
    """Filter repos to get those that have been pushed to in the last week (EST timezone)."""
    print(f"🔍 [COMMIT STREAM] Filtering {len(repo_data_with_dates)} repos for recent activity (past {days_back} days)")
    
    from datetime import datetime, timezone, timedelta
    
    # Calculate cutoff date (1 week ago in EST)
    now_utc = datetime.now(timezone.utc)
    cutoff_date = now_utc - timedelta(days=days_back)
    
    recent_repos = []
    
    for repo_name, pushed_at in repo_data_with_dates:
        if not pushed_at:  # Skip repos with no push date
            continue
            
        try:
            # Parse the push date and convert to UTC
            push_date = datetime.fromisoformat(pushed_at.replace('Z', '+00:00'))
            
            # Check if pushed in the last week
            if push_date >= cutoff_date:
                recent_repos.append(repo_name)
                days_ago = (now_utc - push_date).days
                hours_ago = (now_utc - push_date).total_seconds() / 3600
                if hours_ago < 24:
                    print(f"  ✅ {repo_name}: pushed {hours_ago:.1f} hours ago")
                else:
                    print(f"  ✅ {repo_name}: pushed {days_ago} days ago")
            else:
                days_ago = (now_utc - push_date).days
                print(f"  ❌ {repo_name}: pushed {days_ago} days ago (too old)")
                
        except Exception as e:
            print(f"  ⚠️  {repo_name}: Error parsing push date '{pushed_at}': {e}")
    
    print(f"📋 [COMMIT STREAM] Found {len(recent_repos)} repos pushed to in the last {days_back} days")
    if recent_repos:
        print(f"📋 [COMMIT STREAM] Recent repos: {recent_repos[:5]}{'...' if len(recent_repos) > 5 else ''}")
    
    return recent_repos

def get_recently_active_repos(token: str, days_back: int = 7, limit: int = 30) -> List[str]:
    """Get repositories that have been updated in the past week."""
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
    result = _run_graphql_query_with_timeout(token, query, variables)
    
    if not result or "data" not in result:
        print("❌ [COMMIT STREAM] No data returned from GraphQL query")
        return []
    
    repos = result.get("data", {}).get("viewer", {}).get("repositories", {}).get("nodes", [])
    print(f"📊 [COMMIT STREAM] Got {len(repos)} total repos from API")
    
    # Filter repos that were actually updated in the past week
    active_repos = []
    week_ago = datetime.now(timezone.utc) - timedelta(days=days_back)
    
    for repo in repos:
        if repo.get("pushedAt"):
            pushed_at = datetime.fromisoformat(repo["pushedAt"].replace('Z', '+00:00'))
            days_since = (datetime.now(timezone.utc) - pushed_at).days
            print(f"  📦 {repo['nameWithOwner']}: pushed {days_since} days ago ({repo['pushedAt']})")
            
            if pushed_at >= week_ago:
                active_repos.append(repo["nameWithOwner"])
                print(f"    ✅ Added to active repos")
            else:
                print(f"    ❌ Too old, skipping")
        else:
            print(f"  📦 {repo.get('nameWithOwner', 'Unknown')}: No push date")
    
    print(f"🎯 [COMMIT STREAM] Found {len(active_repos)} recently active repos: {active_repos}")
    return active_repos


def get_all_commits_for_repos(token: str, repo_names: List[str], commit_limit: int = 100) -> List[Dict[str, Any]]:
    """Get all commits from all branches for specified repositories."""
    print(f"🔍 [COMMIT STREAM] Fetching commits for {len(repo_names)} repos, limit {commit_limit}")
    
    if not token or not repo_names:
        print("❌ [COMMIT STREAM] No token or no repos provided")
        return []
    
    # Limit to 5 repos to avoid timeout
    limited_repos = repo_names[:5]
    print(f"📋 [COMMIT STREAM] Limited to {len(limited_repos)} repos: {limited_repos}")
    
    # Build query for multiple repositories and all their branches
    repo_queries = []
    for i, repo_name in enumerate(limited_repos):
        owner, name = repo_name.split('/', 1)
        commits_per_repo = min(commit_limit // len(limited_repos), 25)  # Increased from 10 to 25
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
    
    query = f"""
    query {{
      {' '.join(repo_queries)}
    }}
    """
    
    print(f"🔄 [COMMIT STREAM] Executing GraphQL query with 45s timeout...")
    start_time = time.time()
    result = _run_graphql_query_with_timeout(token, query, timeout=45)  # Longer timeout for complex query
    query_time = time.time() - start_time
    print(f"⏱️  [COMMIT STREAM] GraphQL query completed in {query_time:.2f}s")
    
    if not result or "data" not in result:
        print("❌ [COMMIT STREAM] No data returned from commits query")
        return []
    
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
                        "message": commit["messageHeadline"],
                        "author": commit.get("author", {}).get("name", "Unknown") if commit.get("author") else "Unknown",
                        "date": commit["committedDate"],
                        "url": commit["url"]
                    }
                    all_commits.append(commit_data)
            else:
                print(f"    🌿 {branch_name}: No commit history available")
    
    print(f"📊 [COMMIT STREAM] Collected {len(all_commits)} total commits from all branches")
    
    # Sort by date (most recent first) - show ALL commits, no limit
    sorted_commits = sorted(all_commits, key=lambda x: x["date"], reverse=True)
    
    print(f"🎯 [COMMIT STREAM] Returning ALL {len(sorted_commits)} commits (no limit)")
    if sorted_commits:
        print(f"  📅 Newest: {sorted_commits[0]['repo']}/{sorted_commits[0]['branch_name']} - {sorted_commits[0]['date']}")
        print(f"  📅 Oldest: {sorted_commits[-1]['repo']}/{sorted_commits[-1]['branch_name']} - {sorted_commits[-1]['date']}")
    
    return sorted_commits


def format_commit_for_stream(commit: Dict[str, Any], is_today: bool) -> str:
    """Format a single commit for the stream display."""
    from dashboard_app_graphql import _format_timestamp_to_local
    
    formatted_date = _format_timestamp_to_local(commit["date"])
    date_part = formatted_date.split()[0]  # Just the date part (YYYY-MM-DD)
    time_part = " ".join(formatted_date.split()[1:3])  # Time and AM/PM
    
    # Truncate long commit messages for right sidebar
    message = commit["message"]
    if len(message) > 30:
        message = message[:27] + "..."
    
    # Simplified display for right sidebar
    repo_name = commit["repo"].split("/")[-1]
    branch_name = commit["branch_name"]
    author = commit["author"]
    sha = commit["sha"]
    
    # Create compact format with date
    today_badge = "🔥" if is_today else "•"
    
    return f"""{today_badge} **[{repo_name}]({commit["repo_url"]})** `{branch_name}`  
*{message}*  
`{sha}` {author}  
📅 {date_part} {time_part}"""


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_commit_stream_data(token: str, days_back: int = 7, commit_limit: int = 100, debug_mode: bool = False) -> List[Dict[str, Any]]:
    """Get commit stream data with caching."""
    import os
    import json
    
    cs_debug_file = os.getcwd() + "/cs_debug.json"
    
    # Check if debug mode is enabled and file exists
    if debug_mode and os.path.exists(cs_debug_file):
        debug_start_time = time.time()
        print(f"🔄 [COMMIT STREAM] DEBUG MODE: Reading from {cs_debug_file}")
        try:
            with open(cs_debug_file, 'r') as f:
                debug_data = json.load(f)
            commits = debug_data.get("commits", [])
            debug_time = time.time() - debug_start_time
            print(f"📊 [COMMIT STREAM] DEBUG MODE: Loaded {len(commits)} commits in {debug_time:.3f}s from debug file")
            return commits
        except Exception as e:
            print(f"❌ [COMMIT STREAM] DEBUG MODE: Error reading debug file: {str(e)}")
            # Fall through to live data fetching
    
    if not token:
        return []
    
    try:
        # Get recently active repositories
        active_repos = get_recently_active_repos(token, days_back)
        if not active_repos:
            return []
        
        # Get all commits from these repositories
        commits = get_all_commits_for_repos(token, active_repos, commit_limit)
        
        # Save to debug file if not in debug mode (for future debug use)
        if not debug_mode:
            try:
                save_start = time.time()
                debug_data = {"commits": commits}
                with open(cs_debug_file, 'w') as f:
                    json.dump(debug_data, f, indent=4)
                save_time = time.time() - save_start
                print(f"💾 [COMMIT STREAM] Saved {len(commits)} commits to {cs_debug_file} in {save_time:.3f}s")
            except Exception as e:
                print(f"❌ [COMMIT STREAM] Error saving debug file: {str(e)}")
        
        return commits
        
    except Exception as e:
        st.error(f"Error fetching commit stream: {str(e)}")
        return []


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_commit_stream_data_from_repos(token: str, repo_data_with_dates: List[tuple], commit_limit: int = 100, debug_mode: bool = False) -> List[Dict[str, Any]]:
    """Get commit stream data using repo data with push dates."""
    import os
    import json
    
    cs_debug_file = os.getcwd() + "/cs_debug.json"
    
    # Check if debug mode is enabled and file exists
    if debug_mode and os.path.exists(cs_debug_file):
        debug_start_time = time.time()
        print(f"🔄 [COMMIT STREAM] DEBUG MODE: Reading from {cs_debug_file}")
        try:
            with open(cs_debug_file, 'r') as f:
                debug_data = json.load(f)
            commits = debug_data.get("commits", [])
            debug_time = time.time() - debug_start_time
            print(f"📊 [COMMIT STREAM] DEBUG MODE: Loaded {len(commits)} commits in {debug_time:.3f}s from debug file")
            return commits
        except Exception as e:
            print(f"❌ [COMMIT STREAM] DEBUG MODE: Error reading debug file: {str(e)}")
            # Fall through to live data fetching
    
    print(f"🔄 [COMMIT STREAM] Starting commit stream data fetch with repo push date filtering")
    start_time = time.time()
    
    if not token and not debug_mode:
        print("❌ [COMMIT STREAM] No token provided")
        return []
    
    if not repo_data_with_dates:
        print("❌ [COMMIT STREAM] No repo data provided")
        return []
    
    try:
        # Filter repos to get only those pushed to in the last week (EST)
        active_repos = get_recently_active_repos_from_existing(repo_data_with_dates)
        if not active_repos:
            print("❌ [COMMIT STREAM] No repos found that were pushed to in the last week")
            return []
        
        # Get all commits from these recently active repositories
        commits = get_all_commits_for_repos(token, active_repos, commit_limit)
        
        total_time = time.time() - start_time
        print(f"⏱️  [COMMIT STREAM] LIVE DATA: GitHub GraphQL API queries completed in {total_time:.2f}s")
        print(f"📊 [COMMIT STREAM] LIVE DATA: Final result: {len(commits)} commits from {len(active_repos)} recently active repos")
        
        # Save to debug file if not in debug mode (for future debug use)
        if not debug_mode:
            try:
                save_start = time.time()
                debug_data = {"commits": commits}
                with open(cs_debug_file, 'w') as f:
                    json.dump(debug_data, f, indent=4)
                save_time = time.time() - save_start
                print(f"💾 [COMMIT STREAM] Saved {len(commits)} commits to {cs_debug_file} in {save_time:.3f}s")
            except Exception as e:
                print(f"❌ [COMMIT STREAM] Error saving debug file: {str(e)}")
        
        return commits
        
    except Exception as e:
        total_time = time.time() - start_time
        print(f"❌ [COMMIT STREAM] Error after {total_time:.2f}s: {str(e)}")
        st.error(f"Error fetching commit stream: {str(e)}")
        return []


def display_commit_stream(token: str, repo_data_with_dates: list = None, debug_mode: bool = False):
    """Display the commit stream on the right side of the screen."""
    st.subheader("🔄 Live Commit Stream")
    if debug_mode:
        st.markdown("*Recent commits from all branches* **[DEBUG MODE]**")
    else:
        st.markdown("*Recent commits from all branches*")
    
    if not token and not debug_mode:
        st.warning("GitHub token required for commit stream")
        return
    
    # Get commit data with timing - use repo data with push dates
    fetch_start_time = time.time()
    
    if repo_data_with_dates:
        print(f"🔄 [COMMIT STREAM] Using {len(repo_data_with_dates)} repos with push dates from main dashboard")
        commits = get_commit_stream_data_from_repos(token, repo_data_with_dates, debug_mode=debug_mode)
    else:
        print(f"🔄 [COMMIT STREAM] No repo data provided, fetching independently")
        commits = get_commit_stream_data(token, debug_mode=debug_mode)
    
    fetch_time = time.time() - fetch_start_time
    
    print(f"🔄 [COMMIT STREAM] Retrieved {len(commits)} commits for display")
    if commits:
        print(f"🔄 [COMMIT STREAM] First commit sample: {commits[0].get('repo', 'unknown')}/{commits[0].get('branch_name', 'unknown')} - {commits[0].get('message', 'no message')[:30]}...")
    
    if not commits:
        print(f"❌ [COMMIT STREAM] No commits found, showing info message")
        st.info("No recent commits found")
        return
    
    # Display stats and controls in a compact layout
    if debug_mode:
        st.markdown(f"**{len(commits)} commits** • 🐛 *DEBUG MODE* • ⏱️ *{fetch_time:.1f}s*")
        st.info("Using cached data from cs_debug.json")
    else:
        st.markdown(f"**{len(commits)} commits** • ⏱️ *GitHub API: {fetch_time:.1f}s*")
    
    # Add refresh button
    if st.button("🔄 Refresh Stream", key="refresh_stream"):
        st.cache_data.clear()
        st.rerun()
    
    # Sort commits by date to ensure newest first (in case they're not already sorted)
    commits_sorted = sorted(commits, key=lambda x: x["date"], reverse=True)
    today = datetime.now().date()
    
    print(f"📅 [COMMIT STREAM] Displaying {len(commits_sorted)} commits sorted by date")
    if commits_sorted:
        print(f"📅 [COMMIT STREAM] Newest: {commits_sorted[0]['date']} | Oldest: {commits_sorted[-1]['date']}")
    
    # Create a scrollable container using st.container with 60vh height
    container = st.container(height=800)
    
    with container:
        # Display ALL commits using Streamlit's native markdown (ensures proper rendering)
        for i, commit in enumerate(commits_sorted):
            # Check if commit is from today
            commit_utc = datetime.fromisoformat(commit['date'].replace('Z', '+00:00'))
            commit_local = commit_utc.replace(tzinfo=timezone.utc).astimezone()
            is_today = commit_local.date() == today
            
            # Format the commit using the existing function (ensures proper markdown rendering)
            commit_markdown = format_commit_for_stream(commit, is_today)
            st.markdown(commit_markdown)
            
            # Add separator except for last item
            if i < len(commits_sorted) - 1:
                st.markdown("---")