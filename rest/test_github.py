import os

from dotenv import load_dotenv
from github import Github


load_dotenv()
# Replace 'YOUR_PERSONAL_ACCESS_TOKEN' with your actual token
g = Github(os.getenv("GITHUB_TOKEN"))

# Get the authenticated user
user = g.get_user()

# Get all repositories owned by the authenticated user
repos = user.get_repos()

# Iterate and print repository names
print("Your GitHub Repositories:")
for repo in repos:
    print(repo.full_name)

# To get a specific repository by its full name (e.g., 'username/repository_name')
try:
    specific_repo = g.get_repo("PyGithub/PyGithub")
    print(f"\nInformation for specific repository '{specific_repo.full_name}':")
    print(f"  Stars: {specific_repo.stargazers_count}")
    print(f"  Description: {specific_repo.description}")
except Exception as e:
    print(f"Error fetching specific repository: {e}")