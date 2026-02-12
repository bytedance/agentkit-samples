---
name: skills-download
description: Downloads skills from a AgentKit skill space to the local machine. Invoke when the user wants to fetch, download, or retrieve skills from the platform.
license: Complete terms in LICENSE.txt
---

# AgentKit Skill Download

This skill downloads skills from a specified AgentKit skill space to a local directory. It handles downloading the skill package from TOS and extracting it.

## Usage

To download skills, run the following command:

```bash
python3 scripts/skills_download.py <download_path> [--skills <skill_name1> <skill_name2> ...]
```

### Arguments

- `<download_path>`: The local directory path where the skills will be saved.
- `--skills`: (Optional) A space-separated list of specific skill names to download. If omitted, all skills in the space will be downloaded.

## Requirements

- `veadk` python package installed.
- Environment variables:
  - `VOLCENGINE_ACCESS_KEY`
  - `VOLCENGINE_SECRET_KEY`
  - `SKILL_SPACE_ID` (required, comma-separated list of skill space IDs)
  - `AGENTKIT_TOOL_REGION` (optional, defaults to cn-beijing)

## Example

Download all skills to `./my-skills`:

```bash
python3 scripts/skills_download.py ./my-skills
```

Download only `skill-a` and `skill-b`:

```bash
python3 scripts/skills_download.py ./my-skills --skills skill-a skill-b
```
