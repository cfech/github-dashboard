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

if __name__ == '__main__':
    unittest.main()
