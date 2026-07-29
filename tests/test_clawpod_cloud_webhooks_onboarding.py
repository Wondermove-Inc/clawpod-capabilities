from pathlib import Path


def test_webhooks_skill_requires_immediate_post_install_onboarding_handoff():
    skill = Path("skills/clawpod-cloud-webhooks/SKILL.md").read_text()
    for phrase in (
        "Immediately after installation",
        "installation succeeded but connection has not started",
        "ClawPod Cloud TA account or Webhook Manager permission",
        "user's sign-in/MFA actions",
        "protected credential/session handling and revocation",
        "ask whether to start onboarding now",
        "Omitting this handoff is an incomplete installation",
    ):
        assert phrase in skill
