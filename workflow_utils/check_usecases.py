import os
import subprocess
import sys
from pathlib import Path


def get_changed_files(base_sha: str, head_sha: str) -> list[str]:
    if not base_sha or not head_sha:
        return []
    try:
        output = subprocess.check_output(
            ["git", "diff", "--name-only", base_sha, head_sha],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.output)
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def main() -> None:
    base_sha = os.environ.get("BASE_SHA", "")
    head_sha = os.environ.get("HEAD_SHA", "")

    changed = get_changed_files(base_sha, head_sha)
    changed_use_cases = [p for p in changed if p.startswith("python")]

    if not changed_use_cases:
        print("No changes under python, skipping main.py checks.")
        return

    candidate_dirs: set[Path] = set()
    for rel_path in changed_use_cases:
        parts = Path(rel_path).parts
        if (
            len(parts) >= 3
            and parts[0] == "python"
            and parts[1] in ["02-use-cases", "01-use-cases"]
        ):
            candidate_dirs.add(Path(parts[0]) / parts[1] / parts[2])
    if not candidate_dirs:
        print("No top-level python/* directories detected, skipping main.py checks.")
        return

    print("Use-case directories to check:")
    for d in sorted(candidate_dirs):
        print(f"  - {d}")

    failed_dirs: list[Path] = []

    for d in sorted(candidate_dirs):
        # deploy_sh = d / "deploy.sh"
        # if deploy_sh.is_file():
        #     print(f"Found deploy.sh in {d}, running it")
        #     result = subprocess.run(["bash", "deploy.sh"], cwd=str(d))
        #     if result.returncode != 0:
        #         failed_dirs.append(d)
        #     continue

        agent_py = d / "agent.py"

        if not agent_py.is_file():
            print(f"No agent.py in {d}, skipping agentkit commands now.")
            continue

        agent_name = d.name
        print(f"Running 'agentkit config' in {d} for agent_name={agent_name}")
        config_cmd = [
            "agentkit",
            "config",
            "--agent_name",
            agent_name,
            "--entry_point",
            "agent.py",
            "--description",
            "a helpful agent",
            "--launch_type",
            "cloud",
            "--image_tag",
            "v1.0.0",
            "--cr_repo_name",
            agent_name,
            "--region",
            "cn-beijing",
        ]
        result = subprocess.run(config_cmd, cwd=str(d))
        if result.returncode != 0:
            failed_dirs.append(d)
            print(f"'agentkit config' failed in {d}, skipping launch.")
            continue

        command = os.environ.get("AGENTKIT_COMMAND", "launch")
        print(f"Running 'agentkit {command}' in {d}")
        launch_cmd = ["agentkit", command]
        result = subprocess.run(launch_cmd, cwd=str(d))
        if result.returncode != 0:
            failed_dirs.append(d)

    if failed_dirs:
        sys.stderr.write(
            "agentkit checks failed in directories: "
            + ", ".join(str(d) for d in failed_dirs)
            + "\n"
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
