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

    def test_only_authorized_associations_are_accepted(self):
        self.assertIn('["OWNER","MEMBER","COLLABORATOR"]', self.workflow)
        self.assertIn("author_association", self.workflow)

    def test_permissions_are_minimal_for_closing_pull_requests(self):
        self.assertIn("contents: read", self.workflow)
        self.assertIn("pull-requests: write", self.workflow)
        self.assertNotIn("contents: write", self.workflow)


if __name__ == "__main__":
    unittest.main()
