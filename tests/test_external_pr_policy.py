import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"


def workflow_texts():
    for pattern in ("*.yml", "*.yaml"):
        for path in WORKFLOWS.glob(pattern):
            yield path, path.read_text(encoding="utf-8")


class ExternalPullRequestPolicyTests(unittest.TestCase):
    def test_no_workflow_can_write_to_or_close_pull_requests(self):
        close_patterns = (
            r"\bgh\s+pr\s+close\b",
            r"\bclose-pull-request\b",
            r"\bclose-pull\b",
            r"pulls?\.(?:update|close)\s*\(",
            r"state\s*[:=]\s*['\"]closed['\"]",
        )

        for path, workflow in workflow_texts():
            with self.subTest(workflow=path.name):
                self.assertNotRegex(workflow, r"pull-requests:\s*write")
                for pattern in close_patterns:
                    self.assertIsNone(
                        re.search(pattern, workflow, flags=re.IGNORECASE),
                        f"{path} contains pull-request auto-close behavior: {pattern}",
                    )

    def test_reject_external_pull_requests_workflow_is_removed(self):
        self.assertFalse((WORKFLOWS / "reject-external-prs.yml").exists())
        self.assertFalse((WORKFLOWS / "reject-external-prs.yaml").exists())

    def test_contribution_policy_welcomes_external_review(self):
        policy = " ".join(CONTRIBUTING.read_text(encoding="utf-8").split())
        self.assertIn("External contributions are welcome.", policy)
        self.assertIn(
            "Pull requests from contributors without repository access may remain open for review",
            policy,
        )

    def test_contribution_policy_reserves_merge_authority_for_admins(self):
        policy = " ".join(CONTRIBUTING.read_text(encoding="utf-8").split())
        self.assertIn("only repository administrators may merge pull requests", policy)
        self.assertIn("Merge authority is enforced through repository branch protection", policy)


if __name__ == "__main__":
    unittest.main()
