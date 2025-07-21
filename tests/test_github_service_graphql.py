import unittest
from unittest.mock import patch, MagicMock
from github_service_graphql import _run_graphql_query, _build_bulk_query, get_all_accessible_repo_names, \
    get_bulk_data


class TestGithubServiceGraphQL(unittest.TestCase):

    @patch('github_service_graphql.requests.post')
    def test_run_graphql_query(self, mock_post):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"data": "test"}
        mock_post.return_value = mock_response

        response = _run_graphql_query("fake_token", "query")
        self.assertEqual(response, {"data": "test"})

    @patch('github_service_graphql._run_graphql_query')
    def test_get_all_accessible_repo_names(self, mock_run_query):
        mock_run_query.side_effect = [
            # Viewer repos
            {
                "data": {
                    "viewer": {
                        "repositories": {
                            "nodes": [{"nameWithOwner": "owner/repo1", "pushedAt": "2025-01-01T00:00:00Z"}],
                            "pageInfo": {"hasNextPage": False, "endCursor": None}
                        }
                    }
                }
            },
            # Orgs
            {
                "data": {
                    "viewer": {
                        "organizations": {
                            "nodes": [{"login": "my-org"}],
                            "pageInfo": {"hasNextPage": False, "endCursor": None}
                        }
                    }
                }
            },
            # Org repos
            {
                "data": {
                    "organization": {
                        "repositories": {
                            "nodes": [{"nameWithOwner": "my-org/repo2", "pushedAt": "2025-01-02T00:00:00Z"}],
                            "pageInfo": {"hasNextPage": False, "endCursor": None}
                        }
                    }
                }
            }
        ]
        repos = get_all_accessible_repo_names("fake_token", specific_org_logins=None)
        self.assertIn("owner/repo1", repos)
        self.assertIn("my-org/repo2", repos)
        self.assertEqual(repos, ["my-org/repo2", "owner/repo1"]) # Sorted by pushedAt

    def test_build_bulk_query(self):
        query = _build_bulk_query(["owner/repo1", "owner/repo2"], 10, 5)
        self.assertIn("repo0: repository(owner: \"owner\", name: \"repo1\")", query)
        self.assertIn("repo1: repository(owner: \"owner\", name: \"repo2\")", query)
        self.assertIn("history(first: 10)", query)
        self.assertIn("pullRequests(states: [OPEN], first: 5", query)

    @patch('github_service_graphql._run_graphql_query')
    def test_get_bulk_data(self, mock_run_query):
        mock_run_query.return_value = {
            "data": {
                "repo0": {
                    "nameWithOwner": "owner/repo1",
                    "url": "https://github.com/owner/repo1",
                    "defaultBranchRef": {
                        "name": "main",
                        "target": {
                            "history": {
                                "nodes": [
                                    {
                                        "oid": "1234567",
                                        "url": "https://github.com/owner/repo1/commit/1234567",
                                        "messageHeadline": "Initial commit",
                                        "committedDate": "2025-01-01T00:00:00Z",
                                        "author": {"name": "test_user"}
                                    }
                                ]
                            }
                        }
                    },
                    "openPRs": {"nodes": []},
                    "mergedPRs": {"nodes": []}
                }
            }
        }
        commits, open_prs, merged_prs = get_bulk_data("fake_token", ["owner/repo1"])
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0]["repo"], "owner/repo1")
        self.assertEqual(commits[0]["message"], "Initial commit")

    @patch('github_service_graphql.requests.post')
    def test_run_graphql_query_with_variables(self, mock_post):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"data": "test"}
        mock_post.return_value = mock_response

        variables = {"limit": 10}
        response = _run_graphql_query("fake_token", "query", variables)
        
        self.assertEqual(response, {"data": "test"})
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]['json']['variables'], variables)

    @patch('github_service_graphql._run_graphql_query')
    def test_get_all_accessible_repo_names_with_specific_orgs(self, mock_run_query):
        mock_run_query.side_effect = [
            # Viewer repos
            {
                "data": {
                    "viewer": {
                        "repositories": {
                            "nodes": [{"nameWithOwner": "owner/repo1", "pushedAt": "2025-01-01T00:00:00Z"}],
                            "pageInfo": {"hasNextPage": False, "endCursor": None}
                        }
                    }
                }
            },
            # Specific org repos
            {
                "data": {
                    "organization": {
                        "repositories": {
                            "nodes": [{"nameWithOwner": "my-org/repo2", "pushedAt": "2025-01-02T00:00:00Z"}],
                            "pageInfo": {"hasNextPage": False, "endCursor": None}
                        }
                    }
                }
            }
        ]
        
        repos = get_all_accessible_repo_names("fake_token", specific_org_logins=["my-org"])
        self.assertIn("owner/repo1", repos)
        self.assertIn("my-org/repo2", repos)
        self.assertEqual(len(repos), 2)

    @patch('github_service_graphql._run_graphql_query')
    def test_get_all_accessible_repo_names_empty_specific_orgs(self, mock_run_query):
        mock_run_query.return_value = {
            "data": {
                "viewer": {
                    "repositories": {
                        "nodes": [{"nameWithOwner": "owner/repo1", "pushedAt": "2025-01-01T00:00:00Z"}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None}
                    }
                }
            }
        }
        
        # Test with empty list (should not fetch org repos)
        repos = get_all_accessible_repo_names("fake_token", specific_org_logins=[])
        self.assertIn("owner/repo1", repos)
        self.assertEqual(len(repos), 1)
        # Should only call once for viewer repos, not for orgs
        self.assertEqual(mock_run_query.call_count, 1)

    def test_get_bulk_data_empty_repo_list(self):
        commits, open_prs, merged_prs = get_bulk_data("fake_token", [])
        self.assertEqual(commits, [])
        self.assertEqual(open_prs, [])
        self.assertEqual(merged_prs, [])

    @patch('github_service_graphql._run_graphql_query')
    def test_get_bulk_data_null_repo(self, mock_run_query):
        mock_run_query.return_value = {
            "data": {
                "repo0": None  # Simulate a null repo (access denied or doesn't exist)
            }
        }
        
        commits, open_prs, merged_prs = get_bulk_data("fake_token", ["owner/repo1"])
        self.assertEqual(commits, [])
        self.assertEqual(open_prs, [])
        self.assertEqual(merged_prs, [])

    @patch('github_service_graphql._run_graphql_query')
    def test_get_bulk_data_author_null(self, mock_run_query):
        mock_run_query.return_value = {
            "data": {
                "repo0": {
                    "nameWithOwner": "owner/repo1",
                    "url": "https://github.com/owner/repo1",
                    "defaultBranchRef": {
                        "name": "main",
                        "target": {
                            "history": {
                                "nodes": [
                                    {
                                        "oid": "1234567",
                                        "url": "https://github.com/owner/repo1/commit/1234567",
                                        "messageHeadline": "Commit with null author",
                                        "committedDate": "2025-01-01T00:00:00Z",
                                        "author": None  # Null author case
                                    }
                                ]
                            }
                        }
                    },
                    "openPRs": {
                        "nodes": [
                            {
                                "number": 1,
                                "title": "PR with null author",
                                "author": None,  # Null author case
                                "createdAt": "2025-01-01T00:00:00Z",
                                "url": "https://github.com/owner/repo1/pull/1"
                            }
                        ]
                    },
                    "mergedPRs": {
                        "nodes": [
                            {
                                "number": 2,
                                "title": "Merged PR with null author",
                                "author": None,  # Null author case
                                "mergedAt": "2025-01-01T00:00:00Z",
                                "url": "https://github.com/owner/repo1/pull/2"
                            }
                        ]
                    }
                }
            }
        }
        
        commits, open_prs, merged_prs = get_bulk_data("fake_token", ["owner/repo1"])
        
        # Verify all items handle null authors correctly
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0]["author"], "n/a")
        
        self.assertEqual(len(open_prs), 1)
        self.assertEqual(open_prs[0]["author"], "n/a")
        
        self.assertEqual(len(merged_prs), 1)
        self.assertEqual(merged_prs[0]["author"], "n/a")

if __name__ == '__main__':
    unittest.main()
