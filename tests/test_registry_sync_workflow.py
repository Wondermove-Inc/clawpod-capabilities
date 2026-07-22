from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "registry-sync.yml"


class RegistrySyncWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_uses_trusted_base_generator(self) -> None:
        self.assertIn("pull_request_target:", self.workflow)
        self.assertIn("ref: main", self.workflow)
        self.assertIn("trusted/scripts/sync_registry.py --root candidate", self.workflow)

    def test_candidate_checkout_has_no_persisted_credentials(self) -> None:
        self.assertGreaterEqual(self.workflow.count("persist-credentials: false"), 4)
        self.assertIn("ref: ${{ github.event.pull_request.head.sha }}", self.workflow)

    def test_candidate_validation_is_isolated_from_write_permissions(self) -> None:
        validation = self.workflow.split("  validate-candidate:", 1)[1].split("  registry-sync:", 1)[0]
        self.assertIn("contents: read", validation)
        self.assertNotIn("contents: write", validation)
        self.assertNotIn("statuses: write", validation)
        self.assertIn("Generate candidate Registry with trusted code", validation)
        self.assertIn("Run repository tests", (ROOT / ".github" / "workflows" / "validate.yml").read_text())

    def test_generated_commit_receives_required_actions_status(self) -> None:
        synchronization = self.workflow.split("  registry-sync:", 1)[1]
        self.assertIn("needs: validate-candidate", synchronization)
        self.assertIn("statuses: write", synchronization)
        self.assertIn('statuses/$generated_sha', synchronization)
        self.assertIn("context=validate", synchronization)

    def test_only_generated_registry_is_committed(self) -> None:
        self.assertIn("git -C candidate add registry/index.json", self.workflow)
        self.assertNotIn("git -C candidate add .", self.workflow)

    def test_rejects_unauthorized_or_fork_pull_requests(self) -> None:
        self.assertIn("--jq .user.login", self.workflow)
        self.assertIn('collaborators/$author/permission', self.workflow)
        self.assertIn("admin|maintain|write", self.workflow)
        self.assertIn('HEAD_REPOSITORY" != "$REPOSITORY', self.workflow)


if __name__ == "__main__":
    unittest.main()
