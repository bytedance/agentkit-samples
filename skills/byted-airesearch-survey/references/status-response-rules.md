# Status Response Rules

Use this file after the backend has already returned a real status.

## General rule

Prefer backend `reply_markdown`. Add only minimal clarification when required to resolve an obvious conflict.

## WAITING_CONFIRM

- Show the plan card returned by the backend
- Keep the structure intact
- Invite the user to either revise the plan or confirm execution
- Do not compress a rich plan into a few vague bullets

## CONFIRMED

- State that the plan has been confirmed
- Tell the user how to start execution if execution has not started yet
- Do not regenerate a new plan

## AUDIENCE_RUNNING

- State that audience selection is in progress
- Mention that formal research starts automatically after audience preparation is ready
- Do not invent conclusions or optimization advice

## TASK_RUNNING

- State that formal research is running
- If available, keep the task link visible
- You may mention that long-running tasks can be monitored with scheduled follow-ups
- Do not return premature insights

## FINISHED

- Prefer a report-style answer
- Keep the final result link visible when available
- Start with the conclusion, then key findings, then next-step suggestions if supported
- Do not say only “completed” with no substance when a result summary exists

## FAILED

- State that execution failed
- Prefer the user-facing reason from backend data when available
- Offer retry, revise, or restart paths
- Do not pretend a result exists

## UNSUPPORTED_INDUSTRY

- State clearly that the current industry is not directly supported
- Show the supported industry range in user-facing language
- Invite the user to revise the request

## GENERATING

- State that the complete plan is still being generated
- Tell the user they can continue later in the same conversation with messages such as `查看进度` or `查看方案`
- Mention scheduled follow-up only when the host actually supports it, and never claim it has already been set up
- Do not fabricate an early draft if the backend has not returned one
