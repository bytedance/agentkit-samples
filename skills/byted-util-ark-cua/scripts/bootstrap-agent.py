#!/usr/bin/env python3
"""Install or update credential-agent from a signed ai-workflow release."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any


DEFAULT_ARTIFACT_BASE = "https://al-artifacts-bj.tos-cn-beijing.volces.com"
DEFAULT_PUBLIC_KEY = "FYJ6pbAiSmmE6UnVv4LtKhQaJ3cxJgxyQrZZSAHsosc="
MAX_METADATA_BYTES = 1 << 20
MAX_PACKAGE_BYTES = 512 << 20
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

# RFC 8032 verification arithmetic. Keeping this standard-library-only avoids
# trusting an unverified third-party package during the first bootstrap.
Q = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493
D = (-121665 * pow(121666, Q - 2, Q)) % Q
I = pow(2, (Q - 1) // 4, Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(D * y * y + 1, Q - 2, Q) % Q
    x = pow(xx, (Q + 3) // 8, Q)
    if (x * x - xx) % Q != 0:
        x = x * I % Q
    if (x * x - xx) % Q != 0:
        raise ValueError("invalid Ed25519 point")
    if x & 1:
        x = Q - x
    return x


B_Y = 4 * pow(5, Q - 2, Q) % Q
B = (_xrecover(B_Y), B_Y)


def _edwards(p: tuple[int, int], q: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = p
    x2, y2 = q
    product = D * x1 * x2 * y1 * y2
    x3 = (x1 * y2 + x2 * y1) * pow(1 + product, Q - 2, Q) % Q
    y3 = (y1 * y2 + x1 * x2) * pow(1 - product, Q - 2, Q) % Q
    return x3, y3


def _scalarmult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = (0, 1)
    addend = point
    while scalar:
        if scalar & 1:
            result = _edwards(result, addend)
        addend = _edwards(addend, addend)
        scalar >>= 1
    return result


def _decodepoint(raw: bytes) -> tuple[int, int]:
    if len(raw) != 32:
        raise ValueError("invalid Ed25519 point length")
    encoded = int.from_bytes(raw, "little")
    y = encoded & ((1 << 255) - 1)
    sign = encoded >> 255
    if y >= Q:
        raise ValueError("non-canonical Ed25519 point")
    x = _xrecover(y)
    if (x & 1) != sign:
        x = Q - x
    if x == 0 and sign:
        raise ValueError("non-canonical Ed25519 point sign")
    if (-x * x + y * y - 1 - D * x * x * y * y) % Q != 0:
        raise ValueError("Ed25519 point is not on curve")
    return x, y


def verify_ed25519(public_key: bytes, message: bytes, signature: bytes) -> bool:
    if len(public_key) != 32 or len(signature) != 64:
        return False
    try:
        r_encoded = signature[:32]
        scalar = int.from_bytes(signature[32:], "little")
        if scalar >= L:
            return False
        public_point = _decodepoint(public_key)
        r_point = _decodepoint(r_encoded)
        challenge = int.from_bytes(
            hashlib.sha512(r_encoded + public_key + message).digest(), "little"
        ) % L
        return _scalarmult(B, scalar) == _edwards(
            r_point, _scalarmult(public_point, challenge)
        )
    except (ValueError, ZeroDivisionError):
        return False


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


OPENER = urllib.request.build_opener(NoRedirect())


def normalize_base_url(raw: str) -> str:
    parsed = urllib.parse.urlsplit(raw.strip())
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("artifact base URL must be an HTTPS origin without credentials, path, query, or fragment")
    return urllib.parse.urlunsplit(("https", parsed.netloc, "", "", ""))


def valid_object_key(value: Any) -> bool:
    if not isinstance(value, str) or not value or len(value) > 1024:
        return False
    if value.startswith("/") or value.endswith("/") or "\\" in value:
        return False
    parts = PurePosixPath(value).parts
    return bool(parts) and all(
        part not in (".", "..") and SAFE_COMPONENT.fullmatch(part) for part in parts
    )


def object_url(base: str, key: str) -> str:
    if not valid_object_key(key):
        raise ValueError("artifact object key is unsafe")
    quoted = "/".join(urllib.parse.quote(part, safe="") for part in key.split("/"))
    return f"{base}/{quoted}"


def request(url: str, headers: dict[str, str] | None = None) -> Any:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username is not None:
        raise ValueError("download URL must use HTTPS without embedded credentials")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "byted-util-ark-cua-credential-bootstrap/1", **(headers or {})},
    )
    return OPENER.open(req, timeout=30)


def fetch_bytes(url: str, limit: int) -> bytes:
    with request(url) as response:
        if getattr(response, "status", 200) != 200:
            raise RuntimeError(f"metadata download failed with HTTP {response.status}")
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("metadata exceeds the allowed size")
    return raw


def decode_b64(value: str, expected_length: int, label: str) -> bytes:
    compact = "".join(value.split())
    padded = compact + "=" * ((4 - len(compact) % 4) % 4)
    for altchars in (None, b"-_"):
        try:
            decoded = base64.b64decode(padded, altchars=altchars, validate=True)
        except (ValueError, binascii.Error):
            continue
        if len(decoded) == expected_length:
            return decoded
    raise ValueError(f"{label} is not valid base64 or has the wrong length")


def load_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def detect_os() -> str:
    value = platform.system().lower()
    return {"darwin": "darwin", "linux": "linux", "windows": "windows"}.get(value, value)


def detect_arch() -> str:
    system = platform.system().lower()
    value = platform.machine().lower()
    if system == "darwin":
        try:
            apple_silicon = subprocess.run(
                ["/usr/sbin/sysctl", "-n", "hw.optional.arm64"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            ).stdout.strip()
            if apple_silicon == "1":
                return "arm64"
        except (OSError, subprocess.SubprocessError):
            pass
    if system in ("darwin", "linux"):
        try:
            native = subprocess.run(
                ["uname", "-m"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            ).stdout.strip().lower()
            if native:
                value = native
        except (OSError, subprocess.SubprocessError):
            pass
    elif system == "windows":
        value = os.environ.get("PROCESSOR_ARCHITEW6432", os.environ.get("PROCESSOR_ARCHITECTURE", value)).lower()
    mapping = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    return mapping.get(value, value)


def default_install_path(goos: str) -> Path:
    if goos == "windows":
        root = os.environ.get("LOCALAPPDATA")
        if not root:
            raise ValueError("LOCALAPPDATA is not set")
        return Path(root) / "AL" / "CredentialAgent" / "credential-agent.exe"
    return Path.home() / ".local" / "bin" / "credential-agent"


def select_release(manifest: dict[str, Any], goos: str, arch: str) -> dict[str, Any]:
    if (
        manifest.get("schemaVersion") != 1
        or manifest.get("artifactName") != "credential-agent"
        or not isinstance(manifest.get("version"), str)
        or not SAFE_COMPONENT.fullmatch(manifest["version"])
    ):
        raise ValueError("release manifest identity is invalid")
    files = manifest.get("files")
    if not isinstance(files, list) or not (1 <= len(files) <= 64):
        raise ValueError("release manifest files are invalid")
    wanted = f"{goos}/{arch}"
    matches = [item for item in files if isinstance(item, dict) and item.get("platform") == wanted]
    if len(matches) != 1:
        raise ValueError(f"release manifest does not contain exactly one {wanted} artifact")
    selected = matches[0]
    size = selected.get("size")
    digest = selected.get("sha256")
    key = selected.get("key")
    if not isinstance(size, int) or not (0 < size <= MAX_PACKAGE_BYTES):
        raise ValueError("release artifact size is invalid")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise ValueError("release artifact SHA-256 is invalid")
    if not valid_object_key(key):
        raise ValueError("release artifact key is unsafe")
    return {
        "version": manifest["version"],
        "size": size,
        "sha256": digest.lower(),
        "key": key,
    }


def download_artifact(url: str, destination: Path, expected_size: int, expected_digest: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    for attempt in range(1, 4):
        existing = part.stat().st_size if part.exists() else 0
        if existing > expected_size:
            part.unlink()
            existing = 0
        headers = {"Range": f"bytes={existing}-"} if existing else {}
        try:
            with request(url, headers) as response:
                status = getattr(response, "status", 200)
                if existing and status != 206:
                    part.unlink(missing_ok=True)
                    existing = 0
                    raise RuntimeError("artifact server did not honor range request")
                if not existing and status != 200:
                    raise RuntimeError(f"artifact download failed with HTTP {status}")
                mode = "ab" if existing else "wb"
                downloaded = existing
                with part.open(mode) as output:
                    while True:
                        chunk = response.read(256 << 10)
                        if not chunk:
                            break
                        downloaded += len(chunk)
                        if downloaded > expected_size:
                            raise ValueError("artifact exceeds signed size")
                        output.write(chunk)
                        percent = int(downloaded * 100 / expected_size)
                        print(
                            f"\rDownloading Credential Agent: {percent:3d}% "
                            f"{downloaded / (1 << 20):.1f}/{expected_size / (1 << 20):.1f} MiB",
                            end="",
                            flush=True,
                        )
            print()
            break
        except (OSError, urllib.error.URLError, RuntimeError) as exc:
            print()
            if attempt == 3:
                raise RuntimeError(f"artifact download failed after {attempt} attempts: {exc}") from exc
            print(f"Download interrupted; retrying attempt {attempt + 1}/3...", file=sys.stderr)
            time.sleep(attempt * 2)
    if part.stat().st_size != expected_size:
        raise ValueError("downloaded artifact length does not match signed manifest")
    digest = hashlib.sha256()
    with part.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_digest:
        raise ValueError("downloaded artifact SHA-256 does not match signed manifest")
    os.replace(part, destination)


def invoke_existing_update(
    agent: Path,
    manifest_url: str,
    signature_url: str,
    public_key: str,
    artifact_base: str,
) -> bool:
    if not agent.is_file():
        return False
    command = [
        str(agent),
        "update",
        "--manifest",
        manifest_url,
        "--signature",
        signature_url,
        "--public-key",
        public_key,
        "--artifact-base-url",
        artifact_base,
    ]
    print(f"Using the installed Agent's atomic updater: {agent}")
    try:
        completed = subprocess.run(command, check=False)
    except OSError as exc:
        print(f"Installed Agent could not start: {exc}", file=sys.stderr)
        return False
    return completed.returncode == 0


def direct_install(downloaded: Path, install_path: Path, goos: str) -> None:
    install_path.parent.mkdir(parents=True, exist_ok=True)
    if goos == "windows" and install_path.exists():
        raise RuntimeError(
            "the existing Windows Agent updater failed; refusing to overwrite a possibly running executable. "
            "Close Chrome and repair/update the installed Agent before retrying"
        )
    mode = downloaded.stat().st_mode
    downloaded.chmod(mode | stat.S_IXUSR)
    os.replace(downloaded, install_path)
    if goos != "windows":
        install_path.chmod(0o700)


def run_self_test() -> None:
    public_key = bytes.fromhex(
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
    )
    signature = bytes.fromhex(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    )
    if not verify_ed25519(public_key, b"", signature):
        raise RuntimeError("RFC 8032 Ed25519 verification vector failed")
    if verify_ed25519(public_key, b"tampered", signature):
        raise RuntimeError("tampered Ed25519 verification unexpectedly succeeded")
    print("bootstrap-agent self-test passed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-base-url", default=DEFAULT_ARTIFACT_BASE)
    parser.add_argument("--public-key", default=DEFAULT_PUBLIC_KEY)
    parser.add_argument("--expected-os", choices=("darwin", "linux", "windows"))
    parser.add_argument("--expected-arch", choices=("amd64", "arm64"))
    parser.add_argument("--install-path")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return 0
    goos = detect_os()
    arch = detect_arch()
    if args.expected_os and goos != args.expected_os:
        raise ValueError(f"wrapper expected {args.expected_os}, detected {goos}")
    if args.expected_arch and arch != args.expected_arch:
        raise ValueError(f"wrapper expected {args.expected_arch}, detected {arch}")
    if goos not in ("darwin", "linux", "windows") or arch not in ("amd64", "arm64"):
        raise ValueError(f"unsupported platform {goos}/{arch}")
    base = normalize_base_url(args.artifact_base_url)
    public_key = decode_b64(args.public_key, 32, "release public key")
    latest_url = object_url(base, "credential-agent/latest.json")
    latest_raw = fetch_bytes(latest_url, MAX_METADATA_BYTES)
    latest = load_json(latest_raw, "latest metadata")
    if latest.get("schemaVersion") != 1 or latest.get("artifactName") != "credential-agent":
        raise ValueError("latest metadata identity is invalid")
    manifest_key = latest.get("manifestKey")
    signature_key = latest.get("manifestSignatureKey")
    if not valid_object_key(manifest_key) or not valid_object_key(signature_key):
        raise ValueError("latest metadata contains unsafe object keys")
    manifest_url = object_url(base, manifest_key)
    signature_url = object_url(base, signature_key)
    manifest_raw = fetch_bytes(manifest_url, MAX_METADATA_BYTES)
    latest_digest = latest.get("manifestSHA256")
    if isinstance(latest_digest, str) and re.fullmatch(r"[0-9a-fA-F]{64}", latest_digest):
        if hashlib.sha256(manifest_raw).hexdigest() != latest_digest.lower():
            raise ValueError("manifest SHA-256 does not match latest metadata")
    signature_raw = fetch_bytes(signature_url, 4096)
    signature = decode_b64(signature_raw.decode("ascii"), 64, "manifest signature")
    if not verify_ed25519(public_key, manifest_raw, signature):
        raise ValueError("release manifest Ed25519 signature is invalid")
    manifest = load_json(manifest_raw, "release manifest")
    selected = select_release(manifest, goos, arch)
    install_path = Path(args.install_path).expanduser() if args.install_path else default_install_path(goos)
    install_path = install_path.resolve(strict=False)
    print(f"Verified release {selected['version']} for {goos}/{arch}")
    if args.verify_only:
        print(
            json.dumps(
                {
                    "ok": True,
                    "version": selected["version"],
                    "platform": f"{goos}/{arch}",
                    "size": selected["size"],
                    "sha256": selected["sha256"],
                    "object_key": selected["key"],
                },
                separators=(",", ":"),
            )
        )
        return 0
    if invoke_existing_update(install_path, manifest_url, signature_url, args.public_key, base):
        return 0
    with tempfile.TemporaryDirectory(prefix="al-credential-bootstrap-") as temporary:
        staged = Path(temporary) / ("credential-agent.exe" if goos == "windows" else "credential-agent")
        download_artifact(
            object_url(base, selected["key"]),
            staged,
            selected["size"],
            selected["sha256"],
        )
        direct_install(staged, install_path, goos)
    completed = subprocess.run([str(install_path), "help"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if completed.returncode != 0:
        raise RuntimeError("installed Agent failed its executable smoke test")
    print(f"Credential Agent installed and verified: {install_path}")
    print(f"SHA256: {selected['sha256']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("bootstrap cancelled", file=sys.stderr)
        raise SystemExit(10)
    except Exception as exc:  # noqa: BLE001 - CLI boundary returns a concise error.
        print(f"bootstrap failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
