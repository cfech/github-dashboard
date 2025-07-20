# GitHub Personal Dashboard (GraphQL)

This is a web-based dashboard built with Python and Streamlit to provide a quick overview of your GitHub repositories. It uses GitHub's efficient GraphQL API to fetch data in bulk, displaying your most recently updated repositories, their open pull requests, and their latest commits.

## Features

-   ⚡ **Efficient**: Uses a single GraphQL query to fetch data for multiple repositories at once.
-   ⚙️ **Configurable**: Set how many of your most recently updated repos to display.
-   🐛 **Debug Mode**: Includes a debug mode to load data from a local file, speeding up UI development and avoiding API rate limits.
-   🏢 **Enterprise Ready**: Can be pointed to a private GitHub Enterprise server.

***
## Prerequisites

Before you begin, ensure you have the following:

-   **Python 3.12**
-   **Pipenv** (`pip install pipenv`)
-   A **GitHub Personal Access Token (PAT)** with the `repo` scope.

***
## Installation & Setup

1.  **Create Project Files**:
    Place the two project files in a new directory:
    -   `dashboard_app_graphql.py`
    -   `github_service_graphql.py`

2.  **Create the `Pipfile`**:
    Create a file named `Pipfile` in the same directory with the following content:
    ```toml
    [[source]]
    url = "[https://pypi.org/simple](https://pypi.org/simple)"
    verify_ssl = true
    name = "pypi"
    
    [packages]
    streamlit = "*"
    pandas = "*"
    python-dotenv = "*"
    requests = "*"
    
    [requires]
    python_version = "3.12"
    ```

3.  **Set Environment Variables**:
    Create a file named `.env` in the same directory. This file will store your secret token.
    ```
    # Your Personal Access Token with 'repo' scope
    GITHUB_TOKEN="ghp_YourTokenGoesHere"
    
    # Optional: For GitHub Enterprise, uncomment and set this URL
    # GITHUB_BASE_URL="https://your-github-hostname/api/v3"
    ```

4.  **Install Dependencies**:
    Open your terminal in the project directory and run:
    ```bash
    pipenv install
    ```
    This will create a virtual environment and install all the required packages.

***
## Running the Application

To run the dashboard, execute the following command from your project directory:

```bash
pipenv run streamlit run dashboard_app_graphql.py
```
## Usage

-   **Repo Limit**: Use the number input in the sidebar to change how many of your most recently updated repositories are shown.
-   **Debug Mode**: To use local data for development, open `dashboard_app_graphql.py` and change the `DEBUG_MODE` constant to `True`. Run the app once with `DEBUG_MODE = False` to create the initial `github_data.json` file.# github-dashboard
