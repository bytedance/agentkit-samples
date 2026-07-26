#!/bin/sh
set -eu

usage() {
  cat <<'EOF'
Usage:
  ./scripts/install_codex_skill.sh
  ./scripts/install_codex_skill.sh --update

The default command installs the repository's AgentKit demo Skill without
overwriting an existing user copy. Use --update after reviewing a newer
repository version; the previous copy is retained as a timestamped backup.
EOF
}

mode="${1:-install}"
case "${mode}" in
  install)
    ;;
  --update)
    mode="update"
    ;;
  -h|--help)
    usage
    exit 0
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
project_dir="$(CDPATH= cd -- "${script_dir}/.." && pwd)"
source_dir="${project_dir}/.agents/skills/agentkit-hybrid-cloud-demo"
codex_root="${CODEX_HOME:-${HOME}/.codex}"
skills_dir="${codex_root}/skills"
destination="${skills_dir}/agentkit-hybrid-cloud-demo"
backup_dir="${codex_root}/skill-backups"

if [ ! -f "${source_dir}/SKILL.md" ]; then
  echo "Error: project Skill not found: ${source_dir}/SKILL.md" >&2
  echo "Run this script from a complete hybrid_cloud_customer_service checkout." >&2
  exit 1
fi

mkdir -p "${skills_dir}"

if [ ! -e "${destination}" ]; then
  cp -R "${source_dir}" "${destination}"
  echo "Installed agentkit-hybrid-cloud-demo to ${destination}"
  echo "Start a new Codex task before using the route-map Prompt."
  exit 0
fi

if diff -qr "${source_dir}" "${destination}" >/dev/null 2>&1; then
  echo "agentkit-hybrid-cloud-demo is already up to date: ${destination}"
  echo "Start a new Codex task if the current task was opened before installation."
  exit 0
fi

if [ "${mode}" != "update" ]; then
  echo "A different agentkit-hybrid-cloud-demo is already installed: ${destination}" >&2
  echo "Review the repository Skill, then run ./scripts/install_codex_skill.sh --update." >&2
  exit 2
fi

mkdir -p "${backup_dir}"
backup="${backup_dir}/agentkit-hybrid-cloud-demo.$(date +%Y%m%d%H%M%S)"
mv "${destination}" "${backup}"
if ! cp -R "${source_dir}" "${destination}"; then
  mv "${backup}" "${destination}"
  echo "Error: update failed; the previous Skill was restored." >&2
  exit 1
fi

echo "Updated agentkit-hybrid-cloud-demo: ${destination}"
echo "Previous copy retained at: ${backup}"
echo "Start a new Codex task before using the route-map Prompt."
