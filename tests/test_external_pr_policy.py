import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "reject-external-prs.yml"


class ExternalPullRequestPolicyTests(unittest.TestCase):
    def setUp(self):
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_uses_target_event_without_checking_out_contributor_code(self):
        self.assertIn("pull_request_target:", self.workflow)
        self.assertNotIn("actions/checkout", self.workflow)

    def test_author_association_is_read_from_github_api(self):
        self.assertIn('gh api "repos/$REPOSITORY/pulls/$PR_NUMBER"', self.workflow)
        self.assertIn("--jq .author_association", self.workflow)
        self.assertIn("OWNER|MEMBER|COLLABORATOR", self.workflow)

    def test_unauthorized_pull_requests_are_closed_and_fail(self):
        self.assertIn('gh pr close "$PR_NUMBER"', self.workflow)
        self.assertIn("exit 1", self.workflow)

    def test_permissions_are_minimal_for_closing_pull_requests(self):
        self.assertIn("contents: read", self.workflow)
        self.assertIn("pull-requests: write", self.workflow)
        self.assertNotIn("contents: write", self.workflow)


if __name__ == "__main__":
    unittest.main()
