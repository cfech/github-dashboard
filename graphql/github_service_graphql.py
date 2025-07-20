import requests
from operator import itemgetter

GRAPHQL_URL = "https://api.github.com/graphql"

def _run_graphql_query(token: str, query: str):
    """A simple helper function to run a GraphQL query."""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(GRAPHQL_URL, json={"query": query}, headers=headers)
    response.raise_for_status()
    return response.json()

def get_all_accessible_repo_names(token: str):
    """Gets all repo names using GraphQL and sorts them by last push time."""
    query = """
    query {
      viewer {
        repositories(first: 100, affiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER], orderBy: {field: PUSHED_AT, direction: DESC}) {
          nodes {
            nameWithOwner
          }
        }
      }
    }
    """
    print("Fetching repository list via GraphQL...")
    result = _run_graphql_query(token, query)
    nodes = result.get("data", {}).get("viewer", {}).get("repositories", {}).get("nodes", [])
    repo_names = [repo["nameWithOwner"] for repo in nodes]
    print(f"Returning {len(repo_names)} sorted repositories.")
    return repo_names

def _build_bulk_query(repo_names: list[str], limit: int):
    """Dynamically builds the bulk query string for commits and PRs."""
    query_parts = []
    for i, name in enumerate(repo_names):
        owner, repo_name = name.split("/")
        # Create a valid GraphQL alias (no dashes or dots)
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
            pullRequests(states: [OPEN], first: 20, orderBy: {{field: CREATED_AT, direction: DESC}}) {{
                nodes {{
                    number
                    title
                    author {{ login }}
                    url
                }}
            }}
            defaultBranchRef {{
                target {{
                    ... on Commit {{
                        history(first: {limit}) {{
                            nodes {{
                                oid
                                messageHeadline
                                committedDate
                                author {{ name }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
    """

def get_latest_commits_and_prs_bulk(token: str, repo_names: list[str], limit: int = 5):
    """Fetches commits and PRs for a list of repos in a single GraphQL call."""
    if not repo_names:
        return [], []

    bulk_query = _build_bulk_query(repo_names, limit)
    print(f"Fetching bulk data for {len(repo_names)} repositories via GraphQL...")
    result = _run_graphql_query(token, bulk_query)

    all_commits = []
    all_prs = []

    repo_data = result.get("data", {})
    for repo_alias in repo_data:
        repo = repo_data[repo_alias]
        if not repo:
            continue

        repo_name = repo["nameWithOwner"]

        # Parse PRs
        for pr_node in repo.get("pullRequests", {}).get("nodes", []):
            all_prs.append({
                "repo": repo_name,
                "number": pr_node["number"],
                "title": pr_node["title"],
                "author": pr_node.get("author", {}).get("login", "n/a"),
                "url": pr_node["url"]
            })

        # Parse commits
        history = repo.get("defaultBranchRef", {}).get("target", {}).get("history", {})
        for commit_node in history.get("nodes", []):
            all_commits.append({
                "repo": repo_name,
                "sha": commit_node["oid"][:7],
                "message": commit_node["messageHeadline"],
                "author": commit_node.get("author", {}).get("name", "n/a"),
                "date": commit_node["committedDate"]
            })

    # Sort all collected commits by date, descending
    sorted_commits = sorted(all_commits, key=itemgetter("date"), reverse=True)

    return sorted_commits[:limit], all_prs