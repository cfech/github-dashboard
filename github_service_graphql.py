import os
import requests
from operator import itemgetter

GRAPHQL_URL = os.getenv("GITHUB_GRAPHQL_URL","https://api.github.com/graphql")

def _run_graphql_query(token: str, query: str, variables: dict = None):
    """A helper function to run a GraphQL query with variables."""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    response = requests.post(GRAPHQL_URL, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()

def get_all_accessible_repo_names(token: str, specific_org_logins: list[str] | None = None):
    """Gets all accessible repo names using GraphQL with pagination, including those accessible via organization membership and teams.
    If specific_org_logins is provided, only repos from those organizations will be fetched in addition to direct repos.
    """
    all_repo_names = set() # Use a set to automatically handle deduplication
    all_repos_with_pushed_at = {}
    print("Fetching all accessible repository names...")

    # --- Phase 1: Fetch repositories directly affiliated with the user ---
    has_next_page = True
    end_cursor = None
    while has_next_page:
        query = """
        query($endCursor: String) {
          viewer {
            repositories(first: 100, after: $endCursor, affiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER], orderBy: {field: PUSHED_AT, direction: DESC}) {
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
        variables = {"endCursor": end_cursor}
        result = _run_graphql_query(token, query, variables)
        data = result.get("data", {}).get("viewer", {}).get("repositories", {})
        nodes = data.get("nodes", [])
        for repo in nodes:
            all_repos_with_pushed_at[repo["nameWithOwner"]] = repo["pushedAt"]

        page_info = data.get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        end_cursor = page_info.get("endCursor")

    # --- Phase 2: Fetch repositories from specified organizations ---
    org_logins_to_fetch = []
    if specific_org_logins is not None: # If a list is provided (even empty), use it
        org_logins_to_fetch = specific_org_logins
    else: # If specific_org_logins is None, fetch all organizations
        has_next_org_page = True
        org_end_cursor = None
        while has_next_org_page:
            org_query = """
            query($orgEndCursor: String) {
              viewer {
                organizations(first: 100, after: $orgEndCursor) {
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
            org_variables = {"orgEndCursor": org_end_cursor}
            org_result = _run_graphql_query(token, org_query, org_variables)
            org_data = org_result.get("data", {}).get("viewer", {}).get("organizations", {})
            org_nodes = org_data.get("nodes", [])
            for org in org_nodes:
                org_logins_to_fetch.append(org["login"])

            org_page_info = org_data.get("pageInfo", {})
            has_next_org_page = org_page_info.get("hasNextPage", False)
            org_end_cursor = org_page_info.get("endCursor")

    # Now, for each organization in the determined list, fetch its repositories
    for org_login in org_logins_to_fetch:
        print(f"Fetching repositories for organization: {org_login}...")
        has_next_repo_page = True
        repo_end_cursor = None
        while has_next_repo_page:
            org_repo_query = """
            query($orgLogin: String!, $repoEndCursor: String) {
              organization(login: $orgLogin) {
                repositories(first: 100, after: $repoEndCursor, orderBy: {field: PUSHED_AT, direction: DESC}) {
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
            org_repo_variables = {"orgLogin": org_login, "repoEndCursor": repo_end_cursor}
            org_repo_result = _run_graphql_query(token, org_repo_query, org_repo_variables)
            org_repo_data = org_repo_result.get("data", {}).get("organization", {}).get("repositories", {})
            org_repo_nodes = org_repo_data.get("nodes", [])
            for repo in org_repo_nodes:
                all_repos_with_pushed_at[repo["nameWithOwner"]] = repo["pushedAt"]

            org_repo_page_info = org_repo_data.get("pageInfo", {})
            has_next_repo_page = org_repo_page_info.get("hasNextPage", False)
            repo_end_cursor = org_repo_page_info.get("endCursor")

    # Sort all repositories by pushedAt before returning
    sorted_repos = sorted(all_repos_with_pushed_at.items(), key=lambda item: item[1] if item[1] else "", reverse=True)
    final_repo_names = [repo_name for repo_name, _ in sorted_repos]

    print(f"Fetched {len(final_repo_names)} total repositories.")
    return final_repo_names

def get_all_accessible_repo_data(token: str, specific_org_logins: list[str] | None = None):
    """Gets all accessible repo data including names and push dates, sorted by most recent push."""
    all_repo_names = set()
    all_repos_with_pushed_at = {}
    print("Fetching all accessible repository data with push dates...")

    # --- Phase 1: Fetch repositories directly affiliated with the user ---
    has_next_page = True
    end_cursor = None
    while has_next_page:
        query = """
        query($endCursor: String) {
          viewer {
            repositories(first: 100, after: $endCursor, affiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER], orderBy: {field: PUSHED_AT, direction: DESC}) {
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
        variables = {"endCursor": end_cursor}
        result = _run_graphql_query(token, query, variables)
        data = result.get("data", {}).get("viewer", {}).get("repositories", {})
        nodes = data.get("nodes", [])
        for repo in nodes:
            all_repos_with_pushed_at[repo["nameWithOwner"]] = repo["pushedAt"]

        page_info = data.get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        end_cursor = page_info.get("endCursor")

    # --- Phase 2: Fetch repositories from specified organizations ---
    org_logins_to_fetch = []
    if specific_org_logins is not None:
        org_logins_to_fetch = specific_org_logins
    else:
        has_next_org_page = True
        org_end_cursor = None
        while has_next_org_page:
            org_query = """
            query($orgEndCursor: String) {
              viewer {
                organizations(first: 100, after: $orgEndCursor) {
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
            org_variables = {"orgEndCursor": org_end_cursor}
            org_result = _run_graphql_query(token, org_query, org_variables)
            org_data = org_result.get("data", {}).get("viewer", {}).get("organizations", {})
            org_nodes = org_data.get("nodes", [])
            for org in org_nodes:
                org_logins_to_fetch.append(org["login"])

            org_page_info = org_data.get("pageInfo", {})
            has_next_org_page = org_page_info.get("hasNextPage", False)
            org_end_cursor = org_page_info.get("endCursor")

    # Now, for each organization in the determined list, fetch its repositories
    for org_login in org_logins_to_fetch:
        print(f"Fetching repositories for organization: {org_login}...")
        has_next_repo_page = True
        repo_end_cursor = None
        while has_next_repo_page:
            org_repo_query = """
            query($orgLogin: String!, $repoEndCursor: String) {
              organization(login: $orgLogin) {
                repositories(first: 100, after: $repoEndCursor, orderBy: {field: PUSHED_AT, direction: DESC}) {
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
            org_repo_variables = {"orgLogin": org_login, "repoEndCursor": repo_end_cursor}
            org_repo_result = _run_graphql_query(token, org_repo_query, org_repo_variables)
            org_repo_data = org_repo_result.get("data", {}).get("organization", {}).get("repositories", {})
            org_repo_nodes = org_repo_data.get("nodes", [])
            for repo in org_repo_nodes:
                all_repos_with_pushed_at[repo["nameWithOwner"]] = repo["pushedAt"]

            org_repo_page_info = org_repo_data.get("pageInfo", {})
            has_next_repo_page = org_repo_page_info.get("hasNextPage", False)
            repo_end_cursor = org_repo_page_info.get("endCursor")

    # Sort all repositories by pushedAt before returning
    sorted_repos = sorted(all_repos_with_pushed_at.items(), key=lambda item: item[1] if item[1] else "", reverse=True)
    
    print(f"Fetched {len(sorted_repos)} total repositories with push dates.")
    return sorted_repos  # Returns list of (repo_name, pushed_at) tuples

def _build_bulk_query(repo_names: list[str], commit_limit: int, pr_limit: int):
    """Dynamically builds the bulk query string for commits and PRs."""
    query_parts = []
    for i, name in enumerate(repo_names):
        owner, repo_name = name.split("/")
        alias = f"repo{i}"
        query_parts.append(f'''
            {alias}: repository(owner: "{owner}", name: "{repo_name}") {{
                ...repoFields
            }}
        ''')

    all_queries = "\n".join(query_parts)
    return f"""
        query {{
            {all_queries}
        }}

        fragment repoFields on Repository {{
            nameWithOwner
            url
            openPRs: pullRequests(states: [OPEN], first: {pr_limit}, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
                ...prFields
            }}
            mergedPRs: pullRequests(states: [MERGED], first: {pr_limit}, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
                ...prFields
            }}
            defaultBranchRef {{
                name
                target {{
                    ... on Commit {{
                        history(first: {commit_limit}) {{
                            nodes {{
                                oid
                                url
                                messageHeadline
                                committedDate
                                author {{ name }}
                            }}
                        }}
                    }}
                }}
            }}
        }}

        fragment prFields on PullRequestConnection {{
            nodes {{
                number
                title
                url
                author {{ login }}
                createdAt
                mergedAt
            }}
        }}
    """

def get_bulk_data(token: str, repo_names: list[str], commit_limit: int = 100, pr_limit: int = 20):
    """Fetches commits, open PRs, and merged PRs for a list of repos."""
    if not repo_names:
        return [], [], []

    bulk_query = _build_bulk_query(repo_names, commit_limit, pr_limit)
    print(f"Fetching bulk data for {len(repo_names)} repositories...")
    result = _run_graphql_query(token, bulk_query)

    all_commits, all_open_prs, all_merged_prs = [], [], []
    repo_data = result.get("data", {})

    for repo_alias in repo_data:
        repo = repo_data[repo_alias]
        if not repo:
            continue

        repo_name = repo["nameWithOwner"]
        repo_url = repo["url"]
        default_branch_ref = repo.get("defaultBranchRef")
        branch_name = default_branch_ref.get("name") if default_branch_ref else None
        branch_url = f"{repo_url}/tree/{branch_name}" if branch_name else None

        # Parse Open PRs
        for pr_node in repo.get("openPRs", {}).get("nodes", []):
            all_open_prs.append({
                "repo": repo_name, "repo_url": repo_url,
                "pr_number": pr_node["number"], "title": pr_node["title"],
                "author": pr_node["author"]["login"] if pr_node.get("author") and pr_node["author"] else "n/a",
                "date": pr_node["createdAt"], "url": pr_node["url"]
            })

        # Parse Merged PRs
        for pr_node in repo.get("mergedPRs", {}).get("nodes", []):
            all_merged_prs.append({
                "repo": repo_name, "repo_url": repo_url,
                "pr_number": pr_node["number"], "title": pr_node["title"],
                "author": pr_node["author"]["login"] if pr_node.get("author") and pr_node["author"] else "n/a",
                "date": pr_node["mergedAt"], "url": pr_node["url"]
            })

        # Parse commits
        history = repo.get("defaultBranchRef", {}).get("target", {}).get("history", {})
        for commit_node in history.get("nodes", []):
            all_commits.append({
                "repo": repo_name, "repo_url": repo_url,
                "branch_name": branch_name, "branch_url": branch_url,
                "sha": commit_node["oid"][:7], "message": commit_node["messageHeadline"],
                "author": commit_node.get("author", {}).get("name", "n/a") if commit_node.get("author") else "n/a",
                "date": commit_node["committedDate"], "url": commit_node["url"]
            })

    # Sort all by date
    sorted_commits = sorted(all_commits, key=itemgetter("date"), reverse=True)
    sorted_open_prs = sorted(all_open_prs, key=itemgetter("date"), reverse=True)
    sorted_merged_prs = sorted(all_merged_prs, key=itemgetter("date"), reverse=True)

    return sorted_commits, sorted_open_prs, sorted_merged_prs
