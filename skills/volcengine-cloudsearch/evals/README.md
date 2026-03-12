# Evaluations

These JSON files are lightweight, scenario-based checks aligned to `skill_authoring_best_practices.md`.

They are not executed automatically by this repo. They are intended as:
- A shared rubric for human review
- A prompt suite for manual testing across models

## Files

- `01-control-plane-provisioning.json`: discovery + provisioning workflow should run in the correct order and gate `create` on explicit confirmation.
- `02-data-plane-preflight-and-search.json`: requires `info` preflight, enforces single auth method, then runs a simple search.
- `03-destructive-confirmation.json`: destructive ops must be gated and require `--confirm`.
