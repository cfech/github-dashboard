# GitHub Dashboard

A modern, real-time GitHub dashboard built with Streamlit that provides comprehensive visibility into your GitHub repositories, commits, and pull requests across multiple organizations.

## Overview

This dashboard aggregates data from your accessible GitHub repositories and presents it in a clean, interactive interface. It features live activity streams, detailed repository analytics, and performance metrics to help you stay on top of your development workflow.

### Key Features

- **Live Activity Streams**: Real-time feeds of commits and pull requests
- **Multi-Organization Support**: Aggregate data across multiple GitHub organizations
- **Advanced Filtering**: Filter by repository, time periods, and activity types
- **Performance Monitoring**: Built-in timing metrics and caching
- **Debug Mode**: Local data caching for development and testing
- **Responsive Design**: Optimized for various screen sizes

## Technology Stack

- **Frontend**: Streamlit (Python web framework)
- **API Integration**: GitHub GraphQL API v4
- **Data Processing**: Pandas for data manipulation
- **Styling**: Custom CSS with Streamlit components
- **Caching**: Streamlit's built-in caching system
- **Environment Management**: Python-dotenv for configuration

### Architecture

The application follows a modular architecture with clear separation of concerns:

- `dashboard_app_graphql.py` - Main Streamlit application and UI components
- `github_service_graphql.py` - GitHub API service layer with GraphQL queries
- `commit_stream.py` - Real-time commit stream functionality  
- `constants.py` - Centralized configuration and constants
- `utils.py` - Shared utility functions
- `tests/` - Test suite for all components

## Installation & Setup

### Prerequisites

- Python 3.8+
- GitHub Personal Access Token
- Internet connection for GitHub API access

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd github-dashboard
   ```

2. **Install dependencies**
   ```bash
   pipenv install
   ```

3. **Set up environment variables**
   ```bash
   GITHUB_TOKEN="your token"
   GITHUB_API_URL="your github url if not using default"
   TARGET_ORGANIZATIONS="org1,org2,org3"
   ```

4. **Run the application**
   ```bash
   pienv run streamlit run dashboard_app_graphql.py
   ```

5. **Access the dashboard**
   Open your browser to `http://localhost:8501`

## Configuration

### Environment Variables

#### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub Personal Access Token with repo access | `ghp_xxxxxxxxxxxxxxxxxxxx` |

#### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REPO_FETCH_LIMIT` | `25` | Maximum number of repositories to fetch |
| `DEBUG_MODE` | `False` | Enable debug mode for local development |
| `TARGET_ORGANIZATIONS` | `""` | Comma-separated list of GitHub organizations to fetch (empty = user repos only) |
| `GITHUB_API_URL` | `https://api.github.com/graphql` | GitHub GraphQL API endpoint |

### GitHub Token Setup

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate a new token with the following scopes:
   - `repo` - Full control of private repositories
   - `read:org` - Read org and team membership
   - `read:user` - Read user profile data

3. Add the token to your `.env` file:
   ```bash
   GITHUB_TOKEN=your_token_here
   ```

### Configuration Options

#### Debug Mode

When `DEBUG_MODE=True` in `constants.py`, the application:
- Uses cached data from local JSON files
- Displays "[DEBUG]" indicators in the UI
- Shows debug file status in sidebar
- Skips live API calls for faster development

#### Organization Targeting

Configure which organizations to fetch using the `TARGET_ORGANIZATIONS` environment variable:

```bash
# Fetch from specific organizations
TARGET_ORGANIZATIONS="your-org-1,your-org-2,your-org-3"

# Fetch only user repositories (no organizations)
TARGET_ORGANIZATIONS=""

# If not set, will fetch from all user organizations
# TARGET_ORGANIZATIONS not set
```

#### Performance Tuning

Adjust these constants in `constants.py` for optimal performance:

```python
# Repository limits
DEFAULT_REPO_FETCH_LIMIT: int = 25
COMMIT_STREAM_REPO_LIMIT: int = 30
MAX_REPOS_FOR_COMMIT_STREAM: int = 5

# API timeouts
REQUEST_TIMEOUT: int = 30
GRAPHQL_QUERY_TIMEOUT: int = 45

# UI settings
STREAM_CONTAINER_HEIGHT: int = 900
```

### Advanced Configuration

#### Custom Styling

The application includes extensive CSS customization options in `constants.py`:

- `DATE_COLORS` - Timeline color scheme
- `BADGE_COLORS` - Status badge colors  
- `CSS_CLASSES` - CSS class mappings

#### Data Caching

Two types of caching are available:

1. **Streamlit Cache**: Automatic 5-minute TTL for API calls
2. **Debug Files**: Local JSON storage for development
   - `github_data.json` - Main dashboard data
   - `cs_debug.json` - Commit stream data

## Usage

### Dashboard Sections

1. **Live Activity Streams** - Real-time commits and PR feeds
2. **Pull Requests** - Detailed PR tables with filtering
3. **Commits** - Repository commit history with branch information
4. **Sidebar** - Performance metrics and configuration status

### Keyboard Shortcuts

- `R` - Refresh data
- `S` - Toggle sidebar
- `F11` - Full screen mode

### Filtering & Search

- Use repository dropdowns to filter by specific repos
- Adjust display limits with sliders
- Sort by date, author, or repository
- Filter by time periods (today, this week, etc.)

## Development

### Running Tests

```bash
# Run all tests with unittest
python -m unittest discover tests/ -v

# Run specific test file
python -m unittest tests.test_github_service_graphql -v

# Run specific test class
python -m unittest tests.test_github_service_graphql.TestGitHubService -v

# Run with pattern matching
python -m unittest discover -s tests/ -p "test_*.py" -v
```

### Development Mode

1. Set `DEBUG_MODE = True` in `constants.py`
2. Ensure debug JSON files exist with sample data
3. Run the application - it will use cached data instead of API calls

### Contributing

1. Follow the existing code structure and naming conventions
2. Add tests for new functionality
3. Update constants in `constants.py` rather than hardcoding values
4. Use the shared utility functions in `utils.py`

## Troubleshooting

### Common Issues

**"No token" error**
- Ensure `GITHUB_TOKEN` is set in your environment
- Verify the token has correct permissions

**Empty data display**  
- Check if your token has access to the target organizations
- Verify the organizations exist in `DEFAULT_TARGET_ORGANIZATIONS`

**Slow performance**
- Reduce `REPO_FETCH_LIMIT` in environment variables
- Enable debug mode for development
- Check network connectivity

**GraphQL errors**
- Verify token permissions include `repo` and `read:org`
- Check API rate limits (5000 requests/hour)

### Debug Information

Enable debug mode and check the sidebar for:
- Performance timing
- Data load status  
- Cache utilization
- API call metrics

## License

This project is provided as-is for educational and development purposes.