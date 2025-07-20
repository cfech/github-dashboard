import streamlit as st
import pandas as pd
import os
import json
import time # Import the time module
from dotenv import load_dotenv
from operator import itemgetter

load_dotenv()
import github_service_graphql as github_service

# --- Page Configuration ---
st.set_page_config(page_title="GitHub Dashboard (GraphQL)", page_icon="⚡", layout="wide")

# --- App Constants ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DEBUG_DATA_FILE = "github_data.json"
DEBUG_MODE = False
TARGET_ORGANIZATIONS = ["mcitcentral"] # Add your organization logins here, e.g., ["my-org", "another-org"]
REPO_FETCH_LIMIT = 25 # Set to None to fetch all, or an integer to limit to the N most recently pushed repositories

# --- Caching & Data Loading ---
@st.cache_data(ttl=3600) # Cache for 1 hour
def load_github_data(token):
    """Fetches data from GitHub and optionally saves it for debugging."""
    if not token:
        st.error("GITHUB_TOKEN environment variable not set.")
        return None, None, None

    if DEBUG_MODE:
        print("Running in DEBUG_MODE. Data will be loaded from/saved to local file.")

    start_time = time.time()
    repo_names = github_service.get_all_accessible_repo_names(token, specific_org_logins=TARGET_ORGANIZATIONS)
    end_repo_fetch_time = time.time()
    print(f"Time to fetch all accessible repository names: {end_repo_fetch_time - start_time:.2f} seconds")

    # Apply REPO_FETCH_LIMIT if set
    if REPO_FETCH_LIMIT is not None and len(repo_names) > REPO_FETCH_LIMIT:
        st.warning(f"Limiting bulk data fetch to the first {REPO_FETCH_LIMIT} repositories (most recently pushed) out of {len(repo_names)}.")
        repo_names_for_bulk_fetch = repo_names[:REPO_FETCH_LIMIT]
    else:
        repo_names_for_bulk_fetch = repo_names

    start_bulk_fetch_time = time.time()
    commits, open_prs, merged_prs = github_service.get_bulk_data(token, repo_names_for_bulk_fetch)
    end_bulk_fetch_time = time.time()
    print(f"Time to fetch bulk data for {len(repo_names_for_bulk_fetch)} repositories: {end_bulk_fetch_time - start_bulk_fetch_time:.2f} seconds")
    print(f"Total API call time: {end_bulk_fetch_time - start_time:.2f} seconds")

    if not DEBUG_MODE:
        with open(DEBUG_DATA_FILE, 'w') as f:
            json.dump({"commits": commits, "open_prs": open_prs, "merged_prs": merged_prs}, f, indent=4)

    return commits, open_prs, merged_prs

# --- Main App ---
st.title("⚡ Personal GitHub Dashboard (GraphQL)")

# --- Custom CSS for scrollable tables ---
st.markdown("""
<style>
.table-container {
    height: 350px;
    overflow-y: auto;
}
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.title("Settings")
if DEBUG_MODE:
    st.sidebar.warning("Debug Mode is ON. Using local data.")
else:
    st.sidebar.info("Debug Mode is OFF. Fetching live data.")
    if st.sidebar.button("Refresh Live Data"):
        st.cache_data.clear()
        st.rerun()

# --- Data Loading ---
if DEBUG_MODE:
    try:
        with open(DEBUG_DATA_FILE, 'r') as f:
            data = json.load(f)
            commits_data, open_prs_data, merged_prs_data = data["commits"], data["open_prs"], data["merged_prs"]
    except FileNotFoundError:
        st.sidebar.error(f"{DEBUG_DATA_FILE} not found. Turn off Debug Mode to fetch and create it.")
        st.stop()
else:
    with st.spinner("Fetching live data from GitHub..."):
        commits_data, open_prs_data, merged_prs_data = load_github_data(GITHUB_TOKEN)

if not commits_data and not open_prs_data and not merged_prs_data:
    st.info("No data loaded. Check your token or try fetching live data.")
    st.stop()

# --- UI Layout ---

# --- Pull Request Sections ---
st.header("Pull Requests")

# Box 1: Recent Open PRs
st.subheader("Recent Open Pull Requests")
total_open_prs = len(open_prs_data)
num_open_prs = st.slider("Number to show", 1, max(2, total_open_prs), min(10, total_open_prs), key="num_open_prs")
st.write(f"Showing **{num_open_prs}** of **{total_open_prs}** open pull requests.")
if total_open_prs > 0:
    df = pd.DataFrame(open_prs_data[:num_open_prs])
    df['Repository'] = df.apply(lambda row: f"<a href='{row['repo_url']}' target='_blank'>{row['repo']}</a>", axis=1)
    df['PR Number'] = df.apply(lambda row: f"<a href='{row['url']}' target='_blank'>{row['pr_number']}</a>", axis=1)
    df.rename(columns={"title": "Title", "author": "Author", "date": "Date"}, inplace=True)
    html = df[['Repository', 'PR Number', 'Title', 'Author', 'Date']].to_html(escape=False, index=False)
    st.markdown(f'<div class="table-container">{html}</div>', unsafe_allow_html=True)

st.divider()

# Box 2: Recent Merged PRs
st.subheader("Recent Merged Pull Requests")
total_merged_prs = len(merged_prs_data)
num_merged_prs = st.slider("Number to show", 1, max(2, total_merged_prs), min(10, total_merged_prs), key="num_merged_prs")
st.write(f"Showing **{num_merged_prs}** of **{total_merged_prs}** merged pull requests.")
if total_merged_prs > 0:
    df = pd.DataFrame(merged_prs_data[:num_merged_prs])
    df['Repository'] = df.apply(lambda row: f"<a href='{row['repo_url']}' target='_blank'>{row['repo']}</a>", axis=1)
    df['PR Number'] = df.apply(lambda row: f"<a href='{row['url']}' target='_blank'>{row['pr_number']}</a>", axis=1)
    df.rename(columns={"title": "Title", "author": "Author", "date": "Date"}, inplace=True)
    html = df[['Repository', 'PR Number', 'Title', 'Author', 'Date']].to_html(escape=False, index=False)
    st.markdown(f'<div class="table-container">{html}</div>', unsafe_allow_html=True)

st.divider()

# Box 3: PRs by Repository
st.subheader("Pull Requests by Repository")
all_prs_data = sorted(open_prs_data + merged_prs_data, key=itemgetter('date'), reverse=True)
if all_prs_data:
    repo_list_prs = sorted(list(set(p['repo'] for p in all_prs_data)))
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_repo_prs = st.selectbox("Select Repository", repo_list_prs, key="prs_repo_select")

    prs_in_repo = [p for p in all_prs_data if p['repo'] == selected_repo_prs]
    total_prs_in_repo = len(prs_in_repo)

    with col2:
        num_prs_repo = st.slider("Number to show", 1, max(2, total_prs_in_repo), min(10, total_prs_in_repo), key="num_prs_repo")

    st.write(f"Showing **{num_prs_repo}** of **{total_prs_in_repo}** pull requests for **{selected_repo_prs}**.")
    if total_prs_in_repo > 0:
        df = pd.DataFrame(prs_in_repo[:num_prs_repo])
        df['Repository'] = df.apply(lambda row: f"<a href='{row['repo_url']}' target='_blank'>{row['repo']}</a>", axis=1)
        df['PR Number'] = df.apply(lambda row: f"<a href='{row['url']}' target='_blank'>{row['pr_number']}</a>", axis=1)
        df.rename(columns={"title": "Title", "author": "Author", "date": "Date"}, inplace=True)
        html = df[['Repository', 'PR Number', 'Title', 'Author', 'Date']].to_html(escape=False, index=False)
        st.markdown(f'<div class="table-container">{html}</div>', unsafe_allow_html=True)
else:
    st.info("No pull requests found.")

# --- Commit Sections ---
st.header("Commits")

# Box 4: Recent Commits
st.subheader("Recent Commits")
total_commits = len(commits_data)
num_recent_commits = st.slider("Number to show", 1, max(2, total_commits), min(10, total_commits), key="num_recent_commits")
st.write(f"Showing **{num_recent_commits}** of **{total_commits}** recent commits.")
if total_commits > 0:
    df = pd.DataFrame(commits_data[:num_recent_commits])
    df['Repository'] = df.apply(lambda row: f"<a href='{row['repo_url']}' target='_blank'>{row['repo']}</a>", axis=1)
    df['Branch'] = df.apply(lambda row: f"<a href='{row['branch_url']}' target='_blank'>{row['branch_name']}</a>", axis=1)
    df['SHA'] = df.apply(lambda row: f"<a href='{row['url']}' target='_blank'>{row['sha']}</a>", axis=1)
    df.rename(columns={"message": "Message", "author": "Author", "date": "Date"}, inplace=True)
    html = df[['Repository', 'Branch', 'SHA', 'Message', 'Author', 'Date']].to_html(escape=False, index=False)
    st.markdown(f'<div class="table-container">{html}</div>', unsafe_allow_html=True)

st.divider()

# Box 5: Commits by Repository
st.subheader("Commits by Repository")
if commits_data:
    repo_list_commits = sorted(list(set(c['repo'] for c in commits_data)))
    col3, col4 = st.columns([3, 1])
    with col3:
        selected_repo_commits = st.selectbox("Select Repository", repo_list_commits, key="commits_repo_select")

    commits_in_repo = [c for c in commits_data if c['repo'] == selected_repo_commits]
    total_commits_in_repo = len(commits_in_repo)

    with col4:
        num_commits_repo = st.slider("Number to show", 1, max(2, total_commits_in_repo), min(10, total_commits_in_repo), key="num_commits_repo")

    st.write(f"Showing **{num_commits_repo}** of **{total_commits_in_repo}** commits for **{selected_repo_commits}**.")
    if total_commits_in_repo > 0:
        df = pd.DataFrame(commits_in_repo[:num_commits_repo])
        df['Repository'] = df.apply(lambda row: f"<a href='{row['repo_url']}' target='_blank'>{row['repo']}</a>", axis=1)
        df['Branch'] = df.apply(lambda row: f"<a href='{row['branch_url']}' target='_blank'>{row['branch_name']}</a>", axis=1)
        df['SHA'] = df.apply(lambda row: f"<a href='{row['url']}' target='_blank'>{row['sha']}</a>", axis=1)
        df.rename(columns={"message": "Message", "author": "Author", "date": "Date"}, inplace=True)
        html = df[['Repository', 'Branch', 'SHA', 'Message', 'Author', 'Date']].to_html(escape=False, index=False)
        st.markdown(f'<div class="table-container">{html}</div>', unsafe_allow_html=True)
else:
    st.info("No commits found.")