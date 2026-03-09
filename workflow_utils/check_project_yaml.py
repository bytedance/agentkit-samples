# pip install python-frontmatter
import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

SAMPLE_TYPES = ["tutorial", "application"]

COMPONENT_OPTIONS = {
    "sandbox": ["aio_sandbox", "skills_sandbox"],
    "knowledgebase": ["vikingknowledge"],
    "memory": ["vikingmem", "mem0"],
    "mcp_toolset": ["mcptoolset"],
}


def check_name(metadata: dict[str, Any]):
    name = metadata.get("name")
    if not name:
        raise ValueError("name is required")

    if len(name) > 255:
        raise ValueError("name should be less than 255 characters")


def check_name_en(metadata: dict[str, Any]):
    name_en = metadata.get("name_en")
    if not name_en:
        raise ValueError("name_en is required")

    if len(name_en) > 255:
        raise ValueError("name_en should be less than 255 characters")


def check_description(metadata: dict[str, Any]):
    description = metadata.get("description")
    if not description:
        raise ValueError("description is required")

    if len(description) < 10 or len(description) > 60:
        raise ValueError("description should be between 10-60 characters")


def check_details(metadata: dict[str, Any]):
    details = metadata.get("details")
    if not details:
        raise ValueError("details is required")

    if len(details) < 10 or len(details) > 400:
        raise ValueError("details should be between 10-400 characters")


def check_tags(metadata: dict[str, Any]):
    tags: dict = metadata.get("tags", {})
    if not tags:
        raise ValueError("tags is required")

    assert tags.get("industry"), "industry tag is required"
    assert tags.get("from"), "from tag is required"
    assert tags.get("framework"), "framework tag is required"
    assert tags.get("language"), "language tag is required"

    tech: list = tags.get("tech", [])
    if len(tech) > 5:
        raise ValueError("tech should have 5 items at most")


def check_type(metadata: dict[str, Any]):
    type = metadata.get("type")
    if not type:
        raise ValueError("type is required")

    if type not in SAMPLE_TYPES:
        raise ValueError(f"type should be one of {SAMPLE_TYPES}")


def check_scenarios(metadata: dict[str, Any]):
    type = metadata.get("type")
    scenarios: list = metadata.get("scenarios", [])
    if not scenarios and type == "application":
        raise ValueError("scenarios is required when type is `application`")

    if len(scenarios) < 2 or len(scenarios) > 6:
        raise ValueError("scenarios should have 2-6 items")

    for scenario in scenarios:
        name = scenario.get("name")
        if not name:
            raise ValueError("scenario name is required")
        if len(name) < 2 or len(name) > 15:
            raise ValueError("scenario name should be between 2-15 characters")

        desc = scenario.get("desc")
        if not desc:
            raise ValueError("scenario desc is required")
        if len(desc) < 10 or len(desc) > 20:
            raise ValueError("scenario desc should be between 10-20 characters")


def check_prompts(metadata: dict[str, Any]):
    prompts: list = metadata.get("prompts", [])
    if not prompts:
        raise ValueError("prompts field is required")

    for prompt in prompts:
        text = prompt.get("text")
        if not text:
            raise ValueError("prompt text is required")

        resource_url = prompt.get("resource_url")
        if resource_url:
            assert resource_url.startswith("https://") or resource_url.startswith(
                "http://"
            ), "resource_url must start with `https://` or `http://`"


def check_models(metadata: dict[str, Any]):
    models: list = metadata.get("models", [])
    if not models:
        raise ValueError("models field is required")


def check_envs(metadata: dict[str, Any]):
    envs: list = metadata.get("envs", [])

    for env in envs:
        assert env.get("name"), "env name is required"
        assert env.get("key"), "env key is required"

        url = env.get("url")
        assert url, "env url is required"
        assert url.startswith("https://") or url.startswith("http://"), (
            "env url must start with `https://` or `http://`"
        )


def check_components(metadata: dict[str, Any]):
    components = metadata.get("components", [])

    for component in components:
        assert component.get("type"), "component type is required"
        assert component.get("product"), "component product is required"

        component_type = component["type"].lower()
        component_product = component["product"].lower()

        assert component_type in COMPONENT_OPTIONS, (
            f"component type should be one of {COMPONENT_OPTIONS.keys()}"
        )
        assert component_product in COMPONENT_OPTIONS[component_type], (
            f"component product should be one of {COMPONENT_OPTIONS[component_type]}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*")
    args = parser.parse_args(argv)

    if not args.files:
        return 0

    repo_root = Path(__file__).resolve().parent.parent
    use_cases_dir = repo_root / "python"

    diff_commands = [
        ["git", "diff", "--name-only", "--diff-filter=ACMRT"],
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRT"],
    ]

    changed_files: set[str] = set()
    for cmd in diff_commands:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
        changed_files.update(
            line.strip() for line in completed.stdout.splitlines() if line.strip()
        )

    failed = False

    for file_path in args.files:
        path = Path(file_path).resolve()
        try:
            rel = path.relative_to(repo_root)
        except ValueError:
            continue

        if path.name.lower() != "project.yaml":
            continue

        if use_cases_dir not in path.parents:
            continue

        if str(rel) not in changed_files:
            continue

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        try:
            check_name(data)
            check_name_en(data)
            check_description(data)
            check_details(data)
            check_tags(data)
            check_type(data)
            check_scenarios(data)
            check_prompts(data)
            check_models(data)
            check_envs(data)
            check_components(data)
        except ValueError as exc:
            sys.stderr.write(f"{rel}: {exc}\n")
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
