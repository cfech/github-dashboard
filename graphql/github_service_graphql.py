import requests
from operator import itemgetter

GRAPHQL_URL = "https://api.github.com/graphql"

def _run_graphql_query(token: str, query: str, variables: dict = None):
    """A helper function to run a GraphQL query with variables."""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    response = requests.post(GRAPHQL_URL, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()

def get_all_accessible_repo_names(token: str):
    """Gets all accessible repo names using GraphQL with pagination."""
    repo_names = []
    has_next_page = True
    end_cursor = None
    print("Fetching all accessible repository names...")

    while has_next_page:
        query = """
        query($endCursor: String) {
          viewer {
            repositories(first: 100, after: $endCursor, affiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER], orderBy: {field: PUSHED_AT, direction: DESC}) {
              nodes {
                nameWithOwner
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
        repo_names.extend([repo["nameWithOwner"] for repo in nodes])

        page_info = data.get("pageInfo", {})
        has_next_page = page_info.get("hasNextPage", False)
        end_cursor = page_info.get("endCursor")

    print(f"Fetched {len(repo_names)} total repositories.")
    return repo_names

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
                "author": pr_node.get("author", {}).get("login", "n/a"),
                "date": pr_node["createdAt"], "url": pr_node["url"]
            })

        # Parse Merged PRs
        for pr_node in repo.get("mergedPRs", {}).get("nodes", []):
            all_merged_prs.append({
                "repo": repo_name, "repo_url": repo_url,
                "pr_number": pr_node["number"], "title": pr_node["title"],
                "author": pr_node.get("author", {}).get("login", "n/a"),
                "date": pr_node["mergedAt"], "url": pr_node["url"]
            })

        # Parse commits
        history = repo.get("defaultBranchRef", {}).get("target", {}).get("history", {})
        for commit_node in history.get("nodes", []):
            all_commits.append({
                "repo": repo_name, "repo_url": repo_url,
                "branch_name": branch_name, "branch_url": branch_url,
                "sha": commit_node["oid"][:7], "message": commit_node["messageHeadline"],
                "author": commit_node.get("author", {}).get("name", "n/a"),
                "date": commit_node["committedDate"], "url": commit_node["url"]
            })

    # Sort all by date
    sorted_commits = sorted(all_commits, key=itemgetter("date"), reverse=True)
    sorted_open_prs = sorted(all_open_prs, key=itemgetter("date"), reverse=True)
    sorted_merged_prs = sorted(all_merged_prs, key=itemgetter("date"), reverse=True)

    return sorted_commits, sorted_open_prs, sorted_merged_prs
