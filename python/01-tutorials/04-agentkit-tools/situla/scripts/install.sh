#!/bin/sh
set -eu

default_download_base_url=https://public-reading.tos-cn-beijing.volces.com/agentkit/situla
download_base_url=${SITULA_DOWNLOAD_BASE_URL:-$default_download_base_url}
default_install_directory="$HOME/.local/bin"
install_directory=${SITULA_INSTALL_DIR:-$default_install_directory}
version=${SITULA_VERSION:-0.1.0}
version=${version#v}

fail() {
  echo "situla: $*" >&2
  exit 1
}

add_default_install_directory_to_path() {
  shell_name=${SHELL:-}
  shell_name=${shell_name##*/}
  case "$shell_name" in
    zsh) shell_profile="$HOME/.zshrc" ;;
    bash)
      if [ "$(uname -s)" = Darwin ]; then
        shell_profile="$HOME/.bash_profile"
      else
        shell_profile="$HOME/.bashrc"
      fi
      ;;
    *) shell_profile="" ;;
  esac

  if [ -z "$shell_profile" ]; then
    echo "Note: $install_directory is not currently in PATH."
    echo "Add this line to your shell profile:"
    echo '  export PATH="$HOME/.local/bin:$PATH"'
    return 1
  fi

  path_line='export PATH="$HOME/.local/bin:$PATH"'
  if ! grep -Fqx "$path_line" "$shell_profile" 2>/dev/null; then
    if ! printf '\n# Situla\n%s\n' "$path_line" >> "$shell_profile"; then
      echo "Warning: could not update $shell_profile."
      echo "Add this line manually:"
      echo "  $path_line"
      return 1
    fi
    echo "Added $install_directory to PATH in $shell_profile"
  else
    echo "$install_directory is already configured in $shell_profile"
  fi

  echo "Restart your shell, or run:"
  echo "  . \"$shell_profile\""
  return 0
}

case "$version" in
  ""|*[!0-9A-Za-z.+-]*) fail "invalid version: $version" ;;
esac

operating_system=$(uname -s)
machine=$(uname -m)

case "$operating_system" in
  Linux) platform=linux ;;
  Darwin) platform=darwin ;;
  *) fail "unsupported operating system: $operating_system" ;;
esac

case "$machine" in
  x86_64|amd64) architecture=x64 ;;
  arm64|aarch64) architecture=arm64 ;;
  *) fail "unsupported architecture: $machine" ;;
esac

artifact="situla-v${version}-${platform}-${architecture}"
artifact_url="${download_base_url%/}/${artifact}"
temporary_directory=$(mktemp -d "${TMPDIR:-/tmp}/situla-install.XXXXXX")
staged_install=""

cleanup() {
  if [ -n "$staged_install" ]; then
    rm -f "$staged_install"
  fi
  rm -rf "$temporary_directory"
}
trap cleanup EXIT HUP INT TERM

command -v curl >/dev/null 2>&1 || fail "curl is required"

echo "Downloading ${artifact_url}"
curl -fL --retry 3 --connect-timeout 15 --proto '=https' --proto-redir '=https' \
  -o "$temporary_directory/$artifact" "$artifact_url"
curl -fL --retry 3 --connect-timeout 15 --proto '=https' --proto-redir '=https' \
  -o "$temporary_directory/$artifact.sha256" "$artifact_url.sha256"

expected=$(awk 'NR == 1 && length($1) == 64 && $1 ~ /^[0-9A-Fa-f]+$/ { print tolower($1) }' "$temporary_directory/$artifact.sha256")
[ -n "$expected" ] || fail "invalid checksum file for $artifact"

if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$temporary_directory/$artifact" | awk '{ print tolower($1) }')
elif command -v shasum >/dev/null 2>&1; then
  actual=$(shasum -a 256 "$temporary_directory/$artifact" | awk '{ print tolower($1) }')
else
  fail "sha256sum or shasum is required to verify the download"
fi
[ "$actual" = "$expected" ] || fail "checksum verification failed for $artifact"
echo "Checksum verified"

mkdir -p "$install_directory"
staged_install="$install_directory/.situla-install.$$"
cp "$temporary_directory/$artifact" "$staged_install"
chmod 755 "$staged_install"
mv -f "$staged_install" "$install_directory/situla"
staged_install=""

installed_version=$("$install_directory/situla" --version) || fail "installed binary did not start"
[ "$installed_version" = "$version" ] || fail "installed version is $installed_version, expected $version"

echo "Installed Situla $installed_version to $install_directory/situla"

start_command="situla start"
case ":$PATH:" in
  *":$install_directory:"*) ;;
  *)
    case "${SITULA_NO_MODIFY_PATH:-}" in
      1|true|yes)
        echo "Note: $install_directory is not currently in PATH."
        echo "Add this line to your shell profile:"
        if [ "$install_directory" = "$default_install_directory" ]; then
          echo '  export PATH="$HOME/.local/bin:$PATH"'
        else
          echo "  export PATH=\"$install_directory:\$PATH\""
        fi
        start_command="$install_directory/situla start"
        ;;
      *)
        if [ "$install_directory" = "$default_install_directory" ]; then
          add_default_install_directory_to_path || start_command="$install_directory/situla start"
        else
          echo "Note: custom install directory $install_directory is not currently in PATH."
          echo "Add this line to your shell profile:"
          echo "  export PATH=\"$install_directory:\$PATH\""
          start_command="$install_directory/situla start"
        fi
        ;;
    esac
    ;;
esac

echo "Start Situla with: $start_command"
