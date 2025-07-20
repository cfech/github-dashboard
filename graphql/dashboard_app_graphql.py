import streamlit as st
import pandas as pd
import os
import json
from dotenv import load_dotenv

load_dotenv()
import github_service_graphql as github_service

# --- Page Configuration ---
st.set_page_config(page_title="GitHub Dashboard (GraphQL)", page_icon="⚡", layout="wide")

# --- App Constants ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DEBUG_DATA_FILE = "github_data.json"
DEBUG_MODE = False

# --- UI Sidebar ---
st.sidebar.title("Settings")
repo_limit = st.sidebar.number_input(
    label="Number of Repos to Display", min_value=5, max_value=100, value=20, step=5,
    help="The number of most recently updated repositories to fetch data for."
)

# --- Caching & Data Loading ---
@st.cache_data(ttl=600)
def load_github_data(token, limit, is_debug):
    if is_debug:
        st.sidebar.warning("Debug Mode is ON. Reading from local file.")
        try:
            with open(DEBUG_DATA_FILE, 'r') as f:
                data = json.load(f)
                return data['commits'], data['prs'], data['total_repo_count']
        except FileNotFoundError:
            st.sidebar.error(f"{DEBUG_DATA_FILE} not found. Set DEBUG_MODE to False to create it.")
            return None, None, 0

    if not token:
        st.error("GITHUB_TOKEN environment variable not set.")
        return None, None, 0

    all_repo_names = github_service.get_all_accessible_repo_names(token)
    repo_names_to_fetch = all_repo_names[:limit]

    # This single function now gets both commits and PRs
    commits, prs = github_service.get_latest_commits_and_prs_bulk(token, repo_names_to_fetch, limit=5)
    total_repo_count = len(all_repo_names)

    print("LIVE: Saving data to local file for future debugging.")
    data_to_save = {"commits": commits, "prs": prs, "total_repo_count": total_repo_count}
    with open(DEBUG_DATA_FILE, 'w') as f:
        json.dump(data_to_save, f, indent=2)

    return commits, prs, total_repo_count

# --- Main App ---
st.title("⚡ Personal GitHub Dashboard (GraphQL)")
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
            column_config={"url": st.column_config.LinkColumn("Link", display_text="Open on GitHub →")},
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