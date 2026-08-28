#!/usr/bin/env python3
from pathlib import Path
import re
import sys

# Resolve the default from this script, not the caller's working directory, so the
# documented repository-root gate is reproducible.
skill = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / 'SKILL.md'
text = skill.read_text(encoding='utf-8')
checks = {
    'track_a_direct_delegation_heading': r'Track A,\s+direct delegation',
    'track_a_three_criteria': r'single practitioner.*immediate.*read-only or has no material impact.*No plan review is needed',
    'ambiguity_fails_to_tasks': r'Ambiguity fails to Tasks-governed delegation',
    'track_b_tasks_governed_heading': r'Track B,\s+Tasks-governed delegation',
    'track_b_when_track_a_fails': r'Track A criteria do not all hold',
    'track_b_multi_step_or_multiple': r'multi-step.*more than one practitioner',
    'track_b_material_or_uncertain': r'material impact.*confidently classify',
    'tasks_practitioner_visible_sot': r'Tasks is the practitioner-visible system of record',
    'workboard_private_progress_only': r'Workboard is private scratch/progress tracking only',
    'leader_created_or_accepted_tasks': r'leader-created or leader-accepted Tasks',
    'forbid_workboard_delivery_sot': r'Do not use Workboard as practitioner-visible delivery SoT|Do not use Workboard `parents` for concurrent delegation',
    'record_practitioner_task_id': r'practitioner_task_id',
    'execution_task_proof_completion': r'proof.*completion|completion.*proof',
    'wake_followup_blocker': r'wake/follow-up|block.*owner/reason/next action',
    'validate_supplied_context_before_acting': r'validate only the supplied context required for the assignment.*Set or confirm the Task status',
    'pre_existing_modifications_preserved': r'Preserve pre-existing modifications|pre_existing_modified_files',
    'room_delivery_not_completion': r'Do not treat Room/chat delivery as Task completion',
    'no_secret_destructive_authority': r'secret|destructive|production|config',
    'pr_delivery_default': r'use branch, commit, and pull request submission by default',
    'closeout_gate_before_completion': r'run `scripts/task-closeout-gate\.py`.*proceed only on exit 0',
    'execution_context_defined_once': r'execution context defined in the leader procedure',
}
missing = [name for name, pattern in checks.items() if not re.search(pattern, text, re.I | re.S)]
if missing:
    print('FAIL missing checks: ' + ', '.join(missing))
    raise SystemExit(1)
print('PASS leader-workboard-delegation skill eval checks=' + str(len(checks)))
