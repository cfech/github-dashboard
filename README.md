# GitHub Dashboard (GraphQL)

This project implements a GitHub dashboard application that leverages the GitHub GraphQL API to fetch and display repository information. It provides a user-friendly interface to visualize data related to your GitHub repositories.

## Technologies Used

This application is built with:

*   **Python 3.x**: The core programming language.
*   **Streamlit**: For creating the interactive web dashboard.
*   **Pandas**: For data manipulation and analysis.
*   **python-dotenv**: For managing environment variables.
*   **Requests**: For making HTTP requests to the GitHub GraphQL API.

## How to Run

Follow these steps to set up and run the application:

### Prerequisites

*   **Python 3.x**: Ensure you have Python installed on your system.
*   **Pipenv**: This project uses Pipenv for dependency management. If you don't have it installed, you can install it using pip:
    ```bash
    pip install pipenv
    ```

### Setup and Execution

1.  **Navigate to the `graphql` directory**:
    ```bash
    cd /Users/connorfech/Desktop/code/github-dashboard/graphql
    ```

2.  **Install Dependencies**:
    Install the project dependencies using Pipenv. This will create a virtual environment and install all necessary packages.
    ```bash
    pipenv install
    ```

3.  **Activate the Virtual Environment**:
    Enter the Pipenv shell to activate the virtual environment.
    ```bash
    pipenv shell
    ```

4.  **Run the Application**:
    Once the virtual environment is active, you can run the Streamlit application:
    ```bash
    streamlit run dashboard_app_graphql.py
    ```
    This command will open the dashboard in your web browser.

## Environment Variables

Before running the application, you need to set up a `.env` file in the `graphql` directory with the following environment variables:

*   `GITHUB_TOKEN`: Your personal GitHub access token. This token is required to authenticate with the GitHub GraphQL API and fetch repository data.

    **How to get a GitHub Token:**
    1.  Go to your GitHub settings.
    2.  Navigate to "Developer settings" -> "Personal access tokens" -> "Tokens (classic)".
    3.  Click "Generate new token" (or "Generate new token (classic)").
    4.  Give your token a descriptive name (e.g., "GitHub Dashboard Token").
    5.  Select the necessary scopes. For this application, you will likely need at least `repo` scope to access repository information.
    6.  Click "Generate token" and copy the token.



*   `GITHUB_GRAPHQL_URL` (Optional): The URL for the GitHub GraphQL API. Defaults to `https://api.github.com/graphql`. You typically won't need to change this unless you are using a GitHub Enterprise instance with a different API endpoint. Example: `GITHUB_GRAPHQL_URL=https://github.yourcompany.com/api/graphql`.

    **Example `.env` file:**
    ```
    GITHUB_TOKEN=your_github_personal_access_token_here
    # GITHUB_GRAPHQL_URL=https://api.github.com/graphql
    ```
    Replace `your_github_personal_access_token_here` with the actual token you generated.

## Internal Configuration (Code-based)

The following variables are configured directly within the `dashboard_app_graphql.py` file. To change these, you will need to modify the source code.

*   `DEBUG_DATA_FILE`: The name of the JSON file used to store cached GitHub data when `DEBUG_MODE` is enabled. Default is `github_data.json`.

* `TARGET_ORGANIZATIONS` (Optional): A comma-separated string of GitHub organization logins (e.g., `org1,org2`). If set, the application will primarily fetch repositories from these organizations. If omitted, it will attempt to fetch repositories from all organizations the authenticated user is a member of, in addition to personal repositories.

*   `REPO_FETCH_LIMIT` (Optional): An integer specifying the maximum number of repositories to fetch data for. This can be useful for limiting API calls during development or for focusing on a subset of repositories. For example, `REPO_FETCH_LIMIT=50`.

*   `DEBUG_MODE` (Optional): Set to `True` to enable debug mode. In debug mode, the application will attempt to load data from a local JSON file (`github_data.json`) if it exists, and save fetched data to this file. Example: `DEBUG_MODE=True`.

*   `st.cache_data(ttl=...)`: The `ttl` (time-to-live) parameter for the Streamlit data cache. This determines how long fetched GitHub data is cached in memory before being re-fetched. The default is `3600` seconds (1 hour). You can find this in the `@st.cache_data` decorator in `dashboard_app_graphql.py`.