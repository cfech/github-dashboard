import streamlit as st
import pandas as pd
import os
import json
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from operator import itemgetter

from github_service_graphql import get_all_accessible_repo_names, get_bulk_data

load_dotenv()


# --- App Constants ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DEBUG_DATA_FILE = os.getcwd() + "/github_data.json"
DEBUG_MODE = False
TARGET_ORGANIZATIONS = ["mcitcentral"] # Add your organization logins here, e.g., ["my-org", "another-org"]
REPO_FETCH_LIMIT = 25 # Set to None to fetch all, or an integer to limit to the N most recently pushed repositories

def _get_github_data(token, debug_mode, debug_data_file, target_organizations, repo_fetch_limit):
    """Fetches and processes data from GitHub, with optional debug mode loading."""
    if not token:
        st.error("GITHUB_TOKEN environment variable not set.")
        return [], [], [], [], []

    if debug_mode:
        if os.path.exists(debug_data_file):
            with open(debug_data_file, 'r') as f:
                debug_data = json.load(f)
            return (debug_data.get("commits", []),
                    debug_data.get("open_prs", []),
                    debug_data.get("merged_prs", []),
                    debug_data.get("this_week_commits", []),
                    debug_data.get("this_week_prs", []))
        else:
            # If debug file not found, fetch live data and save
            pass # Fall through to live data fetching

    start_time = time.time()
    repo_names = get_all_accessible_repo_names(token, specific_org_logins=target_organizations)
    end_time = time.time()
    st.write(f"Time to fetch repo names: {end_time - start_time:.2f} seconds")

    if repo_fetch_limit is not None and len(repo_names) > repo_fetch_limit:
        repo_names_for_bulk_fetch = repo_names[:repo_fetch_limit]
    else:
        repo_names_for_bulk_fetch = repo_names

    start_time = time.time()
    commits, open_prs, merged_prs = get_bulk_data(token, repo_names_for_bulk_fetch)
    end_time = time.time()
    st.write(f"Time to fetch bulk data: {end_time - start_time:.2f} seconds")

    one_week_ago = datetime.now(timezone.utc) - timedelta(weeks=1)

    this_week_commits = [c for c in commits if datetime.fromisoformat(c['date'].replace('Z', '+00:00')) >= one_week_ago]

    this_week_open_prs = []
    for pr in open_prs:
        pr_date = datetime.fromisoformat(pr['date'].replace('Z', '+00:00'))
        if pr_date >= one_week_ago:
            pr['status'] = 'Open'
            this_week_open_prs.append(pr)

    this_week_merged_prs = []
    for pr in merged_prs:
        pr_date = datetime.fromisoformat(pr['date'].replace('Z', '+00:00'))
        if pr_date >= one_week_ago:
            pr['status'] = 'Merged'
            this_week_merged_prs.append(pr)

    this_week_prs = sorted(this_week_open_prs + this_week_merged_prs, key=itemgetter('date'), reverse=True)

    if debug_mode or not os.path.exists(debug_data_file):
        with open(debug_data_file, 'w') as f:
            json.dump({"commits": commits, "open_prs": open_prs, "merged_prs": merged_prs, "this_week_commits": this_week_commits, "this_week_prs": this_week_prs}, f, indent=4)

    return commits, open_prs, merged_prs, this_week_commits, this_week_prs

def _display_recent_commits(this_week_commits):
    st.subheader(f"Recent Commits ({len(this_week_commits)})")
    if this_week_commits:
        df_commits = pd.DataFrame(this_week_commits)
        df_commits['Repository'] = df_commits.apply(lambda row: f"<a href='{row['repo_url']}' target='_blank'>{row['repo']}</a>", axis=1)
        df_commits['Branch'] = df_commits.apply(lambda row: f"<a href='{row['branch_url']}' target='_blank'>{row['branch_name']}</a>", axis=1)
        df_commits['SHA'] = df_commits.apply(lambda row: f"<a href='{row['url']}' target='_blank'>{row['sha']}</a>", axis=1)
        df_commits.rename(columns={"message": "Message", "author": "Author", "date": "Date"}, inplace=True)
        html_commits = df_commits[['Repository', 'Branch', 'SHA', 'Message', 'Author', 'Date']].to_html(escape=False, index=False)
        st.markdown(f'<div class="table-container">{html_commits}</div>', unsafe_allow_html=True)
    else:
        st.info("No commits this week.")

def _display_recent_prs(this_week_prs):
    st.subheader(f"Recent Pull Requests ({len(this_week_prs)})")
    if this_week_prs:
        df_prs = pd.DataFrame(this_week_prs)
        df_prs['Repository'] = df_prs.apply(lambda row: f"<a href='{row['repo_url']}' target='_blank'>{row['repo']}</a>", axis=1)
        df_prs['PR Number'] = df_prs.apply(lambda row: f"<a href='{row['url']}' target='_blank'>{row['pr_number']}</a>", axis=1)
        df_prs.rename(columns={"title": "Title", "author": "Author", "date": "Date", "status": "Status"}, inplace=True)
        html_prs = df_prs[['Repository', 'PR Number', 'Title', 'Author', 'Date', 'Status']].to_html(escape=False, index=False)
        st.markdown(f'<div class="table-container">{html_prs}</div>', unsafe_allow_html=True)
    else:
        st.info("No pull requests opened or merged this week.")

def _display_pull_requests_section(open_prs_data, merged_prs_data):
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

def _display_commits_section(commits_data):
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

# --- Main App ---
def main():
    st.set_page_config(page_title="GitHub Dashboard (GraphQL)", page_icon="⚡", layout="wide")
    st.title("⚡ Personal GitHub Dashboard (GraphQL)")

    start_time = time.time()
    commits_data, open_prs_data, merged_prs_data, this_week_commits, this_week_prs = _get_github_data(
        GITHUB_TOKEN, DEBUG_MODE, DEBUG_DATA_FILE, TARGET_ORGANIZATIONS, REPO_FETCH_LIMIT
    )
    end_time = time.time()
    st.write(f"Total data fetch and processing time: {end_time - start_time:.2f} seconds")

    # --- UI Layout ---
    st.markdown("""
    <style>
        .stAppToolbar {display:none;}
    </style>
""", unsafe_allow_html=True)

    # --- This Week's Activity ---
    st.header("This Week's Activity")
    col_commits, col_prs = st.columns(2)

    with col_commits:
        _display_recent_commits(this_week_commits)

    with col_prs:
        _display_recent_prs(this_week_prs)

    st.divider()

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

    _display_pull_requests_section(open_prs_data, merged_prs_data)
    _display_commits_section(commits_data)

if __name__ == "__main__":
    main()