"""
GitHub Dashboard Main Application

This module provides a Streamlit-based dashboard for viewing GitHub repository data,
including commits, pull requests, and activity streams.
"""

import streamlit as st
import pandas as pd
import os
import json
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from operator import itemgetter
from typing import List, Dict, Tuple, Any
import plotly.express as px
import plotly.graph_objects as go

# Import shared modules and services
from constants import (
    DEBUG_MODE, DEBUG_DATA_FILE, DEFAULT_TARGET_ORGANIZATIONS,
    DEFAULT_REPO_FETCH_LIMIT, STREAM_CONTAINER_HEIGHT, TABLE_CONTAINER_HEIGHT,
    ERROR_MESSAGES, INFO_MESSAGES, ENV_VARS, DATE_COLORS, TIMELINE_EMOJIS,
    PR_STATUS_EMOJIS, CSS_CLASSES, BADGE_COLORS, DEFAULT_DISPLAY_COUNT, LOOK_BACK_DAYS
)
from utils import (
    format_timestamp_to_local, is_timestamp_today_local, get_date_color_and_emoji,
    get_repository_display_name, safe_get_commit_field
)
from github_service_graphql import get_bulk_data, get_all_accessible_repo_data, fetch_user_info
from commit_stream import display_commit_stream

load_dotenv()


# =============================================================================
# Configuration and Setup
# =============================================================================

def get_application_config() -> Dict[str, Any]:
    """Get application configuration from environment variables and constants."""
    return {
        'github_token': os.getenv(ENV_VARS['github_token']),
        'debug_mode': DEBUG_MODE,
        'debug_data_file': DEBUG_DATA_FILE,
        'target_organizations': DEFAULT_TARGET_ORGANIZATIONS,
        'repo_fetch_limit': int(os.getenv(ENV_VARS['repo_fetch_limit'], DEFAULT_REPO_FETCH_LIMIT))
    }


# =============================================================================
# Data Processing Functions
# =============================================================================

def filter_data_by_timeframe(data: List[Dict], date_field: str = 'date', weeks: int = 1) -> List[Dict]:
    """Filter data to only include items from the specified timeframe."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    filtered_data = []
    
    for item in data:
        item_date = datetime.fromisoformat(item[date_field].replace('Z', '+00:00'))
        if item_date >= cutoff_date:
            filtered_data.append(item)
    
    return filtered_data


def prepare_pr_data_with_status(open_prs: List[Dict], merged_prs: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Prepare PR data by adding status information and filtering by timeframe."""
    this_week_open_prs = []
    this_week_merged_prs = []
    
    # Process open PRs
    for pr in filter_data_by_timeframe(open_prs):
        pr['status'] = 'Open'
        this_week_open_prs.append(pr)
    
    # Process merged PRs
    for pr in filter_data_by_timeframe(merged_prs):
        pr['status'] = 'Merged'
        this_week_merged_prs.append(pr)
    
    return this_week_open_prs, this_week_merged_prs


def load_debug_data(debug_file_path: str) -> Tuple[List, List, List, List, List]:
    """Load data from debug file if it exists."""
    if os.path.exists(debug_file_path):
        with open(debug_file_path, 'r') as f:
            debug_data = json.load(f)
        return (
            debug_data.get("commits", []),
            debug_data.get("open_prs", []),
            debug_data.get("merged_prs", []),
            debug_data.get("this_week_commits", []),
            debug_data.get("this_week_prs", [])
        )
    return [], [], [], [], []


def save_debug_data(debug_file_path: str, commits: List, open_prs: List, merged_prs: List, 
                   this_week_commits: List, this_week_prs: List) -> None:
    """Save data to debug file."""
    debug_data = {
        "commits": commits,
        "open_prs": open_prs, 
        "merged_prs": merged_prs,
        "this_week_commits": this_week_commits,
        "this_week_prs": this_week_prs
    }
    with open(debug_file_path, 'w') as f:
        json.dump(debug_data, f, indent=4)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_live_github_data_cached(token: str, target_organizations: List[str], repo_fetch_limit: int) -> Tuple[List, List, List, List, float, float]:
    """Fetch live data from GitHub API with caching."""
    
    # Fetch repository data with timing
    start_time = time.time()
    repo_data_with_dates = get_all_accessible_repo_data(token, specific_org_logins=target_organizations)
    repo_names = [repo_name for repo_name, _ in repo_data_with_dates]
    repo_fetch_time = time.time() - start_time
    
    # Apply repository limit if specified
    if repo_fetch_limit is not None and len(repo_names) > repo_fetch_limit:
        repo_names_for_bulk_fetch = repo_names[:repo_fetch_limit]
    else:
        repo_names_for_bulk_fetch = repo_names
    
    # Fetch bulk data with timing
    start_time = time.time()
    commits, open_prs, merged_prs = get_bulk_data(token, repo_names_for_bulk_fetch)
    bulk_fetch_time = time.time() - start_time
    
    return commits, open_prs, merged_prs, repo_data_with_dates, repo_fetch_time, bulk_fetch_time


def get_github_data(config: Dict[str, Any]) -> Tuple[List, List, List, List, List, List, float, float]:
    """
    Main function to get GitHub data, either from debug file or live API.
    
    Returns:
        Tuple of (commits, open_prs, merged_prs, this_week_commits, this_week_prs, repo_data_with_dates, repo_fetch_time, bulk_fetch_time)
    """
    token = config['github_token']
    debug_mode = config['debug_mode']
    debug_data_file = config['debug_data_file']
    
    if not token:
        st.error(ERROR_MESSAGES['no_token'])
        return [], [], [], [], [], [], 0.0, 0.0
    
    # Try to load debug data if in debug mode
    if debug_mode:
        commits, open_prs, merged_prs, this_week_commits, this_week_prs = load_debug_data(debug_data_file)
        if commits or open_prs or merged_prs:  # If any data was loaded
            return commits, open_prs, merged_prs, this_week_commits, this_week_prs, [], 0.0, 0.0
    
    # Fetch live data
    commits, open_prs, merged_prs, repo_data_with_dates, repo_fetch_time, bulk_fetch_time = fetch_live_github_data_cached(
        token, config['target_organizations'], config['repo_fetch_limit']
    )
    
    # Process data for this week's activity
    this_week_commits = filter_data_by_timeframe(commits)
    this_week_open_prs, this_week_merged_prs = prepare_pr_data_with_status(open_prs, merged_prs)
    this_week_prs = sorted(this_week_open_prs + this_week_merged_prs, key=itemgetter('date'), reverse=True)
    
    # Save debug data when appropriate
    if not debug_mode or not os.path.exists(debug_data_file):
        save_debug_data(debug_data_file, commits, open_prs, merged_prs, this_week_commits, this_week_prs)
    
    return commits, open_prs, merged_prs, this_week_commits, this_week_prs, repo_data_with_dates, repo_fetch_time, bulk_fetch_time


# =============================================================================
# PR Stream Formatting and Display
# =============================================================================

def format_pr_for_stream(pr: Dict[str, Any]) -> str:
    """Format a single PR for the stream display with color coding and TODAY badge."""
    formatted_date = format_timestamp_to_local(pr["date"])
    date_part = formatted_date.split()[0]  # Just the date part (YYYY-MM-DD)
    time_part = " ".join(formatted_date.split()[1:3])  # Time and AM/PM
    
    # Get color and emoji based on date
    date_color, badge = get_date_color_and_emoji(pr["date"])
    
    # Check if this PR is from today for the TODAY badge
    is_today = is_timestamp_today_local(pr["date"])
    
    # Extract PR details
    title = pr["title"]
    repo_name = get_repository_display_name(pr["repo"])
    author = pr["author"]
    pr_number = pr["pr_number"]
    status = pr.get("status", "Open")
    
    # Status emoji
    status_emoji = PR_STATUS_EMOJIS.get(status, "🔄")
    
    # Add TODAY badge if it's from today
    repo_display = f"**[{repo_name}]({pr['repo_url']})**"
    if is_today:
        repo_display = f'<span class="{CSS_CLASSES["today_badge"]}">TODAY</span> {repo_display}'
    
    return f"""{badge} {repo_display} **[#{pr_number}]({pr["url"]})**  
*{title}*  
{status_emoji} {status} • {author}  
📅 <span style="color: {date_color};">{date_part} {time_part}</span>"""


def display_pr_stream(all_prs_data: List[Dict], debug_mode: bool = False) -> List[Dict]:
    """Display the PR stream with proper formatting and controls."""
    if not all_prs_data:
        st.info(INFO_MESSAGES['no_prs_this_week'])
        return []
    
    # Filter PRs to only show those from the LOOK_BACK_DAYS period
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=LOOK_BACK_DAYS)
    recent_prs = []
    
    for pr in all_prs_data:
        try:
            pr_date = datetime.fromisoformat(pr["date"].replace('Z', '+00:00'))
            if pr_date >= cutoff_date:
                recent_prs.append(pr)
        except Exception as e:
            print(f"Error parsing PR date '{pr.get('date', 'unknown')}': {e}")
    
    # Sort PRs by date to ensure newest first
    prs_sorted = sorted(recent_prs, key=lambda x: x["date"], reverse=True)
    
    # Display header and stats on one line
    debug_text = " *[DEBUG]*" if debug_mode else ""
    st.markdown(f"**🔀 Pull Requests{debug_text} • {len(prs_sorted)} PRs**")
    
    # Create scrollable container
    container = st.container(height=STREAM_CONTAINER_HEIGHT)
    
    with container:
        for i, pr in enumerate(prs_sorted):
            pr_markdown = format_pr_for_stream(pr)
            st.markdown(pr_markdown, unsafe_allow_html=True)
            
            # Add separator except for last item
            if i < len(prs_sorted) - 1:
                st.markdown("---")
    
    # Return the PRs data for use in charts
    return prs_sorted


# =============================================================================
# Table Formatting Functions
# =============================================================================

def format_item_with_today_highlighting(row: pd.Series, item_type: str = "pr") -> Dict[str, str]:
    """Format a single item (PR or commit) with TODAY highlighting for table display."""
    is_today = is_timestamp_today_local(row['date'])
    formatted_date = format_timestamp_to_local(row['date'])
    
    repo_link = f"<a href='{row['repo_url']}' target='_blank'>{row['repo']}</a>"
    
    # Add TODAY badge if it's from today
    date_text = formatted_date
    if is_today:
        repo_link = f'<span class="{CSS_CLASSES["today_badge"]}">TODAY</span> {repo_link}'
        date_text = f'<span class="{CSS_CLASSES["today_date"]}">{formatted_date}</span>'
    
    if item_type == "pr":
        pr_link = f"<a href='{row['url']}' target='_blank'>{row['pr_number']}</a>"
        return {
            'Repository': repo_link,
            'PR Number': pr_link,
            'Title': row['title'],
            'Author': row['author'],
            'Date': date_text
        }
    else:  # commit
        branch_link = f"<a href='{row['branch_url']}' target='_blank'>{row['branch_name']}</a>"
        sha_link = f"<a href='{row['url']}' target='_blank'>{row['sha']}</a>"
        return {
            'Repository': repo_link,
            'Branch': branch_link,
            'SHA': sha_link,
            'Message': row['message'],
            'Author': row['author'],
            'Date': date_text
        }


def create_enhanced_table_html(df: pd.DataFrame, columns: List[str]) -> str:
    """Create enhanced HTML table with proper formatting."""
    html_rows = []
    for _, row in df.iterrows():
        cells = [f'<td>{row[col]}</td>' for col in columns]
        html_rows.append(f'<tr>{"".join(cells)}</tr>')
    
    header_cells = [f'<th>{col}</th>' for col in columns]
    header_html = f'<tr>{"".join(header_cells)}</tr>'
    table_html = f'<table class="dataframe"><thead>{header_html}</thead><tbody>{"".join(html_rows)}</tbody></table>'
    
    return f'<div class="{CSS_CLASSES["table_container"]}">{table_html}</div>'


# =============================================================================
# Display Section Functions
# =============================================================================

def display_pull_requests_section(open_prs_data: List[Dict], merged_prs_data: List[Dict]) -> None:
    """Display the detailed pull requests section with tables."""
    st.header("Pull Requests")
    
    # Recent Open PRs
    st.subheader("Recent Open Pull Requests")
    total_open_prs = len(open_prs_data)
    num_open_prs = st.slider("Number to show", 1, max(2, total_open_prs), 
                            min(DEFAULT_DISPLAY_COUNT, total_open_prs), key="num_open_prs")
    st.write(f"Showing **{num_open_prs}** of **{total_open_prs}** open pull requests.")
    
    if total_open_prs > 0:
        df = pd.DataFrame(open_prs_data[:num_open_prs])
        enhanced_prs = [format_item_with_today_highlighting(row, "pr") for _, row in df.iterrows()]
        df_enhanced = pd.DataFrame(enhanced_prs)
        
        columns = ['Repository', 'PR Number', 'Title', 'Author', 'Date']
        table_html = create_enhanced_table_html(df_enhanced, columns)
        st.markdown(table_html, unsafe_allow_html=True)
    
    st.divider()
    
    # Recent Merged PRs  
    st.subheader("Recent Merged Pull Requests")
    total_merged_prs = len(merged_prs_data)
    num_merged_prs = st.slider("Number to show", 1, max(2, total_merged_prs),
                              min(DEFAULT_DISPLAY_COUNT, total_merged_prs), key="num_merged_prs")
    st.write(f"Showing **{num_merged_prs}** of **{total_merged_prs}** merged pull requests.")
    
    if total_merged_prs > 0:
        df = pd.DataFrame(merged_prs_data[:num_merged_prs])
        enhanced_prs = [format_item_with_today_highlighting(row, "pr") for _, row in df.iterrows()]
        df_enhanced = pd.DataFrame(enhanced_prs)
        
        columns = ['Repository', 'PR Number', 'Title', 'Author', 'Date']
        table_html = create_enhanced_table_html(df_enhanced, columns)
        st.markdown(table_html, unsafe_allow_html=True)
    
    st.divider()
    
    # PRs by Repository
    display_prs_by_repository(open_prs_data, merged_prs_data)


def display_prs_by_repository(open_prs_data: List[Dict], merged_prs_data: List[Dict]) -> None:
    """Display PRs filtered by repository selection."""
    st.subheader("Pull Requests by Repository")
    all_prs_data = sorted(open_prs_data + merged_prs_data, key=itemgetter('date'), reverse=True)
    
    if not all_prs_data:
        st.info(ERROR_MESSAGES['no_prs'])
        return
    
    repo_list_prs = sorted(list(set(p['repo'] for p in all_prs_data)))
    col1, col2 = st.columns([3, 1])
    
    with col1:
        selected_repo_prs = st.selectbox("Select Repository", repo_list_prs, key="prs_repo_select")
    
    prs_in_repo = [p for p in all_prs_data if p['repo'] == selected_repo_prs]
    total_prs_in_repo = len(prs_in_repo)
    
    with col2:
        num_prs_repo = st.slider("Number to show", 1, max(2, total_prs_in_repo),
                                min(DEFAULT_DISPLAY_COUNT, total_prs_in_repo), key="num_prs_repo")
    
    st.write(f"Showing **{num_prs_repo}** of **{total_prs_in_repo}** pull requests for **{selected_repo_prs}**.")
    
    if total_prs_in_repo > 0:
        df = pd.DataFrame(prs_in_repo[:num_prs_repo])
        enhanced_prs = [format_item_with_today_highlighting(row, "pr") for _, row in df.iterrows()]
        df_enhanced = pd.DataFrame(enhanced_prs)
        
        columns = ['Repository', 'PR Number', 'Title', 'Author', 'Date']
        table_html = create_enhanced_table_html(df_enhanced, columns)
        st.markdown(table_html, unsafe_allow_html=True)


def display_commits_section(commits_data: List[Dict]) -> None:
    """Display the detailed commits section with tables."""
    st.header("Commits")
    
    # Recent Commits
    st.subheader("Recent Commits")
    total_commits = len(commits_data)
    num_recent_commits = st.slider("Number to show", 1, max(2, total_commits),
                                  min(DEFAULT_DISPLAY_COUNT, total_commits), key="num_recent_commits")
    st.write(f"Showing **{num_recent_commits}** of **{total_commits}** recent commits.")
    
    if total_commits > 0:
        df = pd.DataFrame(commits_data[:num_recent_commits])
        enhanced_commits = [format_item_with_today_highlighting(row, "commit") for _, row in df.iterrows()]
        df_enhanced = pd.DataFrame(enhanced_commits)
        
        columns = ['Repository', 'Branch', 'SHA', 'Message', 'Author', 'Date']
        table_html = create_enhanced_table_html(df_enhanced, columns)
        st.markdown(table_html, unsafe_allow_html=True)
    
    st.divider()
    
    # Commits by Repository
    display_commits_by_repository(commits_data)


def display_commits_by_repository(commits_data: List[Dict]) -> None:
    """Display commits filtered by repository selection."""
    st.subheader("Commits by Repository")
    
    if not commits_data:
        st.info(ERROR_MESSAGES['no_commits'])
        return
    
    repo_list_commits = sorted(list(set(c['repo'] for c in commits_data)))
    col3, col4 = st.columns([3, 1])
    
    with col3:
        selected_repo_commits = st.selectbox("Select Repository", repo_list_commits, key="commits_repo_select")
    
    commits_in_repo = [c for c in commits_data if c['repo'] == selected_repo_commits]
    total_commits_in_repo = len(commits_in_repo)
    
    with col4:
        num_commits_repo = st.slider("Number to show", 1, max(2, total_commits_in_repo),
                                    min(DEFAULT_DISPLAY_COUNT, total_commits_in_repo), key="num_commits_repo")
    
    st.write(f"Showing **{num_commits_repo}** of **{total_commits_in_repo}** commits for **{selected_repo_commits}**.")
    
    if total_commits_in_repo > 0:
        df = pd.DataFrame(commits_in_repo[:num_commits_repo])
        enhanced_commits = [format_item_with_today_highlighting(row, "commit") for _, row in df.iterrows()]
        df_enhanced = pd.DataFrame(enhanced_commits)
        
        columns = ['Repository', 'Branch', 'SHA', 'Message', 'Author', 'Date']
        table_html = create_enhanced_table_html(df_enhanced, columns)
        st.markdown(table_html, unsafe_allow_html=True)


# =============================================================================
# User Statistics Functions
# =============================================================================

def create_user_stats_table(data: List[Dict], data_type: str = "commits") -> pd.DataFrame:
    """Create a user statistics DataFrame from commits or PRs data."""
    if not data:
        return pd.DataFrame()
    
    # Count items per user
    user_counts = {}
    for item in data:
        author = item.get('author', 'Unknown')
        user_counts[author] = user_counts.get(author, 0) + 1
    
    # Convert to DataFrame and sort
    if user_counts:
        df = pd.DataFrame(list(user_counts.items()), columns=['User', 'Count'])
        df = df.sort_values('Count', ascending=False).head(10)  # Top 10 users
        return df
    return pd.DataFrame()




def display_commits_chart(commits_data: List[Dict]) -> None:
    """Display commits user activity as a vertical bar chart."""
    st.markdown("**📊 Commit Activity**")
    
    # Use all data from stream (no additional filtering)
    commits_stats = create_user_stats_table(commits_data, "commits")
    
    if not commits_stats.empty:
        # Limit to top 8 and truncate names
        top_commits = commits_stats.head(8).copy()
        top_commits['User'] = top_commits['User'].apply(
            lambda x: x[:12] + "..." if len(x) > 15 else x
        )
        
        # Create vertical bar chart with Plotly
        fig_commits = go.Figure(go.Bar(
            x=top_commits['User'],
            y=top_commits['Count'],
            marker=dict(
                color='#4A90E2',
                line=dict(color='#2C5AA0', width=1)
            ),
            text=top_commits['Count'],
            textposition='inside',
            textfont=dict(color='white', size=12)
        ))
        
        fig_commits.update_layout(
            height=280,
            margin=dict(l=20, r=20, t=40, b=60),
            showlegend=False,
            xaxis=dict(
                showgrid=False,
                title='',
                tickangle=45
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(128,128,128,0.2)',
                title='Commits'
            ),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig_commits, use_container_width=True)
    else:
        st.markdown("*No recent commit data*")


def display_prs_chart(prs_data: List[Dict]) -> None:
    """Display PRs user activity as a vertical bar chart."""
    st.markdown("**📊 PR Activity**")
    
    # Use all data from stream (no additional filtering)
    prs_stats = create_user_stats_table(prs_data, "prs")
    
    if not prs_stats.empty:
        # Limit to top 8 and truncate names
        top_prs = prs_stats.head(8).copy()
        top_prs['User'] = top_prs['User'].apply(
            lambda x: x[:12] + "..." if len(x) > 15 else x
        )
        
        # Create vertical bar chart with Plotly
        fig_prs = go.Figure(go.Bar(
            x=top_prs['User'],
            y=top_prs['Count'],
            marker=dict(
                color='#5B9BD5',
                line=dict(color='#3A7BD5', width=1)
            ),
            text=top_prs['Count'],
            textposition='inside',
            textfont=dict(color='white', size=12)
        ))
        
        fig_prs.update_layout(
            height=280,
            margin=dict(l=20, r=20, t=40, b=60),
            showlegend=False,
            xaxis=dict(
                showgrid=False,
                title='',
                tickangle=45
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(128,128,128,0.2)',
                title='Pull Requests'
            ),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
        st.plotly_chart(fig_prs, use_container_width=True)
    else:
        st.markdown("*No recent PR data*")


# =============================================================================
# Repository Data Preparation
# =============================================================================

def prepare_repo_data_for_commit_stream(config: Dict[str, Any], commits_data: List[Dict], 
                                       open_prs_data: List[Dict], merged_prs_data: List[Dict],
                                       repo_data_from_fetch: List[Tuple]) -> List[Tuple]:
    """Prepare repository data for the commit stream component."""
    if not config['debug_mode'] and config['github_token']:
        print(f"📋 [MAIN DASHBOARD] Got {len(repo_data_from_fetch)} repos with push dates for commit stream")
        return repo_data_from_fetch
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
        mock_date = datetime.now(timezone.utc).isoformat()
        repo_data_with_dates = [(name, mock_date) for name in existing_repo_names]
        print(f"📋 [MAIN DASHBOARD] DEBUG MODE: Created mock repo data for {len(existing_repo_names)} repos")
        
        return repo_data_with_dates


# =============================================================================
# CSS and Styling
# =============================================================================

def apply_custom_styling() -> None:
    """Apply custom CSS styling to the application."""
    st.markdown("""
    <style>
        .stAppToolbar {display:none;}
    </style>
    """, unsafe_allow_html=True)
    
    # Main custom CSS for tables and highlighting
    custom_css = f"""
    <style>
    /* Compact header styling */
    h1 {{
        margin-bottom: 0.5rem !important;
    }}
    
    h2 {{
        margin-top: 1rem !important;
        margin-bottom: 0.5rem !important;
    }}
    
    h3 {{
        margin-top: 0.5rem !important;
        margin-bottom: 0.3rem !important;
    }}
    
    .{CSS_CLASSES["table_container"]} {{
        height: {TABLE_CONTAINER_HEIGHT}px;
        overflow-y: auto;
    }}
    
    /* Today highlighting styles - only for date text */
    .{CSS_CLASSES["today_date"]} {{
        color: #ff6f00 !important;
        font-weight: 600 !important;
    }}
    
    .{CSS_CLASSES["today_badge"]} {{
        background: linear-gradient(135deg, {BADGE_COLORS["today_gradient_start"]}, {BADGE_COLORS["today_gradient_end"]});
        color: white;
        padding: 2px 6px;
        border-radius: 10px;
        font-size: 9px;
        font-weight: 600;
        margin-right: 6px;
        text-shadow: 0 1px 1px rgba(0,0,0,0.2);
        display: inline-block;
    }}
    
    /* Status styling */
    .{CSS_CLASSES["status_open"]} {{
        background-color: {BADGE_COLORS["open_bg"]};
        color: {BADGE_COLORS["open_text"]};
        padding: 2px 6px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 500;
    }}
    
    .{CSS_CLASSES["status_merged"]} {{
        background-color: {BADGE_COLORS["merged_bg"]};
        color: {BADGE_COLORS["merged_text"]};
        padding: 2px 6px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 500;
    }}
    
    /* Stream container styling */
    .stColumns > div:first-child,
    .stColumns > div:last-child {{
        padding: 0 2rem !important;
    }}
    
    /* Main app container */
    .main .block-container.stMainBlockContainer {{
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }}
    
    /* Override specific Streamlit class with 6rem top padding */
    .st-emotion-cache-zy6yx3 {{
        padding-top: 0.5rem !important;
    }}
    
    .stAppHeader {{
        display: none !important;    
    }}
    
    /* Hide sidebar collapse button */
    div[data-testid="stSidebarCollapseButton"] {{
        display: none !important;
    }}
    
    button[data-testid="stBaseButton-headerNoPadding"] {{
        display: none !important;
    }}
    
    button[kind="headerNoPadding"] {{
        display: none !important;
    }}
    
    /* Reduce all gaps and spacing */
    .element-container {{
        margin-bottom: 0.2rem !important;
    }}
    
    .stMarkdown {{
        margin-bottom: 0.2rem !important;
    }}
    
    .stButton {{
        margin-top: 0.2rem !important;
        margin-bottom: 0.2rem !important;
    }}
    
    /* Stream content borders and styling */
    div[data-testid="stContainer"] {{
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        background: linear-gradient(145deg, rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0.01));
        backdrop-filter: blur(10px);
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
        margin: 2px auto;
        max-width: 99%;
        padding: 0.5rem !important;
    }}
    
    /* Center the stream columns */
    .stColumns {{
        gap: 0.5rem !important;
        justify-content: center !important;
        max-width: 1400px;
        margin: 0 auto;
    }}
    
    /* Set max width for stream containers */
    .stColumns > div:first-child,
    .stColumns > div:nth-child(2) {{
        max-width: 600px !important;
    }}
    
    /* Reduce divider spacing */
    hr {{
        margin: 0.3rem 0 !important;
    }}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


# =============================================================================
# Sidebar Functions  
# =============================================================================

def display_user_info(user_info: Dict[str, Any]) -> None:
    """Display user information at the top of the sidebar."""
    if not user_info:
        return
    
    st.sidebar.markdown("### 👤 User Info")
    
    # Basic user info
    name = user_info.get("name") or user_info.get("login", "Unknown")
    login = user_info.get("login", "")
    if name != login and login:
        st.sidebar.markdown(f"**{name}** (@{login})")
    else:
        st.sidebar.markdown(f"**{name}**")
    
    # Company and location
    company = user_info.get("company")
    location = user_info.get("location")
    if company or location:
        info_parts = []
        if company:
            info_parts.append(f"🏢 {company}")
        if location:
            info_parts.append(f"📍 {location}")
        st.sidebar.markdown(" • ".join(info_parts))
    
    # Stats in compact format
    repos = user_info.get("repositories", {}).get("totalCount", 0)
    followers = user_info.get("followers", {}).get("totalCount", 0)
    following = user_info.get("following", {}).get("totalCount", 0)
    
    contributions = user_info.get("contributionsCollection", {})
    commits = contributions.get("totalCommitContributions", 0)
    prs = contributions.get("totalPullRequestContributions", 0)
    
    # Display stats compactly
    st.sidebar.markdown(f"📦 **{repos}** repos • 👥 **{followers}** followers")
    st.sidebar.markdown(f"📝 **{commits}** commits • 🔀 **{prs}** PRs")


def display_sidebar(config: Dict[str, Any], fetch_time: float, commits_count: int = 0, prs_count: int = 0, 
                   repo_fetch_time: float = 0.0, bulk_fetch_time: float = 0.0, user_info: Dict[str, Any] = None) -> None:
    """Display the application sidebar with settings and status."""
    # Display user info at the top
    if user_info:
        display_user_info(user_info)
        st.sidebar.markdown("---")
    
    st.sidebar.markdown("### ⚙️ Settings")
    
    # Debug mode status
    if config['debug_mode']:
        st.sidebar.warning(INFO_MESSAGES['debug_mode_on'])
        # Only show debug file status when in debug mode
        from constants import COMMIT_STREAM_DEBUG_FILE
        if os.path.exists(COMMIT_STREAM_DEBUG_FILE):
            st.sidebar.text("Using debug.json")
    else:
        st.sidebar.info(INFO_MESSAGES['debug_mode_off'])
        if st.sidebar.button(INFO_MESSAGES['refresh_data']):
            st.cache_data.clear()
            st.rerun()
    
    # Data loading times at bottom
    st.sidebar.markdown("---")
    st.sidebar.markdown("**⏱️ Performance:**")
    st.sidebar.text(f"Total fetch: {fetch_time:.2f}s")
    
    # Show detailed timing only when not in debug mode and times are available
    if not config['debug_mode'] and (repo_fetch_time > 0 or bulk_fetch_time > 0):
        if repo_fetch_time > 0:
            st.sidebar.text(f"Repo data: {repo_fetch_time:.2f}s")
        if bulk_fetch_time > 0:
            st.sidebar.text(f"Bulk data: {bulk_fetch_time:.2f}s")


# =============================================================================
# Main Application Function
# =============================================================================

def main() -> None:
    """Main application entry point."""
    # Page configuration
    st.set_page_config(
        page_title="GitHub Dashboard (GraphQL)",
        page_icon="⚡",
        layout="wide"
    )
    st.markdown("#### ⚡ GitHub Dashboard")
    
    # Get configuration and fetch data
    config = get_application_config()
    
    # Show loading spinner while fetching data
    with st.spinner('Loading GitHub data...'):
        start_time = time.time()
        
        (commits_data, open_prs_data, merged_prs_data, 
         this_week_commits, this_week_prs, repo_data_from_fetch, 
         repo_fetch_time, bulk_fetch_time) = get_github_data(config)
    
        end_time = time.time()
        fetch_time = end_time - start_time
        
        # Fetch user information
        user_info = {}
        if config['github_token'] and not config['debug_mode']:
            try:
                user_info = fetch_user_info(config['github_token'])
            except Exception as e:
                print(f"Error fetching user info: {e}")
    
    # Prepare repository data for commit stream
    repo_data_with_dates = prepare_repo_data_for_commit_stream(
        config, commits_data, open_prs_data, merged_prs_data, repo_data_from_fetch
    )
    
    # Apply custom styling
    apply_custom_styling()
    
    # Display main content with 2 columns: commits (400px), PRs (400px)
    stream_col1, stream_col2 = st.columns([1, 1])
    
    with stream_col1:
        stream_commits = display_commit_stream(config['github_token'], repo_data_with_dates, config['debug_mode'])
        # Display commits chart below the stream
        display_commits_chart(stream_commits)
    
    with stream_col2:
        all_prs_data = sorted(open_prs_data + merged_prs_data, key=itemgetter('date'), reverse=True)
        stream_prs = display_pr_stream(all_prs_data, config['debug_mode'])
        # Display PRs chart below the stream
        display_prs_chart(stream_prs)
    
    st.divider()
    
    # Display detailed sections
    display_pull_requests_section(open_prs_data, merged_prs_data)
    display_commits_section(commits_data)
    
    # Display sidebar with metrics
    commits_count = len(commits_data) if commits_data else 0
    prs_count = len(open_prs_data) + len(merged_prs_data) if open_prs_data and merged_prs_data else 0
    display_sidebar(config, fetch_time, commits_count, prs_count, repo_fetch_time, bulk_fetch_time, user_info)


if __name__ == "__main__":
    main()