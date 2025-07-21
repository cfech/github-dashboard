import streamlit as st
import pandas as pd
import os
import json
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from operator import itemgetter

from github_service_graphql import get_bulk_data, get_all_accessible_repo_data
from commit_stream import display_commit_stream

load_dotenv()
# --- App Constants ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
DEBUG_DATA_FILE = os.getcwd() + "/github_data.json"
DEBUG_MODE = False
TARGET_ORGANIZATIONS = ["mcitcentral"] # Add your organization logins here, e.g., ["my-org", "another-org"]
REPO_FETCH_LIMIT = int(os.getenv("REPO_FETCH_LIMIT", 25)) # Set to None to fetch all, or an integer to limit to the N most recently pushed repositories


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

def _get_date_color_and_badge(utc_timestamp):
    """Get color coding and badge for dates based on recency"""
    utc_dt = datetime.fromisoformat(utc_timestamp.replace('Z', '+00:00'))
    local_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone()
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    
    item_date = local_dt.date()
    
    if item_date == today:
        return "#9C27B0", "🌟"  # Nice purple for today - shining star
    elif item_date == yesterday:
        return "#43A047", "🌙"  # Green for yesterday - recent moon
    elif item_date >= week_ago:
        return "#FB8C00", "☄️"   # Orange for this week - comet streak
    else:
        return "#FFFFFF", "⭐"   # White for older - distant star

def format_pr_for_stream(pr: dict) -> str:
    """Format a single PR for the stream display with color coding."""
    formatted_date = _format_timestamp_to_local(pr["date"])
    date_part = formatted_date.split()[0]  # Just the date part (YYYY-MM-DD)
    time_part = " ".join(formatted_date.split()[1:3])  # Time and AM/PM
    
    # Get color and badge based on date
    date_color, badge = _get_date_color_and_badge(pr["date"])
    
    # Check if this PR is from today for the TODAY badge
    pr_utc = datetime.fromisoformat(pr["date"].replace('Z', '+00:00'))
    pr_local = pr_utc.replace(tzinfo=timezone.utc).astimezone()
    is_today = pr_local.date() == datetime.now().date()
    
    # Don't truncate PR titles - allow them to wrap
    title = pr["title"]
    
    # Simplified display for stream
    repo_name = pr["repo"].split("/")[-1]
    author = pr["author"]
    pr_number = pr["pr_number"]
    status = pr.get("status", "Open")
    
    # Status emoji and color
    status_emoji = "✅" if status == "Merged" else "🔄"
    
    # Add TODAY badge if it's from today
    repo_display = f"**[{repo_name}]({pr['repo_url']})**"
    if is_today:
        repo_display = f'<span class="today-badge">TODAY</span> {repo_display}'
    
    return f"""{badge} {repo_display} **[#{pr_number}]({pr["url"]})**  
*{title}*  
{status_emoji} {status} • {author}  
📅 <span style="color: {date_color};">{date_part} {time_part}</span>"""

def display_pr_stream(all_prs_data: list, debug_mode: bool = False):
    """Display the PR stream similar to commit stream."""
    st.subheader("🔀 Live PR Stream")
    if debug_mode:
        st.markdown("*Recent pull requests* **[DEBUG MODE]**")
    else:
        st.markdown("*Recent pull requests*")
    
    if not all_prs_data:
        st.info("No recent pull requests found")
        return
    
    # Sort PRs by date to ensure newest first
    prs_sorted = sorted(all_prs_data, key=lambda x: x["date"], reverse=True)
    today = datetime.now().date()
    
    # Display stats
    st.markdown(f"**{len(prs_sorted)} pull requests** • Recent activity")
    
    # Add refresh button
    if st.button("🔄 Refresh PRs", key="refresh_prs"):
        st.cache_data.clear()
        st.rerun()
    
    # Create a scrollable container with same height as commit stream
    container = st.container(height=800)
    
    with container:
        # Display ALL PRs using Streamlit's native markdown
        for i, pr in enumerate(prs_sorted):
            # Format the PR using the formatting function
            pr_markdown = format_pr_for_stream(pr)
            st.markdown(pr_markdown, unsafe_allow_html=True)
            
            # Add separator except for last item
            if i < len(prs_sorted) - 1:
                st.markdown("---")


def _get_github_data(token, debug_mode, debug_data_file, target_organizations, repo_fetch_limit):
    """Fetches and processes data from GitHub, with optional debug mode loading."""
    if not token:
        st.error("GITHUB_TOKEN environment variable not set.")
        return [], [], [], [], [], []

    if debug_mode:
        if os.path.exists(debug_data_file):
            with open(debug_data_file, 'r') as f:
                debug_data = json.load(f)
            return (debug_data.get("commits", []),
                    debug_data.get("open_prs", []),
                    debug_data.get("merged_prs", []),
                    debug_data.get("this_week_commits", []),
                    debug_data.get("this_week_prs", []),
                    [])  # Empty repo_data_with_dates in debug mode
        else:
            # If debug file not found, fetch live data and save
            pass # Fall through to live data fetching

    start_time = time.time()
    repo_data_with_dates = get_all_accessible_repo_data(token, specific_org_logins=target_organizations)
    repo_names = [repo_name for repo_name, _ in repo_data_with_dates]
    end_time = time.time()
    st.write(f"Time to fetch repo data: {end_time - start_time:.2f} seconds")

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

    # Always save debug file when debug mode is OFF to override cached data
    # Only save when debug mode is ON if file doesn't exist
    if not debug_mode or not os.path.exists(debug_data_file):
        with open(debug_data_file, 'w') as f:
            json.dump({"commits": commits, "open_prs": open_prs, "merged_prs": merged_prs, "this_week_commits": this_week_commits, "this_week_prs": this_week_prs}, f, indent=4)

    return commits, open_prs, merged_prs, this_week_commits, this_week_prs, repo_data_with_dates


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
    commits_data, open_prs_data, merged_prs_data, this_week_commits, this_week_prs, repo_data_with_dates_from_fetch = _get_github_data(
        GITHUB_TOKEN, DEBUG_MODE, DEBUG_DATA_FILE, TARGET_ORGANIZATIONS, REPO_FETCH_LIMIT
    )
    end_time = time.time()
    
    # Use repo data with push dates from the single fetch for commit stream
    if not DEBUG_MODE and GITHUB_TOKEN:
        repo_data_with_dates = repo_data_with_dates_from_fetch
        print(f"📋 [MAIN DASHBOARD] Got {len(repo_data_with_dates)} repos with push dates for commit stream")
    else:
        # In debug mode, create mock repo data from existing repos
        existing_repo_names = []
        if commits_data:
            existing_repo_names = list(set(c['repo'] for c in commits_data))
        elif open_prs_data:
            existing_repo_names = list(set(pr['repo'] for pr in open_prs_data))
        elif merged_prs_data:
            existing_repo_names = list(set(pr['repo'] for pr in merged_prs_data))
        
        # Create mock repo data for debug mode
        from datetime import datetime, timezone
        mock_date = datetime.now(timezone.utc).isoformat()
        repo_data_with_dates = [(name, mock_date) for name in existing_repo_names]
        print(f"📋 [MAIN DASHBOARD] DEBUG MODE: Created mock repo data for {len(existing_repo_names)} repos")

    # --- UI Layout ---
    st.markdown("""
    <style>
        .stAppToolbar {display:none;}
    </style>
""", unsafe_allow_html=True)

    # --- New Layout: Streams on top, detailed sections below ---
    # Top section: Two streams side by side
    st.header("🔄 Live Activity Streams")
    stream_col1, stream_col2 = st.columns(2)
    
    with stream_col1:
        # Display commit stream
        display_commit_stream(GITHUB_TOKEN, repo_data_with_dates, DEBUG_MODE)
    
    with stream_col2:
        # Display PR stream using combined PR data
        all_prs_data = sorted(open_prs_data + merged_prs_data, key=itemgetter('date'), reverse=True)
        display_pr_stream(all_prs_data, DEBUG_MODE)
    
    st.divider()
    
    # Bottom section: Detailed tables in full width
    _display_pull_requests_section(open_prs_data, merged_prs_data)
    _display_commits_section(commits_data)

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
    
    /* Stream container styling */
    .stColumns > div:first-child,
    .stColumns > div:last-child {
        padding: 0 20px !important;
    }
    
    /* Stream content borders and styling */
    div[data-testid="stContainer"] {
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        background: linear-gradient(145deg, rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0.01));
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        margin: 10px auto;
        max-width: 95%;
    }
    
    /* Center the stream columns */
    .stColumns {
        gap: 2rem !important;
        justify-content: center !important;
        max-width: 1200px;
        margin: 0 auto;
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
    
    # Check commit stream debug file status
    import os
    cs_debug_file = os.getcwd() + "/cs_debug.json"
    if os.path.exists(cs_debug_file):
        st.sidebar.text("Using cached data from cs_debug.json")
    

if __name__ == "__main__":
    main()