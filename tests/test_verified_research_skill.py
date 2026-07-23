from pathlib import Path

TEXT=(Path(__file__).parents[1]/'skills/verified-research/SKILL.md').read_text()

def test_positive_research_triggers_are_declared():
 for phrase in ('factual research','source verification','fact checking','citations'):
  assert phrase in TEXT

def test_negative_triggers_are_declared():
 for phrase in ('casual brainstorming','pure editing','fiction','no research'):
  assert phrase in TEXT

def test_hard_no_fabrication_and_judgment_boundary():
 assert 'Hard no-fabrication gate' in TEXT
 assert 'does **not** decide whether claims are true' in TEXT
