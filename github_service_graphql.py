"""
GitHub GraphQL Service Module

This module provides functions for interacting with the GitHub GraphQL API
to fetch repository data, commits, and pull requests.
"""

import os
import requests
from operator import itemgetter
from typing import List, Dict, Any, Optional, Tuple

# Import shared modules
from constants import (
    GITHUB_API_URL, REQUEST_TIMEOUT, ERROR_MESSAGES, GRAPHQL_FRAGMENTS,
    DEFAULT_DISPLAY_COUNT
)
from utils import safe_get_commit_field


# =============================================================================
# Core GraphQL Functions
# =============================================================================

def execute_graphql_query(token: str, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Execute a GraphQL query against the GitHub API.
    
    Args:
        token: GitHub personal access token
        query: GraphQL query string
        variables: Optional query variables
        
    Returns:
        Query result dictionary
        
    Raises:
        requests.HTTPError: If the request fails
    """
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    
    response = requests.post(GITHUB_API_URL, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


# =============================================================================
# Repository Discovery Functions
# =============================================================================

def fetch_user_affiliated_repositories(token: str) -> Dict[str, str]:
    """
    Fetch repositories directly affiliated with the authenticated user.
    
    Args:
        token: GitHub personal access token
        
    Returns:
        Dictionary mapping repository names to push dates
    """
    repositories_with_push_dates = {}
    has_next_page = True
    end_cursor = None
    
    while has_next_page:
        query = f"""
        query($endCursor: String) {{
          viewer {{
            repositories(
              first: 100, 
              after: $endCursor, 
              affiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER], 
              orderBy: {{field: PUSHED_AT, direction: DESC}}
            ) {{
              nodes {{
                {GRAPHQL_FRAGMENTS['repository_fields']}
              }}
              pageInfo {{
                hasNextPage
                endCursor
              }}
            }}
          }}
        }}
        """
        
        variables = {"endCursor": end_cursor}
        result = execute_graphql_query(token, query, variables)
        
        data = result.get("data", {}).get("viewer", {}).get("repositories", {})
        nodes = data.get("nodes", [])
        
        for repo in nodes:
            repo_name = repo["nameWithOwner"]
            push_date = repo["pushedAt"]
            repositories_with_push_dates[repo_name] = push_date
        
        page_info = data.get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        end_cursor = page_info.get("endCursor")
    
    return repositories_with_push_dates


def fetch_user_organizations(token: str) -> List[str]:
    """
    Fetch all organizations the authenticated user belongs to.
    
    Args:
        token: GitHub personal access token
        
    Returns:
        List of organization login names
    """
    organization_logins = []
    has_next_page = True
    end_cursor = None
    
    while has_next_page:
        query = """
        query($endCursor: String) {
          viewer {
            organizations(first: 100, after: $endCursor) {
              nodes {
                login
              }
              pageInfo {
                hasNextPage
                endCursor
              }
            }
          }
        }
        """
        
        variables = {"endCursor": end_cursor}
        result = execute_graphql_query(token, query, variables)
        
        data = result.get("data", {}).get("viewer", {}).get("organizations", {})
        nodes = data.get("nodes", [])
        
        for org in nodes:
            organization_logins.append(org["login"])
        
        page_info = data.get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        end_cursor = page_info.get("endCursor")
    
    return organization_logins


def fetch_organization_repositories(token: str, org_login: str) -> Dict[str, str]:
    """
    Fetch repositories for a specific organization.
    
    Args:
        token: GitHub personal access token
        org_login: Organization login name
        
    Returns:
        Dictionary mapping repository names to push dates
    """
    print(f"Fetching repositories for organization: {org_login}...")
    repositories_with_push_dates = {}
    has_next_page = True
    end_cursor = None
    
    while has_next_page:
        query = f"""
        query($orgLogin: String!, $endCursor: String) {{
          organization(login: $orgLogin) {{
            repositories(
              first: 100, 
              after: $endCursor, 
              orderBy: {{field: PUSHED_AT, direction: DESC}}
            ) {{
              nodes {{
                {GRAPHQL_FRAGMENTS['repository_fields']}
              }}
              pageInfo {{
                hasNextPage
                endCursor
              }}
            }}
          }}
        }}
        """
        
        variables = {"orgLogin": org_login, "endCursor": end_cursor}
        result = execute_graphql_query(token, query, variables)
        
        if not result or not result.get("data", {}).get("organization"):
            break
            
        data = result.get("data", {}).get("organization", {}).get("repositories", {})
        nodes = data.get("nodes", [])
        
        for repo in nodes:
            repo_name = repo["nameWithOwner"]
            push_date = repo["pushedAt"]
            repositories_with_push_dates[repo_name] = push_date
        
        page_info = data.get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        end_cursor = page_info.get("endCursor")
    
    return repositories_with_push_dates


def determine_organizations_to_fetch(token: str, specific_org_logins: Optional[List[str]]) -> List[str]:
    """
    Determine which organizations to fetch repositories from.
    
    Args:
        token: GitHub personal access token
        specific_org_logins: Optional list of specific organization logins
        
    Returns:
        List of organization logins to fetch repositories from
    """
    if specific_org_logins is not None:
        return specific_org_logins
    else:
        return fetch_user_organizations(token)


# =============================================================================
# Main Repository Data Functions
# =============================================================================

def get_all_accessible_repository_names(token: str, specific_org_logins: Optional[List[str]] = None) -> List[str]:
    """
    Get all accessible repository names with pagination support.
    
    This function fetches repositories the user has access to through direct affiliation
    and organization membership.
    
    Args:
        token: GitHub personal access token
        specific_org_logins: Optional list of specific organization logins to fetch from
        
    Returns:
        List of repository names sorted by most recent push date
    """
    print("Fetching all accessible repository names...")
    all_repositories_with_push_dates = {}
    
    # Phase 1: Fetch repositories directly affiliated with the user
    user_repos = fetch_user_affiliated_repositories(token)
    all_repositories_with_push_dates.update(user_repos)
    
    # Phase 2: Fetch repositories from organizations
    organizations_to_fetch = determine_organizations_to_fetch(token, specific_org_logins)
    
    for org_login in organizations_to_fetch:
        org_repos = fetch_organization_repositories(token, org_login)
        all_repositories_with_push_dates.update(org_repos)
    
    # Sort repositories by push date (most recent first)
    sorted_repositories = sorted(
        all_repositories_with_push_dates.items(),
        key=lambda item: item[1] if item[1] else "",
        reverse=True
    )
    
    repository_names = [repo_name for repo_name, _ in sorted_repositories]
    
    print(f"Fetched {len(repository_names)} total repositories.")
    return repository_names


def get_all_accessible_repository_data(token: str, specific_org_logins: Optional[List[str]] = None) -> List[Tuple[str, str]]:
    """
    Get all accessible repository data including names and push dates.
    
    This function fetches repositories with their push dates for more efficient
    processing by other components.
    
    Args:
        token: GitHub personal access token
        specific_org_logins: Optional list of specific organization logins to fetch from
        
    Returns:
        List of (repository_name, push_date) tuples sorted by most recent push date
    """
    print("Fetching all accessible repository data with push dates...")
    all_repositories_with_push_dates = {}
    
    # Phase 1: Fetch repositories directly affiliated with the user
    user_repos = fetch_user_affiliated_repositories(token)
    all_repositories_with_push_dates.update(user_repos)
    
    # Phase 2: Fetch repositories from organizations
    organizations_to_fetch = determine_organizations_to_fetch(token, specific_org_logins)
    
    for org_login in organizations_to_fetch:
        org_repos = fetch_organization_repositories(token, org_login)
        all_repositories_with_push_dates.update(org_repos)
    
    # Sort repositories by push date (most recent first)
    sorted_repositories = sorted(
        all_repositories_with_push_dates.items(),
        key=lambda item: item[1] if item[1] else "",
        reverse=True
    )
    
    print(f"Fetched {len(sorted_repositories)} total repositories with push dates.")
    return sorted_repositories


# =============================================================================
# Bulk Data Fetching Functions
# =============================================================================

def build_bulk_data_query(repository_names: List[str], commit_limit: int = 100, pr_limit: int = 20) -> str:
    """
    Build a GraphQL query to fetch bulk data from multiple repositories.
    
    Args:
        repository_names: List of repository names in "owner/name" format
        commit_limit: Maximum commits to fetch per repository
        pr_limit: Maximum pull requests to fetch per repository
        
    Returns:
        Complete GraphQL query string
    """
    query_parts = []
    
    for i, repo_name in enumerate(repository_names):
        try:
            owner, name = repo_name.split("/", 1)
        except ValueError:
            continue
            
        alias = f"repo{i}"
        query_parts.append(f"""
            {alias}: repository(owner: "{owner}", name: "{name}") {{
                ...repositoryDataFields
            }}
        """)
    
    all_queries = "\n".join(query_parts)
    
    return f"""
        query {{
            {all_queries}
        }}

        fragment repositoryDataFields on Repository {{
            nameWithOwner
            url
            openPRs: pullRequests(
                states: [OPEN], 
                first: {pr_limit}, 
                orderBy: {{field: CREATED_AT, direction: DESC}}
            ) {{
                nodes {{
                    {GRAPHQL_FRAGMENTS['pull_request_fields']}
                }}
            }}
            mergedPRs: pullRequests(
                states: [MERGED], 
                first: {pr_limit}, 
                orderBy: {{field: CREATED_AT, direction: DESC}}
            ) {{
                nodes {{
                    {GRAPHQL_FRAGMENTS['pull_request_fields']}
                }}
            }}
            defaultBranchRef {{
                name
                target {{
                    ... on Commit {{
                        history(first: {commit_limit}) {{
                            nodes {{
                                {GRAPHQL_FRAGMENTS['commit_fields']}
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """


def parse_pull_requests_from_repository(repo_data: Dict, repo_name: str, repo_url: str, 
                                       pr_type: str) -> List[Dict[str, Any]]:
    """
    Parse pull request data from a repository's GraphQL response.
    
    Args:
        repo_data: Repository data from GraphQL response
        repo_name: Repository name
        repo_url: Repository URL
        pr_type: Type of PRs to parse ("openPRs" or "mergedPRs")
        
    Returns:
        List of pull request dictionaries
    """
    pull_requests = []
    date_field = "createdAt" if pr_type == "openPRs" else "mergedAt"
    
    for pr_node in repo_data.get(pr_type, {}).get("nodes", []):
        author_info = pr_node.get("author")
        author_login = "Unknown"
        if author_info and author_info.get("login"):
            author_login = author_info["login"]
        
        pull_request = {
            "repo": repo_name,
            "repo_url": repo_url,
            "pr_number": pr_node["number"],
            "title": pr_node["title"],
            "author": author_login,
            "date": pr_node[date_field],
            "url": pr_node["url"]
        }
        pull_requests.append(pull_request)
    
    return pull_requests


def parse_commits_from_repository(repo_data: Dict, repo_name: str, repo_url: str) -> List[Dict[str, Any]]:
    """
    Parse commit data from a repository's GraphQL response.
    
    Args:
        repo_data: Repository data from GraphQL response
        repo_name: Repository name
        repo_url: Repository URL
        
    Returns:
        List of commit dictionaries
    """
    commits = []
    default_branch_ref = repo_data.get("defaultBranchRef")
    
    if not default_branch_ref:
        return commits
    
    branch_name = default_branch_ref.get("name", "main")
    branch_url = f"{repo_url}/tree/{branch_name}"
    
    history = default_branch_ref.get("target", {}).get("history", {})
    
    for commit_node in history.get("nodes", []):
        author_info = commit_node.get("author", {})
        author_name = safe_get_commit_field(author_info, "name", "Unknown")
        
        commit = {
            "repo": repo_name,
            "repo_url": repo_url,
            "branch_name": branch_name,
            "branch_url": branch_url,
            "sha": commit_node["oid"][:7],
            "message": safe_get_commit_field(commit_node, "messageHeadline", "No message"),
            "author": author_name,
            "date": commit_node["committedDate"],
            "url": commit_node["url"]
        }
        commits.append(commit)
    
    return commits


def get_bulk_repository_data(token: str, repository_names: List[str], 
                           commit_limit: int = 100, pr_limit: int = 20) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Fetch commits, open PRs, and merged PRs for multiple repositories in a single query.
    
    Args:
        token: GitHub personal access token
        repository_names: List of repository names to fetch data for
        commit_limit: Maximum commits to fetch per repository
        pr_limit: Maximum pull requests to fetch per repository
        
    Returns:
        Tuple of (commits, open_prs, merged_prs) lists
    """
    if not repository_names:
        return [], [], []
    
    print(f"Fetching bulk data for {len(repository_names)} repositories...")
    
    query = build_bulk_data_query(repository_names, commit_limit, pr_limit)
    result = execute_graphql_query(token, query)
    
    all_commits = []
    all_open_prs = []
    all_merged_prs = []
    
    repository_data = result.get("data", {})
    
    for repo_alias, repo_info in repository_data.items():
        if not repo_info:
            continue
        
        repo_name = repo_info["nameWithOwner"]
        repo_url = repo_info["url"]
        
        # Parse open pull requests
        open_prs = parse_pull_requests_from_repository(repo_info, repo_name, repo_url, "openPRs")
        all_open_prs.extend(open_prs)
        
        # Parse merged pull requests
        merged_prs = parse_pull_requests_from_repository(repo_info, repo_name, repo_url, "mergedPRs")
        all_merged_prs.extend(merged_prs)
        
        # Parse commits
        commits = parse_commits_from_repository(repo_info, repo_name, repo_url)
        all_commits.extend(commits)
    
    # Sort all data by date (most recent first)
    sorted_commits = sorted(all_commits, key=itemgetter("date"), reverse=True)
    sorted_open_prs = sorted(all_open_prs, key=itemgetter("date"), reverse=True)
    sorted_merged_prs = sorted(all_merged_prs, key=itemgetter("date"), reverse=True)
    
    return sorted_commits, sorted_open_prs, sorted_merged_prs


# =============================================================================
# Legacy Function Aliases (for backwards compatibility)
# =============================================================================

# Keep old function names as aliases to avoid breaking existing code
get_all_accessible_repo_names = get_all_accessible_repository_names
get_all_accessible_repo_data = get_all_accessible_repository_data
get_bulk_data = get_bulk_repository_data
_run_graphql_query = execute_graphql_query
_build_bulk_query = build_bulk_data_query