from pathlib import Path


def test_install_handoff_is_agent_complete_and_minimizes_owner_intervention():
 skill=Path('skills/google-workspace/SKILL.md').read_text()
 runbook=Path('skills/google-workspace/references/onboarding.md').read_text()
 required=(
  'installed but not yet connected','Start Google Workspace authorization and durability setup now?',
  'Google Auth Platform → Audience','External, Testing','seven days','In production','Internal',
  'Google Auth Platform → Branding','Data Access','sensitive or restricted','scope justifications',
  'Google Admin console','API controls','wake-guard','Gmail, Calendar, and Drive smoke-test counts',
  'login/MFA','final legally meaningful','never expose Google\'s response body')
 for phrase in required: assert phrase in runbook
 assert 'agent-complete Google Console durability runbook' in skill
 assert 'do not claim API automation' in runbook


def test_runbook_preserves_harness_login_contract_and_workspace_max():
 runbook=Path('skills/google-workspace/references/onboarding.md').read_text()
 for phrase in ('`auth.login.start`','`auth.login.status`','`auth.login.finalize`','`workspace-max`','loopback-only managed-browser URL','Repeat authorization'):
  assert phrase in runbook


def test_audience_policy_and_durability_language_are_precise():
 runbook=Path('skills/google-workspace/references/onboarding.md').read_text()
 for phrase in (
  'auth.onboarding.decide','default to **Internal only when**','every intended user',
  'expire after **7 days (seven days) when any non-basic scope is requested; the expiration includes refresh tokens**',
  'limited pre-release state','published External state','restricted Gmail or Drive scopes may require',
  'configured Audience','membership and domain','actually granted scopes'):
  assert phrase in runbook
