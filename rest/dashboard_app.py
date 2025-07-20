import streamlit as st
import pandas as pd
import os
import json
from github import Github
from dotenv import load_dotenv

# Always load environment variables from a .env file if it exists
load_dotenv()

# Import our updated service module
import github_service

# --- Page Configuration ---
st.set_page_config(
    page_title="GitHub Dashboard",
    page_icon="🐙",
    layout="wide"
)

# --- App Constants ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DEBUG_DATA_FILE = "github_data.json"
# 1. Set the debug mode with this constant
DEBUG_MODE = False

# --- UI Sidebar ---
st.sidebar.title("Settings")
repo_limit = st.sidebar.number_input(
    label="Number of Repos to Display",
    min_value=5,
    max_value=100,
    value=20, # Default value
    step=5,
    help="The number of most recently updated repositories to fetch data for."
)

# --- Caching & Data Loading ---
@st.cache_data(ttl=600)
def load_github_data(token, limit, is_debug):
    if is_debug:
        st.sidebar.warning("Debug Mode is ON. Reading from local file.")
        try:
            with open(DEBUG_DATA_FILE, 'r') as f:
                print("DEBUG: Reading data from local file.")
                data = json.load(f)
                return data['commits'], data['prs'], data['total_repo_count']
        except FileNotFoundError:
            st.sidebar.error(f"{DEBUG_DATA_FILE} not found. Set DEBUG_MODE to False to create it.")
            return None, None, 0

    # --- Live API Call Logic ---
    if not token:
        st.error("GITHUB_TOKEN environment variable not set.")
        return None, None, 0


        # --- THIS IS THE CHANGE ---
    # Define the base URL for your private server
    # Best practice: Load this from an environment variable as well
    base_url = os.getenv("GITHUB_BASE_URL", "https://api.github.com/api/v3")

    # Pass the base_url to the Github constructor
    client = Github(base_url=base_url, login_or_token=token)
    # --- END OF CHANGE ---
    all_repo_names = github_service.get_all_accessible_repo_names(client)

    if not all_repo_names:
        st.warning("No repositories found for this account.")
        return None, None, 0

    repo_names_to_fetch = all_repo_names[:limit]
    commits = github_service.get_latest_commits(client, repo_names_to_fetch, limit=5)
    prs = github_service.get_open_pull_requests(client, repo_names_to_fetch)
    total_repo_count = len(all_repo_names)

    print("LIVE: Saving data to local file for future debugging.")
    data_to_save = {
        "commits": commits,
        "prs": prs,
        "total_repo_count": total_repo_count
    }
    with open(DEBUG_DATA_FILE, 'w') as f:
        json.dump(data_to_save, f, indent=2)

    return commits, prs, total_repo_count

# --- Main App ---
st.title("🐙 Personal GitHub Dashboard")

# 2. Pass the DEBUG_MODE constant to the data loading function
commits_data, prs_data, total_repo_count = load_github_data(GITHUB_TOKEN, repo_limit, DEBUG_MODE)

if total_repo_count > 0 and not DEBUG_MODE:
    st.info(f"Displaying data for the **{repo_limit}** most recently updated repositories out of **{total_repo_count}** total.")

if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# (The rest of the app display code is unchanged)
if prs_data is not None:
    st.subheader(f"Open Pull Requests ({len(prs_data)})")
    if not prs_data:
        st.info("No open pull requests found. Great job! ✨")
    else:
        pr_df = pd.DataFrame(prs_data)
        st.dataframe(
            pr_df,
            column_config={
                "url": st.column_config.LinkColumn("Link", display_text="Open on GitHub →")
            },
            use_container_width=True
        )

st.divider()

if commits_data is not None:
    st.subheader("Recent Commits")
    if not commits_data:
        st.info("No recent commits found.")
    else:
        commit_df = pd.DataFrame(commits_data)
        st.dataframe(commit_df, use_container_width=True)