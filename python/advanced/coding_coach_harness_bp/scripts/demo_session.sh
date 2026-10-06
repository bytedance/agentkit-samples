#!/usr/bin/env bash
# Run a 3-turn training session against the deployed code-coach runtime.
# One AgentKit session = one training session: the agent remembers the exercise
# it assigned across invokes because the session id stays the same.
#
# Ported from https://github.com/windrichie/byteplus-agentkit-samples
# (use-cases/harness_code_coach/scripts/demo_session.sh) by Windrichie.
#
# Usage (from anywhere; the script cd's into the project directory so the
# standalone agentkit CLI picks up credentials from `.env`):
#   scripts/demo_session.sh                 # runtime "code-coach", fresh session id
#   RUNTIME=code-coach USER_ID=trainee-02 SESSION=my-session scripts/demo_session.sh
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

RUNTIME="${RUNTIME:-code-coach}"
USER_ID="${USER_ID:-trainee-01}"
SESSION="${SESSION:-sess-$(date +%s)}"
PROVIDER="${PROVIDER:-byteplus}"   # this copy of the sample targets BytePlus

say() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
turn() { agentkit --provider "$PROVIDER" harness invoke "$RUNTIME" "$1" --user-id "$USER_ID" --session-id "$SESSION"; }

say "Turn 1 — trainee asks for an exercise  (u=$USER_ID s=$SESSION)"
turn "Hi! I'd like a Python exercise, please."

say "Turn 2 — trainee submits a solution with a deliberate edge-case bug"
# Bug: no guard for "nothing parseable" — crashes with ZeroDivisionError on the
# all_bad and empty hidden tests. The coach must run_code it against the hidden
# tests and report the failures before scoring.
read -r -d '' SUBMISSION <<'PY' || true
Here is my solution:

```python
def clean_average(values: list[str]) -> float:
    total = 0.0
    count = 0
    for v in values:
        try:
            total += float(v)
            count += 1
        except ValueError:
            pass
    return round(total / count, 2)
```
PY
turn "$SUBMISSION"

say "Turn 3 — trainee asks for a hint (progressive hint policy)"
turn "Can I get a hint on what I'm missing?"

say "Done. Resume this session any time with: agentkit --provider $PROVIDER harness invoke $RUNTIME \"...\" --user-id $USER_ID --session-id $SESSION"
