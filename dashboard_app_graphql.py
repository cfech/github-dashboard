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


# --- Helper Functions ---
def _format_timestamp_to_local(utc_timestamp):
    """Convert UTC timestamp to local timezone formatted string"""
    utc_dt = datetime.fromisoformat(utc_timestamp.replace('Z', '+00:00'))
    local_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone()
    return local_dt.strftime('%Y-%m-%d %I:%M %p EST')

def _is_today_local(utc_timestamp):
    """Check if UTC timestamp is today in local timezone"""
    utc_dt = datetime.fromisoformat(utc_timestamp.replace('Z', '+00:00'))
    local_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone()
    return local_dt.date() == datetime.now().date()

# --- App Constants ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DEBUG_DATA_FILE = os.getcwd() + "/github_data.json"
DEBUG_MODE = True
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
        
        # Add highlighting for today's commits (using local timezone)
        today = datetime.now().date()
        
        def format_row_with_highlighting(row):
            # Check if today and format date
            is_today = _is_today_local(row['date'])
            formatted_date = _format_timestamp_to_local(row['date'])
            
            # Base row content
            repo_link = f"<a href='{row['repo_url']}' target='_blank'>{row['repo']}</a>"
            branch_link = f"<a href='{row['branch_url']}' target='_blank'>{row['branch_name']}</a>"
            sha_link = f"<a href='{row['url']}' target='_blank'>{row['sha']}</a>"
            
            # Add TODAY badge and highlight date text
            date_text = formatted_date
            if is_today:
                repo_link = f'<span class="today-badge">TODAY</span> {repo_link}'
                date_text = f'<span class="today-date">{formatted_date}</span>'
            
            return {
                'Repository': repo_link,
                'Branch': branch_link, 
                'SHA': sha_link,
                'Message': row['message'],
                'Author': row['author'],
                'Date': date_text,
                'is_today': False  # No longer need row highlighting
            }
        
        enhanced_commits = [format_row_with_highlighting(row) for _, row in df_commits.iterrows()]
        df_enhanced = pd.DataFrame(enhanced_commits)
        
        # Generate HTML without row highlighting
        html_rows = []
        for _, row in df_enhanced.iterrows():
            cells = []
            for col in ['Repository', 'Branch', 'SHA', 'Message', 'Author', 'Date']:
                cells.append(f'<td>{row[col]}</td>')
            html_rows.append(f'<tr>{"".join(cells)}</tr>')
        
        header_html = '<tr><th>Repository</th><th>Branch</th><th>SHA</th><th>Message</th><th>Author</th><th>Date</th></tr>'
        table_html = f'<table class="dataframe"><thead>{header_html}</thead><tbody>{"".join(html_rows)}</tbody></table>'
        
        st.markdown(f'<div class="table-container">{table_html}</div>', unsafe_allow_html=True)
    else:
        st.info("No commits this week.")

def _display_recent_prs(this_week_prs):
    st.subheader(f"Recent Pull Requests ({len(this_week_prs)})")
    if this_week_prs:
        df_prs = pd.DataFrame(this_week_prs)
        
        # Add highlighting for today's PRs (using local timezone)
        today = datetime.now().date()
        
        def format_pr_row_with_highlighting(row):
            # Check if today and format date
            is_today = _is_today_local(row['date'])
            formatted_date = _format_timestamp_to_local(row['date'])
            
            # Base row content
            repo_link = f"<a href='{row['repo_url']}' target='_blank'>{row['repo']}</a>"
            pr_link = f"<a href='{row['url']}' target='_blank'>{row['pr_number']}</a>"
            
            # Add TODAY badge and highlight date text
            date_text = formatted_date
            if is_today:
                repo_link = f'<span class="today-badge">TODAY</span> {repo_link}'
                date_text = f'<span class="today-date">{formatted_date}</span>'
            
            # Status with color coding
            status_class = 'status-open' if row['status'] == 'Open' else 'status-merged'
            status_html = f'<span class="{status_class}">{row["status"]}</span>'
            
            return {
                'Repository': repo_link,
                'PR Number': pr_link,
                'Title': row['title'],
                'Author': row['author'],
                'Date': date_text,
                'Status': status_html,
                'is_today': False  # No longer need row highlighting
            }
        
        enhanced_prs = [format_pr_row_with_highlighting(row) for _, row in df_prs.iterrows()]
        df_enhanced = pd.DataFrame(enhanced_prs)
        
        # Generate HTML without row highlighting
        html_rows = []
        for _, row in df_enhanced.iterrows():
            cells = []
            for col in ['Repository', 'PR Number', 'Title', 'Author', 'Date', 'Status']:
                cells.append(f'<td>{row[col]}</td>')
            html_rows.append(f'<tr>{"".join(cells)}</tr>')
        
        header_html = '<tr><th>Repository</th><th>PR Number</th><th>Title</th><th>Author</th><th>Date</th><th>Status</th></tr>'
        table_html = f'<table class="dataframe"><thead>{header_html}</thead><tbody>{"".join(html_rows)}</tbody></table>'
        
        st.markdown(f'<div class="table-container">{table_html}</div>', unsafe_allow_html=True)
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
        
        def format_open_pr_with_highlighting(row):
            is_today = _is_today_local(row['date'])
            formatted_date = _format_timestamp_to_local(row['date'])
            
            repo_link = f"<a href='{row['repo_url']}' target='_blank'>{row['repo']}</a>"
            pr_link = f"<a href='{row['url']}' target='_blank'>{row['pr_number']}</a>"
            
            date_text = formatted_date
            if is_today:
                repo_link = f'<span class="today-badge">TODAY</span> {repo_link}'
                date_text = f'<span class="today-date">{formatted_date}</span>'
            
            return {
                'Repository': repo_link,
                'PR Number': pr_link,
                'Title': row['title'],
                'Author': row['author'],
                'Date': date_text
            }
        
        enhanced_prs = [format_open_pr_with_highlighting(row) for _, row in df.iterrows()]
        df_enhanced = pd.DataFrame(enhanced_prs)
        
        html_rows = []
        for _, row in df_enhanced.iterrows():
            cells = []
            for col in ['Repository', 'PR Number', 'Title', 'Author', 'Date']:
                cells.append(f'<td>{row[col]}</td>')
            html_rows.append(f'<tr>{"".join(cells)}</tr>')
        
        header_html = '<tr><th>Repository</th><th>PR Number</th><th>Title</th><th>Author</th><th>Date</th></tr>'
        table_html = f'<table class="dataframe"><thead>{header_html}</thead><tbody>{"".join(html_rows)}</tbody></table>'
        st.markdown(f'<div class="table-container">{table_html}</div>', unsafe_allow_html=True)

    st.divider()

    # Box 2: Recent Merged PRs
    st.subheader("Recent Merged Pull Requests")
    total_merged_prs = len(merged_prs_data)
    num_merged_prs = st.slider("Number to show", 1, max(2, total_merged_prs), min(10, total_merged_prs), key="num_merged_prs")
    st.write(f"Showing **{num_merged_prs}** of **{total_merged_prs}** merged pull requests.")
    if total_merged_prs > 0:
        df = pd.DataFrame(merged_prs_data[:num_merged_prs])
        
        def format_merged_pr_with_highlighting(row):
            is_today = _is_today_local(row['date'])
            formatted_date = _format_timestamp_to_local(row['date'])
            
            repo_link = f"<a href='{row['repo_url']}' target='_blank'>{row['repo']}</a>"
            pr_link = f"<a href='{row['url']}' target='_blank'>{row['pr_number']}</a>"
            
            date_text = formatted_date
            if is_today:
                repo_link = f'<span class="today-badge">TODAY</span> {repo_link}'
                date_text = f'<span class="today-date">{formatted_date}</span>'
            
            return {
                'Repository': repo_link,
                'PR Number': pr_link,
                'Title': row['title'],
                'Author': row['author'],
                'Date': date_text
            }
        
        enhanced_prs = [format_merged_pr_with_highlighting(row) for _, row in df.iterrows()]
        df_enhanced = pd.DataFrame(enhanced_prs)
        
        html_rows = []
        for _, row in df_enhanced.iterrows():
            cells = []
            for col in ['Repository', 'PR Number', 'Title', 'Author', 'Date']:
                cells.append(f'<td>{row[col]}</td>')
            html_rows.append(f'<tr>{"".join(cells)}</tr>')
        
        header_html = '<tr><th>Repository</th><th>PR Number</th><th>Title</th><th>Author</th><th>Date</th></tr>'
        table_html = f'<table class="dataframe"><thead>{header_html}</thead><tbody>{"".join(html_rows)}</tbody></table>'
        st.markdown(f'<div class="table-container">{table_html}</div>', unsafe_allow_html=True)

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
            
            def format_repo_pr_with_highlighting(row):
                is_today = _is_today_local(row['date'])
                formatted_date = _format_timestamp_to_local(row['date'])
                
                repo_link = f"<a href='{row['repo_url']}' target='_blank'>{row['repo']}</a>"
                pr_link = f"<a href='{row['url']}' target='_blank'>{row['pr_number']}</a>"
                
                date_text = formatted_date
                if is_today:
                    repo_link = f'<span class="today-badge">TODAY</span> {repo_link}'
                    date_text = f'<span class="today-date">{formatted_date}</span>'
                
                return {
                    'Repository': repo_link,
                    'PR Number': pr_link,
                    'Title': row['title'],
                    'Author': row['author'],
                    'Date': date_text
                }
            
            enhanced_prs = [format_repo_pr_with_highlighting(row) for _, row in df.iterrows()]
            df_enhanced = pd.DataFrame(enhanced_prs)
            
            html_rows = []
            for _, row in df_enhanced.iterrows():
                cells = []
                for col in ['Repository', 'PR Number', 'Title', 'Author', 'Date']:
                    cells.append(f'<td>{row[col]}</td>')
                html_rows.append(f'<tr>{"".join(cells)}</tr>')
            
            header_html = '<tr><th>Repository</th><th>PR Number</th><th>Title</th><th>Author</th><th>Date</th></tr>'
            table_html = f'<table class="dataframe"><thead>{header_html}</thead><tbody>{"".join(html_rows)}</tbody></table>'
            st.markdown(f'<div class="table-container">{table_html}</div>', unsafe_allow_html=True)
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
        
        def format_recent_commit_with_highlighting(row):
            is_today = _is_today_local(row['date'])
            formatted_date = _format_timestamp_to_local(row['date'])
            
            repo_link = f"<a href='{row['repo_url']}' target='_blank'>{row['repo']}</a>"
            branch_link = f"<a href='{row['branch_url']}' target='_blank'>{row['branch_name']}</a>"
            sha_link = f"<a href='{row['url']}' target='_blank'>{row['sha']}</a>"
            
            date_text = formatted_date
            if is_today:
                repo_link = f'<span class="today-badge">TODAY</span> {repo_link}'
                date_text = f'<span class="today-date">{formatted_date}</span>'
            
            return {
                'Repository': repo_link,
                'Branch': branch_link,
                'SHA': sha_link,
                'Message': row['message'],
                'Author': row['author'],
                'Date': date_text
            }
        
        enhanced_commits = [format_recent_commit_with_highlighting(row) for _, row in df.iterrows()]
        df_enhanced = pd.DataFrame(enhanced_commits)
        
        html_rows = []
        for _, row in df_enhanced.iterrows():
            cells = []
            for col in ['Repository', 'Branch', 'SHA', 'Message', 'Author', 'Date']:
                cells.append(f'<td>{row[col]}</td>')
            html_rows.append(f'<tr>{"".join(cells)}</tr>')
        
        header_html = '<tr><th>Repository</th><th>Branch</th><th>SHA</th><th>Message</th><th>Author</th><th>Date</th></tr>'
        table_html = f'<table class="dataframe"><thead>{header_html}</thead><tbody>{"".join(html_rows)}</tbody></table>'
        st.markdown(f'<div class="table-container">{table_html}</div>', unsafe_allow_html=True)

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
            
            def format_repo_commit_with_highlighting(row):
                is_today = _is_today_local(row['date'])
                formatted_date = _format_timestamp_to_local(row['date'])
                
                repo_link = f"<a href='{row['repo_url']}' target='_blank'>{row['repo']}</a>"
                branch_link = f"<a href='{row['branch_url']}' target='_blank'>{row['branch_name']}</a>"
                sha_link = f"<a href='{row['url']}' target='_blank'>{row['sha']}</a>"
                
                date_text = formatted_date
                if is_today:
                    repo_link = f'<span class="today-badge">TODAY</span> {repo_link}'
                    date_text = f'<span class="today-date">{formatted_date}</span>'
                
                return {
                    'Repository': repo_link,
                    'Branch': branch_link,
                    'SHA': sha_link,
                    'Message': row['message'],
                    'Author': row['author'],
                    'Date': date_text
                }
            
            enhanced_commits = [format_repo_commit_with_highlighting(row) for _, row in df.iterrows()]
            df_enhanced = pd.DataFrame(enhanced_commits)
            
            html_rows = []
            for _, row in df_enhanced.iterrows():
                cells = []
                for col in ['Repository', 'Branch', 'SHA', 'Message', 'Author', 'Date']:
                    cells.append(f'<td>{row[col]}</td>')
                html_rows.append(f'<tr>{"".join(cells)}</tr>')
            
            header_html = '<tr><th>Repository</th><th>Branch</th><th>SHA</th><th>Message</th><th>Author</th><th>Date</th></tr>'
            table_html = f'<table class="dataframe"><thead>{header_html}</thead><tbody>{"".join(html_rows)}</tbody></table>'
            st.markdown(f'<div class="table-container">{table_html}</div>', unsafe_allow_html=True)
    else:
        st.info("No commits found.")

# --- Main App ---
def main():
    st.set_page_config(page_title="GitHub Dashboard (GraphQL)", page_icon="⚡", layout="wide")
    st.title("⚡ Personal GitHub Dashboard (GraphQL)")
    
    # Timezone disclaimer
    st.markdown("<p style='color: #666; font-size: 0.9em; margin-bottom: 1rem;'>⏰ All times are displayed in your local timezone (EST)</p>", unsafe_allow_html=True)

    start_time = time.time()
    commits_data, open_prs_data, merged_prs_data, this_week_commits, this_week_prs = _get_github_data(
        GITHUB_TOKEN, DEBUG_MODE, DEBUG_DATA_FILE, TARGET_ORGANIZATIONS, REPO_FETCH_LIMIT
    )
    end_time = time.time()

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

    # --- Custom CSS for scrollable tables and highlighting ---
    st.markdown("""
    <style>
    .table-container {
        height: 350px;
        overflow-y: auto;
    }
    
    /* Today highlighting styles - only for date text */
    .today-date {
        color: #ff6f00 !important;
        font-weight: 600 !important;
    }
    
    .today-badge {
        background: linear-gradient(135deg, #ff8f00, #f57c00);
        color: white;
        padding: 2px 6px;
        border-radius: 10px;
        font-size: 9px;
        font-weight: 600;
        margin-right: 6px;
        text-shadow: 0 1px 1px rgba(0,0,0,0.2);
        display: inline-block;
    }
    
    /* Status styling */
    .status-open {
        background-color: #e3f2fd;
        color: #1565c0;
        padding: 2px 6px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 500;
    }
    
    .status-merged {
        background-color: #e8f5e8;
        color: #2e7d32;
        padding: 2px 6px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 500;
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
    
    # Data fetching status in sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Data Status:**")
    st.sidebar.text(f"Fetch time: {end_time - start_time:.2f}s")

    _display_pull_requests_section(open_prs_data, merged_prs_data)
    _display_commits_section(commits_data)

if __name__ == "__main__":
    main()