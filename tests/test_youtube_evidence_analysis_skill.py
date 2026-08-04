from pathlib import Path

TEXT = (Path(__file__).parents[1] / "skills/youtube-evidence-analysis/SKILL.md").read_text()


def test_required_policy_and_composition_are_explicit():
    for phrase in ("source hierarchy", "browser transcript panel", "untrusted data", "factual claims", "primary-source", "timestamp", "accessibility transcript", "video-frames", "verified-research", "Korean report", "Completion requires", "Exclusions"):
        assert phrase.lower() in TEXT.lower()


def test_hard_exclusions_and_no_fabrication():
    for phrase in ("Do not download media", "bypass login", "scrape captions", "biometric", "use credentials", "arbitrary commands", "Do not fabricate"):
        assert phrase in TEXT
