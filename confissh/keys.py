"""Discover local SSH key files without storing their contents in application data."""
from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

MAX_KEY_BYTES = 1024 * 1024
PRIVATE_HEADERS = {
    "-----BEGIN OPENSSH PRIVATE KEY-----", "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN DSA PRIVATE KEY-----", "-----BEGIN EC PRIVATE KEY-----",
    "-----BEGIN PRIVATE KEY-----", "-----BEGIN ENCRYPTED PRIVATE KEY-----",
}
PUBLIC_HEADERS = {
    "-----BEGIN PUBLIC KEY-----", "-----BEGIN RSA PUBLIC KEY-----",
    "---- BEGIN SSH2 PUBLIC KEY ----",
}
NON_KEY_FILES = {"config", "authorized_keys", "authorized_keys2", "known_hosts", "known_hosts2"}


@dataclass(frozen=True)
class KeyFile:
    path: Path
    kind: str


def identity_path(value: str) -> Path | None:
    """Resolve literal IdentityFile values; leave host-dependent tokens unresolved."""
    try:
        parts = shlex.split(value)
        if len(parts) != 1 or parts[0].lower() == "none":
            return None
        value = parts[0]
        if any(token not in ("%", "d") for token in re.findall(r"%(.)?", value)):
            return None
        value = re.sub(r"%[%d]", lambda match: "%" if match[0] == "%%" else str(Path.home()), value)
        value = os.path.expandvars(value)
        if "${" in value:
            return None
        return Path(value).expanduser().absolute()
    except (ValueError, RuntimeError):
        return None


def quote_identity_path(filename: str) -> str:
    value = filename.replace("%", "%%")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def key_kind(header: str) -> str | None:
    if header in PRIVATE_HEADERS or header.startswith("PuTTY-User-Key-File-"):
        return "private"
    if header in PUBLIC_HEADERS or re.match(
        r"(?:ssh-(?:rsa|dss|ed25519)(?:-cert-v01@openssh\.com)?|"
        r"ecdsa-sha2-\S+|sk-\S+) [A-Za-z0-9+/]+={0,3}(?:\s|$)", header
    ):
        return "public"
    return None


def discover_keys(roots=None, identities=()):
    """Scan SSH folders and configured identities, returning paths/types and read errors."""
    roots = [Path.home() / ".ssh"] if roots is None else list(roots)
    candidates = set()
    errors = []
    for root in roots:
        root = Path(root).expanduser()
        if not root.exists():
            continue
        def walk_error(error):
            errors.append(str(error))
        for directory, _dirs, filenames in os.walk(root, followlinks=False, onerror=walk_error):
            candidates.update(Path(directory) / name for name in filenames
                              if name not in NON_KEY_FILES)
    for value in identities:
        path = identity_path(value)
        if path:
            candidates.update((path, Path(str(path) + ".pub")))
    found = []
    seen = set()
    for path in sorted(candidates, key=lambda item: str(item).casefold()):
        try:
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            with path.open("rb") as handle:
                header = handle.readline(8192).decode("ascii", errors="replace").strip()
            kind = key_kind(header)
            if kind:
                found.append(KeyFile(path.absolute(), kind))
        except OSError as error:
            errors.append(f"{path}: {error.strerror}")
    return found, errors


def read_key(path: Path) -> str:
    """Read on explicit copy only, rechecking type and bounding memory use."""
    if not path.is_file():
        raise ValueError("Key file is no longer available")
    with path.open("rb") as handle:
        raw = handle.read(MAX_KEY_BYTES + 1)
    if len(raw) > MAX_KEY_BYTES:
        raise ValueError("Key file is too large")
    content = raw.decode("utf-8")
    if not content or not key_kind(content.splitlines()[0].strip()):
        raise ValueError("File no longer contains a recognized key")
    return content
