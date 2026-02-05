---
name: skills-registration
description: Registers a local skill to the AgentKit platform by uploading it. Invoke when the user wants to publish, upload, or register a skill they have created.
license: Complete terms in LICENSE.txt
---

# AgentKit Skill Registration

This skill registers a local skill directory to the AgentKit platform. It zips the directory, uploads it to TOS, and calls the CreateSkill API.

## Usage

To register a skill, run the following command:

```bash
python3 scripts/skills_register.py <path_to_skill_directory>
```

Replace `<path_to_skill_directory>` with the path to the folder containing your `SKILL.md`.

## Requirements

- `veadk` python package installed.
- Environment variables:
  - `VOLCENGINE_ACCESS_KEY`
  - `VOLCENGINE_SECRET_KEY`
  - `SKILL_SPACE_ID` (required, comma-separated list of skill space IDs)
  - `AGENTKIT_TOOL_REGION` (optional, defaults to cn-beijing)

## Example

```bash
python3 scripts/skills_register.py ./my-new-skill
```
