"""Application metadata and recoverable, paired SSH/JSON writes."""
from __future__ import annotations

import copy
import fcntl
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from .core import ConfigError, HOST_RE, DISABLED_HOST_RE
from .i18n import _


DEFAULT_ENVIRONMENTS = (
    ("Production", "#dc5454"),
    ("Sandbox", "#d99a28"),
    ("Development", "#3b9b72"),
)


def new_id():
    return str(uuid4())


def read_bytes(path):
    return path.read_bytes() if path.exists() else None


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def encode(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


class MetadataStore:
    def __init__(self, path):
        self.path = Path(path)
        self.pending = self.path.with_suffix(".pending.json")
        self.backup_dir = self.path.parent / "backups"
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.lock():
            self.recover()
            self.baseline = read_bytes(self.path)
        try:
            self.data = json.loads(self.baseline) if self.baseline is not None else {
                "version": 1, "groups": {},
                "environments": {
                    new_id(): {"name": name, "color": color}
                    for name, color in DEFAULT_ENVIRONMENTS
                },
                "connections": {}
            }
            self.validate(self.data)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise ConfigError(_("The application data file is invalid and was not overwritten: {path}").format(path=self.path)) from exc

    def lock(self):
        return StoreLock(self.path.with_suffix(".lock"))

    @staticmethod
    def validate(data):
        if data["version"] != 1:
            raise ValueError("Unsupported version")
        for section in ("groups", "environments", "connections"):
            if not isinstance(data[section], dict):
                raise ValueError(section)
            for key in data[section]:
                UUID(key)
        for section in ("groups", "environments"):
            for value in data[section].values():
                if not isinstance(value["name"], str) or not value["name"].strip():
                    raise ValueError("Invalid name")
        for group in data["groups"].values():
            if not isinstance(group["order"], int):
                raise ValueError("Invalid order")
            if "color" in group and (not isinstance(group["color"], str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", group["color"])):
                raise ValueError("Invalid group color")
        for environment in data["environments"].values():
            if not isinstance(environment["color"], str):
                raise ValueError("Invalid color")
        for record in data["connections"].values():
            if not isinstance(record.get("favorite", False), bool) or not isinstance(record.get("note", ""), str):
                raise ValueError("Invalid connection metadata")
            if record.get("last_used") is not None and not isinstance(record["last_used"], (int, float)):
                raise ValueError("Invalid history")
            if record.get("group_id") is not None and record["group_id"] not in data["groups"]:
                raise ValueError("Missing group")
            if record.get("environment_id") is not None and record["environment_id"] not in data["environments"]:
                raise ValueError("Missing environment")
            if not isinstance(record.get("tags", []), list) or not all(isinstance(t, str) for t in record.get("tags", [])):
                raise ValueError("Invalid tags")

    def recover(self):
        if not self.pending.exists():
            return
        transaction = json.loads(self.pending.read_text())
        for item in transaction["files"]:
            current = read_bytes(Path(item["path"]))
            allowed = [value.encode() if value is not None else None
                       for value in (item["before"], item["after"])]
            if current not in allowed:
                raise ConfigError(_("An external change followed an interrupted save. Inspect .pending.json and the backups."))
        for item in reversed(transaction["files"]):
            path = Path(item["path"])
            if item["before"] is None:
                if path.exists():
                    path.unlink()
            else:
                atomic_write(path, item["before"].encode())
        self.pending.unlink()

    def list_backups(self):
        return sorted((path for path in self.backup_dir.glob("*.json")
                       if path.is_file() and not path.is_symlink()), reverse=True)

    def delete_backups(self, paths):
        """Delete only explicitly selected snapshots, never live data or a journal."""
        paths = list(dict.fromkeys(Path(path) for path in paths))
        with self.lock():
            if self.pending.exists():
                raise ConfigError(_("There is an interrupted save. Reopen the application before deleting backups."))
            allowed = set(self.list_backups())
            if any(path not in allowed for path in paths):
                raise ConfigError(_("The backup list changed or an invalid backup was selected. Refresh the list."))
            removed = 0
            try:
                for path in paths:
                    path.unlink()
                    removed += 1
            except OSError as exc:
                raise ConfigError(_("{count} backups were deleted; the rest could not be deleted: {error}").format(count=removed, error=exc)) from exc
        return removed

    def changed_on_disk(self):
        return read_bytes(self.path) != self.baseline

    def commit(self, data, documents):
        """Back up the complete workspace, then journal each changed file."""
        self.validate(data)
        with self.lock():
            if self.pending.exists():
                raise ConfigError(_("There is an interrupted operation. Reopen the application."))
            if self.changed_on_disk() or any(doc.changed_on_disk() for doc in documents.values()):
                raise ConfigError(_("Files changed outside the application. Reload with Ctrl+R."))
            files = []
            snapshot = {"version": 1, "metadata": self.data, "documents": {}}
            for path, doc in documents.items():
                before = doc.baseline.decode() if doc.baseline is not None else None
                after = doc.as_text()
                snapshot["documents"][str(path)] = before
                if before != after:
                    files.append({"path": str(path), "before": before, "after": after})
            after_metadata = encode(data)
            if after_metadata != self.baseline:
                files.append({"path": str(self.path), "before": self.baseline.decode() if self.baseline else None,
                              "after": after_metadata.decode()})
            if not files:
                return
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            atomic_write(self.backup_dir / f"{stamp}.json", encode(snapshot))
            atomic_write(self.pending, encode({"files": files}))
            try:
                for item in files:
                    atomic_write(Path(item["path"]), item["after"].encode())
                self.pending.unlink()
            except OSError as exc:
                self.recover()
                raise ConfigError(_("The save could not be completed; the previous state was restored: {error}").format(error=exc)) from exc
            self.baseline = read_bytes(self.path)
            self.data = copy.deepcopy(data)
            for path, doc in documents.items():
                doc.baseline = read_bytes(path)
                self.hydrate(doc)

    def hydrate(self, document):
        for entry in document.entries:
            record = self.data["connections"].get(entry.connection_id, {})
            entry.group_id = record.get("group_id")
            entry.group = self.data["groups"].get(entry.group_id, {}).get("name", "")
            entry.environment = record.get("environment_id") or ""
            entry.tags = list(record.get("tags", []))
            entry.note = record.get("note", "")

    @staticmethod
    def record(entry, previous=None):
        return {**(previous or {}), "group_id": entry.group_id,
                "environment_id": entry.environment or None,
                "tags": list(entry.tags), "note": entry.note,
                "favorite": (previous or {}).get("favorite", False)}

    def synchronize(self, documents):
        data = self.prepare(documents)
        self.commit(data, documents)
        for document in documents.values():
            self.hydrate(document)

    def prepare(self, documents):
        data = copy.deepcopy(self.data)
        seen = set()
        for document in documents.values():
            for entry in document.entries:
                old_id = entry.connection_id
                duplicate = old_id and old_id in seen
                if not old_id or duplicate:
                    entry.connection_id = new_id()
                seen.add(entry.connection_id)
                if entry.connection_id not in data["connections"]:
                    if duplicate and old_id in data["connections"]:
                        data["connections"][entry.connection_id] = copy.deepcopy(data["connections"][old_id])
                        data["connections"][entry.connection_id]["favorite"] = False
                        data["connections"][entry.connection_id].pop("last_used", None)
                    else:
                        data["connections"][entry.connection_id] = {
                            "group_id": None, "environment_id": None, "tags": [],
                            "note": "", "favorite": False}
            # Apply insertions backwards, without invalidating stored line offsets.
            for entry in reversed(document.entries):
                end = entry.start
                while end < len(document.lines) and not (HOST_RE.match(document.lines[end]) or DISABLED_HOST_RE.match(document.lines[end])):
                    end += 1
                document.lines[entry.start:end] = [f"# confissh-key: {entry.connection_id}"]
            document._parse()
        return data

    @staticmethod
    def restore_default_environments(data):
        """Merge defaults by name, preserving custom environments and IDs."""
        environments = data["environments"]
        by_name = {item["name"].casefold(): key for key, item in environments.items()}
        for name, color in DEFAULT_ENVIRONMENTS:
            key = by_name.get(name.casefold()) or new_id()
            environments[key] = {**environments.get(key, {}), "name": name, "color": color}

    def save_group(self, data, key, name, color=None):
        name = name.strip()
        if not name:
            raise ConfigError(_("Enter a valid group name."))
        if any(item["name"].casefold() == name.casefold() for item_id, item in data["groups"].items() if item_id != key):
            raise ConfigError(_("The group name is already in use."))
        key = key or new_id()
        previous = data["groups"].get(key, {})
        group = {**previous, "name": name, "order": previous.get("order", len(data["groups"]))}
        if color is not None:
            if color == "":
                group.pop("color", None)
            elif isinstance(color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                group["color"] = color.lower()
            else:
                raise ConfigError(_("Select a valid group color."))
        data["groups"][key] = group
        return key

    def delete_group(self, data, key, target=None):
        if target == key or (target and target not in data["groups"]):
            raise ConfigError(_("Select a valid destination group."))
        for record in data["connections"].values():
            if record.get("group_id") == key:
                record["group_id"] = target
        del data["groups"][key]


class StoreLock:
    def __init__(self, path):
        self.path = path
    def __enter__(self):
        self.handle = self.path.open("a")
        os.chmod(self.path, 0o600)
        fcntl.flock(self.handle, fcntl.LOCK_EX)
        return self
    def __exit__(self, *_):
        self.handle.close()
