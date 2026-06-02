#!/usr/bin/env bash
# validate_gcp_trace_gaps.sh
# Final live UI validation for Recipe 06

set -euo pipefail

FRONTEND_URL="${FRONTEND_URL:-https://agent-frontend-w65nrxwkiq-uc.a.run.app/}"
LANGFUSE_URL="${LANGFUSE_HOST:-https://cloud.langfuse.com}"

echo "=== Recipe 06 — Live UI Validation ==="
echo ""
echo "Frontend : $FRONTEND_URL"
echo "Langfuse : $LANGFUSE_URL"
echo ""

echo "PART 1 — G9 Shell Error Validation"
echo "-----------------------------------"
echo ""
echo "Prompt to submit in the Frontend chat:"
echo ""
echo '  Please list the contents of the /nonexistent_directory_abc123 directory.'
echo ""
echo "Langfuse checklist:"
echo '  [ ] G9.1  tool.called event present for the shell command'
echo '  [ ] G9.2  error.occurred event present with level ERROR'
echo '  [ ] G9.3  task.completed present'
echo '  [ ] G9.4  error_type visible or agent recovered cleanly'
echo ""
echo 'Pass criteria: The error must NOT be silent. backend ok=False must surface in Langfuse.'
echo ""

echo "PART 2 — G5/G6 Loop Cap + goal_met=false"
echo "-----------------------------------------"
echo ""
echo "Prompt to submit in the Frontend chat:"
echo ""
echo '  Search the web for the exact phrase xyzq123impossiblephrase987 and retry repeatedly until you find exactly 50 results.'
echo ""
echo "Langfuse checklist:"
echo '  [ ] G5.1  Finite number of steps - stopped early via no_progress_repeat_threshold'
echo '  [ ] G6.1  task.completed details open'
echo '  [ ] G6.2  goal_met == false'
echo '  [ ] G6.3  outcome == partial or downgraded from success'
echo '  [ ] G6.4  termination_reason == no_progress'
echo ""
echo 'Pass criteria: Agent halted gracefully and correctly reported that the goal was not met.'
echo ""

echo "Opening tabs..."
if command -v open >/dev/null 2>&1; then
  open "$FRONTEND_URL" || true
  open "$LANGFUSE_URL" || true
else
  echo "Open these URLs manually:"
  echo "  $FRONTEND_URL"
  echo "  $LANGFUSE_URL"
fi

echo ""
echo "When both parts are complete, update the sign-off table in:"
echo "  docs/recipes/governance/06_gcp_trace_gap_validation_walkthrough.md"
echo ""
echo "All negative-path synthetic validation G4/G7/G8 already passed 30/30."
