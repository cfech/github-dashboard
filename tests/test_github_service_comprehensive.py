import unittest
from unittest.mock import patch, MagicMock
from github_service_graphql import (
    execute_graphql_query, fetch_user_info, fetch_user_affiliated_repositories,
    fetch_user_organizations, fetch_organization_repositories,
    determine_organizations_to_fetch, parse_pull_requests_from_repository,
    parse_commits_from_repository, get_all_accessible_repository_names,
    get_all_accessible_repository_data, get_bulk_repository_data
)


class TestGithubServiceComprehensive(unittest.TestCase):
    """Comprehensive tests for GitHub service functions."""

    def test_fetch_user_info_success(self):
        """Test successful user info fetching."""
        with patch('github_service_graphql.execute_graphql_query') as mock_query:
            mock_query.return_value = {
                "data": {
                    "viewer": {
                        "login": "testuser",
                        "name": "Test User",
                        "email": "test@example.com"
                    }
                }
            }
            
            result = fetch_user_info("fake_token")
            self.assertEqual(result["login"], "testuser")
            self.assertEqual(result["name"], "Test User")

    def test_fetch_user_info_error(self):
        """Test user info fetching with error."""
        with patch('github_service_graphql.execute_graphql_query') as mock_query:
            mock_query.side_effect = Exception("API Error")
            
            result = fetch_user_info("fake_token")
            self.assertEqual(result, {})

    def test_fetch_user_affiliated_repositories(self):
        """Test fetching user affiliated repositories."""
        with patch('github_service_graphql.execute_graphql_query') as mock_query:
            mock_query.return_value = {
                "data": {
                    "viewer": {
                        "repositories": {
                            "nodes": [
                                {"nameWithOwner": "user/repo1", "pushedAt": "2025-01-01T00:00:00Z"}
                            ],
                            "pageInfo": {"hasNextPage": False, "endCursor": None}
                        }
                    }
                }
            }
            
            result = fetch_user_affiliated_repositories("fake_token")
            self.assertEqual(result["user/repo1"], "2025-01-01T00:00:00Z")

    def test_fetch_user_organizations(self):
        """Test fetching user organizations."""
        with patch('github_service_graphql.execute_graphql_query') as mock_query:
            mock_query.return_value = {
                "data": {
                    "viewer": {
                        "organizations": {
                            "nodes": [{"login": "test-org"}],
                            "pageInfo": {"hasNextPage": False, "endCursor": None}
                        }
                    }
                }
            }
            
            result = fetch_user_organizations("fake_token")
            self.assertEqual(result, ["test-org"])

    def test_fetch_organization_repositories(self):
        """Test fetching organization repositories."""
        with patch('github_service_graphql.execute_graphql_query') as mock_query:
            mock_query.return_value = {
                "data": {
                    "organization": {
                        "repositories": {
                            "nodes": [
                                {"nameWithOwner": "org/repo1", "pushedAt": "2025-01-01T00:00:00Z"}
                            ],
                            "pageInfo": {"hasNextPage": False, "endCursor": None}
                        }
                    }
                }
            }
            
            result = fetch_organization_repositories("fake_token", "test-org")
            self.assertEqual(result["org/repo1"], "2025-01-01T00:00:00Z")

    def test_fetch_organization_repositories_not_found(self):
        """Test fetching organization repositories when org not found."""
        with patch('github_service_graphql.execute_graphql_query') as mock_query:
            mock_query.return_value = {"data": {"organization": None}}
            
            result = fetch_organization_repositories("fake_token", "nonexistent-org")
            self.assertEqual(result, {})

    def test_determine_organizations_to_fetch_specific(self):
        """Test organization determination with specific list."""
        result = determine_organizations_to_fetch("fake_token", ["org1", "org2"])
        self.assertEqual(result, ["org1", "org2"])

    def test_determine_organizations_to_fetch_empty(self):
        """Test organization determination with empty list."""
        result = determine_organizations_to_fetch("fake_token", [])
        self.assertEqual(result, [])

    def test_determine_organizations_to_fetch_none(self):
        """Test organization determination with None."""
        with patch('github_service_graphql.fetch_user_organizations') as mock_fetch:
            mock_fetch.return_value = ["user-org"]
            
            result = determine_organizations_to_fetch("fake_token", None)
            self.assertEqual(result, ["user-org"])

    def test_parse_pull_requests_from_repository(self):
        """Test PR parsing from repository data."""
        repo_data = {
            "openPRs": {
                "nodes": [
                    {
                        "number": 123,
                        "title": "Test PR",
                        "author": {"login": "testuser"},
                        "createdAt": "2025-01-01T00:00:00Z",
                        "url": "https://github.com/owner/repo/pull/123"
                    }
                ]
            }
        }
        
        result = parse_pull_requests_from_repository(
            repo_data, "owner/repo", "https://github.com/owner/repo", "openPRs"
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["pr_number"], 123)
        self.assertEqual(result[0]["title"], "Test PR")
        self.assertEqual(result[0]["author"], "testuser")

    def test_parse_pull_requests_no_author(self):
        """Test PR parsing with missing author."""
        repo_data = {
            "openPRs": {
                "nodes": [
                    {
                        "number": 123,
                        "title": "Test PR",
                        "author": None,
                        "createdAt": "2025-01-01T00:00:00Z",
                        "url": "https://github.com/owner/repo/pull/123"
                    }
                ]
            }
        }
        
        result = parse_pull_requests_from_repository(
            repo_data, "owner/repo", "https://github.com/owner/repo", "openPRs"
        )
        
        self.assertEqual(result[0]["author"], "Unknown")

    def test_parse_commits_from_repository(self):
        """Test commit parsing from repository data."""
        repo_data = {
            "defaultBranchRef": {
                "name": "main",
                "target": {
                    "history": {
                        "nodes": [
                            {
                                "oid": "abc123def456",
                                "messageHeadline": "Test commit",
                                "committedDate": "2025-01-01T00:00:00Z",
                                "author": {"name": "Test User"},
                                "url": "https://github.com/owner/repo/commit/abc123"
                            }
                        ]
                    }
                }
            }
        }
        
        result = parse_commits_from_repository(
            repo_data, "owner/repo", "https://github.com/owner/repo"
        )
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["sha"], "abc123d")
        self.assertEqual(result[0]["message"], "Test commit")
        self.assertEqual(result[0]["author"], "Test User")
        self.assertEqual(result[0]["branch_name"], "main")

    def test_parse_commits_no_default_branch(self):
        """Test commit parsing with no default branch."""
        repo_data = {"defaultBranchRef": None}
        
        result = parse_commits_from_repository(
            repo_data, "owner/repo", "https://github.com/owner/repo"
        )
        
        self.assertEqual(result, [])

    def test_get_bulk_repository_data_empty_repos(self):
        """Test bulk data fetching with empty repository list."""
        result = get_bulk_repository_data("fake_token", [])
        self.assertEqual(result, ([], [], []))

    def test_execute_graphql_query_with_variables(self):
        """Test GraphQL query execution with variables."""
        with patch('github_service_graphql.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {"data": "test"}
            mock_post.return_value = mock_response
            
            variables = {"first": 10}
            result = execute_graphql_query("fake_token", "query", variables)
            
            self.assertEqual(result, {"data": "test"})
            # Verify variables were included in payload
            called_args = mock_post.call_args
            self.assertIn("variables", called_args[1]["json"])

    def test_get_all_accessible_repository_names_pagination(self):
        """Test repository names fetching with pagination."""
        with patch('github_service_graphql.fetch_user_affiliated_repositories') as mock_user:
            with patch('github_service_graphql.determine_organizations_to_fetch') as mock_orgs:
                with patch('github_service_graphql.fetch_organization_repositories') as mock_org_repos:
                    mock_user.return_value = {"user/repo1": "2025-01-02T00:00:00Z"}
                    mock_orgs.return_value = ["test-org"]
                    mock_org_repos.return_value = {"org/repo1": "2025-01-01T00:00:00Z"}
                    
                    result = get_all_accessible_repository_names("fake_token")
                    
                    # Should be sorted by push date (newest first)
                    self.assertEqual(result, ["user/repo1", "org/repo1"])

    def test_get_all_accessible_repository_data_integration(self):
        """Test repository data fetching integration."""
        with patch('github_service_graphql.fetch_user_affiliated_repositories') as mock_user:
            with patch('github_service_graphql.determine_organizations_to_fetch') as mock_orgs:
                mock_user.return_value = {"user/repo1": "2025-01-01T00:00:00Z"}
                mock_orgs.return_value = []
                
                result = get_all_accessible_repository_data("fake_token")
                
                self.assertEqual(result, [("user/repo1", "2025-01-01T00:00:00Z")])

    @patch('github_service_graphql.execute_graphql_query')
    def test_get_bulk_repository_data_with_data(self, mock_query):
        """Test bulk data fetching with actual data."""
        mock_query.return_value = {
            "data": {
                "repo0": {
                    "nameWithOwner": "owner/repo1",
                    "url": "https://github.com/owner/repo1",
                    "openPRs": {"nodes": []},
                    "mergedPRs": {"nodes": []},
                    "defaultBranchRef": {
                        "name": "main",
                        "target": {
                            "history": {
                                "nodes": [{
                                    "oid": "abc123",
                                    "messageHeadline": "Test commit",
                                    "committedDate": "2025-01-01T00:00:00Z",
                                    "author": {"name": "Test User"},
                                    "url": "https://github.com/owner/repo1/commit/abc123"
                                }]
                            }
                        }
                    }
                }
            }
        }
        
        commits, open_prs, merged_prs = get_bulk_repository_data("fake_token", ["owner/repo1"])
        
        self.assertEqual(len(commits), 1)
        self.assertEqual(len(open_prs), 0)
        self.assertEqual(len(merged_prs), 0)
        self.assertEqual(commits[0]["repo"], "owner/repo1")


if __name__ == '__main__':
    unittest.main()