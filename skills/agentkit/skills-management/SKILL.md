---
name: skills-management
description: Manage AgentKit skills, SkillHub/skillhub, skill centers, and skill spaces. Use this skill whenever the user has a management intent for AgentKit skills, skill中心, skill 空间, skill space, or skill hub, including listing, inspecting, downloading, fetching, uploading, publishing, registering, or syncing skills between local directories and remote skill spaces.
license: Complete terms in LICENSE.txt
---

# AgentKit Skills Management

Use this skill to manage AgentKit skills between local directories and remote AgentKit skill spaces.

The bundled scripts support three workflows:

- List skills in one or more skill spaces.
- Download skills from a skill space to a local directory.
- Register a local skill directory to one or more skill spaces.

## Usage

List skills:

```bash
python3 scripts/skill_list.py
```

List skills as JSON:

```bash
python3 scripts/skill_list.py --json
```

Download all skills to `./my-skills`:

```bash
python3 scripts/skills_download.py ./my-skills
```

Download only `skill-a` and `skill-b`:

```bash
python3 scripts/skills_download.py ./my-skills --skills skill-a skill-b
```

Register a local skill:

```bash
python3 scripts/skills_register.py ./my-new-skill
```

## Arguments

### `skill_list.py`

- `--space-id`: Optional comma-separated skill space IDs. Defaults to `SKILL_SPACE_ID`.
- `--json`: Print machine-readable JSON output.

### `skills_download.py`

- `<download_path>`: The local directory path where the skills will be saved.
- `--skills`: Optional space-separated skill names to download. If omitted, all skills in the configured skill spaces are downloaded.

### `skills_register.py`

- `<path_to_skill_directory>`: Path to a local directory containing `SKILL.md`.
- `--space-id`: Optional comma-separated skill space IDs. Defaults to `SKILL_SPACE_ID`.

## Requirements

- `veadk` Python package installed.
- For registration, `python-frontmatter` installed.
- Environment variables:
  - `SKILL_SPACE_ID` required unless `--space-id` is provided.
  - `VOLCENGINE_ACCESS_KEY` and `VOLCENGINE_SECRET_KEY`, unless VEFaaS IAM credentials are available.
  - `AGENTKIT_TOOL_REGION` optional, defaults to `cn-beijing`.
  - `AGENTKIT_TOOL_SERVICE_CODE` optional, defaults to `agentkit`.
  - `AGENTKIT_SKILL_HOST` optional, defaults to `open.volcengineapi.com`.

The scripts also load `/root/.skills_env` when it exists, so persisted skill-space configuration can be reused in sandbox environments.

## Error Handling

- IF a script raises `VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY are not set in environment variables.`, inform the user that credentials are required unless VEFaaS IAM credentials are available. Write the values to the environment variable file in the workspace if the user provides them, make the environment effective, and retry the failed task.
- IF a script raises `SKILL_SPACE_ID environment variable is not set`, inform the user that they need to provide `SKILL_SPACE_ID` or pass `--space-id`. Write it to the environment variable file in the workspace if the user provides it, make the environment effective, and retry the failed task.
