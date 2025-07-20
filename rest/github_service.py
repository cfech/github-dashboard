from github import Github
from operator import itemgetter

def get_all_accessible_repo_names(github_client: Github):
    """
    Gets all repo names, sorts them by the last push time (most recent first),
    and returns the sorted list of names.
    """
    print("Fetching repository list...")
    user = github_client.get_user()

    # Use a dictionary to store full repo objects and handle duplicates
    all_repos_dict = {}

    # 1. Get personally owned repos
    print("Fetching personally owned repos...")
    for repo in user.get_repos(type='owner'):
        all_repos_dict[repo.full_name] = repo

    # 2. Add repos from each organization
    try:
        orgs = user.get_orgs()
        print(f"Fetching repos from {orgs.totalCount} organizations...")
        for org in orgs:
            for repo in org.get_repos():
                # This will not add duplicates, or will overwrite, which is fine
                all_repos_dict[repo.full_name] = repo
    except Exception as e:
        print(f"Could not fetch organization repos: {e}")

    # 3. Sort the collected repositories by the 'pushed_at' attribute
    print("Sorting repositories by last update time...")
    # Get the repository objects from the dictionary
    repo_list = list(all_repos_dict.values())
    # Sort in-place, descending (most recent first)
    repo_list.sort(key=lambda r: r.pushed_at, reverse=True)

    # 4. Extract the full names from the sorted list
    sorted_repo_names = [repo.full_name for repo in repo_list]

    print(f"Returning {len(sorted_repo_names)} sorted repositories.")
    return sorted_repo_names


def get_latest_commits(github_client: Github, repo_names: list[str], limit: int = 5):
    """
    Fetches commits from a list of repos, combines them, sorts by date,
    and returns the most recent ones.
    (This function remains unchanged)
    """
    all_commits = []
    print(f"Fetching commits from {len(repo_names)} repositories...")

    for repo_name in repo_names:
        try:
            repo = github_client.get_repo(repo_name)
            print(f"  - {repo_name}")
            # Fetch a few recent commits from each repo to be efficient
            commits = repo.get_commits()
            for commit in commits[:limit*2]:
                all_commits.append({
                    "repo": repo_name,
                    "sha": commit.sha[:7],
                    "message": commit.commit.message.split('\n')[0],
                    "author": commit.commit.author.name,
                    "date": commit.commit.author.date
                })
                print("fetched commits for {}".format(repo_name), end="\r")
        except Exception as e:
            print(f"Could not access repo {repo_name}: {e}")

    # Sort all collected commits by date, descending
    sorted_commits = sorted(all_commits, key=itemgetter("date"), reverse=True)

    for commit in sorted_commits:
        commit['date'] = commit['date'].strftime("%Y-%m-%d %H:%M:%S")

    return sorted_commits[:limit]


def get_open_pull_requests(github_client: Github, repo_names: list[str]):
    """
    Fetches all open pull requests from a list of repositories.
    (This function remains unchanged)
    """
    all_prs = []
    print(f"Fetching open PRs from {len(repo_names)} repositories...")

    for repo_name in repo_names:
        try:
            repo = github_client.get_repo(repo_name)
            open_prs = repo.get_pulls(state='open')
            for pr in open_prs:
                all_prs.append({
                    "repo": repo_name,
                    "number": pr.number,
                    "title": pr.title,
                    "author": pr.user.login,
                    "url": pr.html_url
                })
            print("fetched PRs for {}".format(repo_name), end="\r")
        except Exception as e:
            print(f"Could not access repo {repo_name}: {e}")

    return all_prs