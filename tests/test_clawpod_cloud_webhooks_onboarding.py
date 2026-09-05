import json
from pathlib import Path


def test_webhooks_skill_requires_immediate_post_install_onboarding_handoff():
    skill = Path("skills/clawpod-cloud-webhooks/SKILL.md").read_text()
    for phrase in (
        "Immediately after installation",
        "installation succeeded but connection has not started",
        "ClawPod Cloud TA account or Webhook Manager permission",
        "user's sign-in/MFA actions",
        "protected credential/session handling and revocation",
        "start onboarding immediately by asking in that same message",
        "Omitting this handoff is an incomplete installation",
        "ClawPod Cloud base URL and the authorized account identifier",
        "never ask for or accept a plaintext password/token in chat",
        "Search existing secret pointers first",
        "Never ask the user to configure environment variables or run commands",
        "exec.useSecrets",
    ):
        assert phrase in skill


def test_webhooks_tls_output_schema_uses_gateway_supported_keywords():
    manifest = json.loads(Path("harnesses/clawpod-cloud-webhooks/harness.json").read_text())
    for command_name, command in manifest["commands"].items():
        tls_mode = command["outputSchema"]["properties"]["tls_verification_mode"]
        assert tls_mode == {"type": "string"}, command_name
