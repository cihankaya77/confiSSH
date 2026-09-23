from __future__ import annotations

import fcntl
import os
import re
import shutil
import tempfile
import glob
import shlex
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .i18n import _


HOST_RE = re.compile(r"^(?P<indent>\s*)Host\s+(?P<value>.+?)\s*$", re.IGNORECASE)
DISABLED_HOST_RE = re.compile(
    r"^(?P<indent>\s*)#\s*Host\s+(?P<value>.+?)\s*$", re.IGNORECASE
)
DIRECTIVE_RE = re.compile(r"^\s*(?P<key>[A-Za-z][A-Za-z0-9]*)(?:\s*=\s*|\s+)(?P<value>.*?)\s*$")
DISABLED_DIRECTIVE_RE = re.compile(
    r"^\s*#\s*(?P<key>[A-Za-z][A-Za-z0-9]*)\s+(?P<value>.*?)\s*$"
)
KEY_RE = re.compile(r"^\s*#\s*confissh-key:\s*([0-9a-fA-F-]{36})\s*$")
SEPARATOR_RE = re.compile(r"^\s*#+\s*$")

PRIMARY_KEYS = ("hostname", "user", "port", "identityfile", "proxyjump")


def parse_tags(text: str) -> list[str]:
    """Comma-separated labels; preserve spelling and order, deduplicate by case."""
    if "\n" in text or "\r" in text:
        raise ConfigError(_("Tags cannot contain line breaks."))
    tags = []
    seen = set()
    for value in text.split(","):
        tag = value.strip()
        if tag and tag.casefold() not in seen:
            tags.append(tag)
            seen.add(tag.casefold())
    return tags


@dataclass
class ConfigOption:
    key: str
    value: str
    enabled: bool = True

    def line(self, indent: str = "  ") -> str:
        if not self.key:
            return f"{indent}{self.value}".rstrip()
        prefix = "" if self.enabled else "# "
        return f"{indent}{prefix}{self.key} {self.value}".rstrip()


@dataclass
class HostEntry:
    aliases: list[str]
    options: list[ConfigOption] = field(default_factory=list)
    group: str = ""
    note: str = ""
    enabled: bool = True
    start: int = -1
    end: int = -1
    environment: str = ""
    tags: list[str] = field(default_factory=list)
    connection_id: str = ""
    group_id: str | None = None

    @property
    def alias(self) -> str:
        return " ".join(self.aliases)

    def get(self, key: str, default: str = "") -> str:
        key = key.lower()
        for option in self.options:
            if option.key.lower() == key and option.enabled:
                return option.value
        return default

    @property
    def endpoint(self) -> str:
        return self.get("hostname") or (self.aliases[0] if self.aliases else "")

    @property
    def extra_options(self) -> list[ConfigOption]:
        result = []
        seen = set()
        for option in self.options:
            key = option.key.lower()
            if key in PRIMARY_KEYS and option.enabled and key not in seen:
                seen.add(key)
            else:
                result.append(option)
        return result

    def render(self) -> list[str]:
        lines: list[str] = []
        if self.connection_id:
            lines.append(f"# confissh-key: {self.connection_id}")

        host_line = f"Host {self.alias}".rstrip()
        if not self.enabled:
            host_line = f"# {host_line}"
        lines.append(host_line)

        for option in self.options:
            line = option.line()
            if not self.enabled:
                line = f"# {line.lstrip()}"
            lines.append(line)
        return lines


class ConfigError(RuntimeError):
    pass


class ConfigDocument:
    """Line-oriented config model that only replaces the host block being edited."""

    def __init__(self, text: str = "", path: Path | None = None):
        self.path = path
        self.baseline = path.read_bytes() if path and path.exists() else None
        self.trailing_newline = text.endswith("\n") or not text
        self.lines = text.splitlines()
        self.entries: list[HostEntry] = []
        self._parse()

    @classmethod
    def load(cls, path: str | Path) -> "ConfigDocument":
        config_path = Path(path).expanduser()
        if not config_path.exists():
            return cls("", config_path)
        try:
            return cls(config_path.read_text(encoding="utf-8"), config_path)
        except OSError as exc:
            raise ConfigError(_("Configuration could not be read: {error}").format(error=exc)) from exc

    def _heading_at(self, index: int) -> str | None:
        line = self.lines[index].strip()
        if not line.startswith("#") or SEPARATOR_RE.match(line) or KEY_RE.match(line):
            return None
        title = line.lstrip("#").strip()
        if not title:
            return None
        before = index > 0 and bool(SEPARATOR_RE.match(self.lines[index - 1]))
        after = index + 1 < len(self.lines) and bool(SEPARATOR_RE.match(self.lines[index + 1]))
        return title if before or after else None

    def _parse(self) -> None:
        metadata = {e.connection_id: (e.group, e.group_id, e.environment, e.note, e.tags)
                    for e in self.entries if e.connection_id}
        self.entries.clear()
        index = 0
        while index < len(self.lines):
            active = HOST_RE.match(self.lines[index])
            disabled = DISABLED_HOST_RE.match(self.lines[index]) if not active else None
            if not active and not disabled:
                index += 1
                continue

            enabled = active is not None
            match = active or disabled
            assert match is not None
            start = index
            meta_start = index
            connection_id = ""

            cursor = index - 1
            while cursor >= 0:
                key = KEY_RE.match(self.lines[cursor])
                if key:
                    connection_id = key.group(1)
                    meta_start = cursor
                    cursor -= 1
                    continue
                break
            start = meta_start

            options: list[ConfigOption] = []
            cursor = index + 1
            while cursor < len(self.lines):
                raw = self.lines[cursor]
                if HOST_RE.match(raw) or DISABLED_HOST_RE.match(raw):
                    break
                if re.match(r"^\s*Match(?:\s|=)", raw, re.I):
                    break
                if not raw.strip():
                    lookahead = cursor + 1
                    while lookahead < len(self.lines) and not self.lines[lookahead].strip():
                        lookahead += 1
                    following = self.lines[lookahead] if lookahead < len(self.lines) else ""
                    if (DIRECTIVE_RE.match(following) and not
                        re.match(r"^\s*(Host|Match)\s", following, re.I)):
                        options.append(ConfigOption("", "", True))
                        cursor += 1
                        continue
                    break
                if SEPARATOR_RE.match(raw):
                    break
                if KEY_RE.match(raw) or self._heading_at(cursor):
                    break

                directive = DIRECTIVE_RE.match(raw)
                commented = DISABLED_DIRECTIVE_RE.match(raw)
                if enabled and directive:
                    options.append(ConfigOption(directive.group("key"), directive.group("value"), True))
                elif enabled and commented:
                    options.append(ConfigOption(commented.group("key"), commented.group("value"), False))
                elif not enabled and commented:
                    options.append(ConfigOption(commented.group("key"), commented.group("value"), True))
                elif raw.strip().startswith("#"):
                    options.append(ConfigOption("", raw.strip(), True))
                cursor += 1

            self.entries.append(
                HostEntry(
                    aliases=match.group("value").split(),
                    options=options,
                    enabled=enabled,
                    start=start,
                    end=cursor,
                    connection_id=connection_id,
                )
            )
            if connection_id in metadata:
                entry = self.entries[-1]
                entry.group, entry.group_id, entry.environment, entry.note, entry.tags = metadata[connection_id]
            index = max(cursor, index + 1)

    def groups(self) -> list[str]:
        return sorted({entry.group for entry in self.entries}, key=str.casefold)

    def aliases(self, excluding: HostEntry | None = None) -> set[str]:
        return {
            alias
            for entry in self.entries
            if entry is not excluding
            for alias in entry.aliases
        }

    def validate_entry(self, entry: HostEntry, replacing: HostEntry | None = None) -> list[str]:
        errors: list[str] = []
        if not entry.aliases:
            errors.append(_("At least one Host alias is required."))
        if any("\n" in value or "\r" in value for value in
               [entry.group, entry.note, entry.environment, *entry.tags] +
               [part for option in entry.options for part in (option.key, option.value)]):
            errors.append(_("Fields cannot contain line breaks."))
        if any("," in tag or not tag.strip() for tag in entry.tags):
            errors.append(_("Tags cannot be empty or contain commas."))
        if any(any(ch.isspace() for ch in alias) for alias in entry.aliases):
            errors.append(_("Host aliases cannot contain whitespace."))
        duplicates = self.aliases(replacing).intersection(entry.aliases)
        if duplicates:
            errors.append(_("This Host alias already exists: {aliases}").format(aliases=", ".join(sorted(duplicates))))
        port = entry.get("port")
        if port:
            try:
                number = int(port)
                if not 1 <= number <= 65535:
                    raise ValueError
            except ValueError:
                errors.append(_("Port must be a number between 1 and 65535."))
        return errors

    def add(self, entry: HostEntry) -> None:
        errors = self.validate_entry(entry)
        if errors:
            raise ConfigError("\n".join(errors))
        if self.lines and self.lines[-1].strip():
            self.lines.append("")
        self.trailing_newline = True
        self.lines.extend(entry.render())
        self.lines.append("")
        if entry.connection_id:
            self.entries.append(entry)
        self._parse()

    def replace(self, old: HostEntry, new: HostEntry) -> None:
        errors = self.validate_entry(new, replacing=old)
        if errors:
            raise ConfigError("\n".join(errors))
        if (old.connection_id and old.connection_id == new.connection_id
                and old.aliases == new.aliases and old.options == new.options
                and old.enabled == new.enabled):
            new.start, new.end = old.start, old.end
            self.entries[self.entries.index(old)] = new
            return
        self.lines[old.start : old.end] = new.render()
        if new.connection_id:
            self.entries[self.entries.index(old)] = new
        self._parse()

    def delete(self, entry: HostEntry) -> None:
        end = entry.end
        if end < len(self.lines) and not self.lines[end].strip():
            end += 1
        del self.lines[entry.start:end]
        self._parse()

    def as_text(self) -> str:
        text = "\n".join(self.lines)
        if self.trailing_newline:
            text += "\n"
        return text

    def save(self, backup: bool = True) -> Path | None:
        if self.path is None:
            raise ConfigError(_("No save path was specified."))
        path = self.path.expanduser()
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        backup_path: Path | None = None

        lock_path = path.with_name(f".{path.name}.confissh.lock")
        try:
            with lock_path.open("w", encoding="utf-8") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                current = path.read_bytes() if path.exists() else None
                if current != self.baseline:
                    raise ConfigError(_("The file changed in another application. Reload and apply the change again."))
                if backup and path.exists():
                    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                    backup_path = path.with_name(f"{path.name}.bak.{stamp}")
                    shutil.copy2(path, backup_path)
                    os.chmod(backup_path, 0o600)

                fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as handle:
                        handle.write(self.as_text())
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.chmod(temp_name, 0o600)
                    os.replace(temp_name, path)
                    self.baseline = path.read_bytes()
                finally:
                    if os.path.exists(temp_name):
                        os.unlink(temp_name)
                fcntl.flock(lock, fcntl.LOCK_UN)
        except OSError as exc:
            raise ConfigError(_("Configuration could not be saved: {error}").format(error=exc)) from exc
        return backup_path

    def changed_on_disk(self) -> bool:
        if not self.path:
            return False
        return (self.path.read_bytes() if self.path.exists() else None) != self.baseline

    def backups(self) -> list[Path]:
        if not self.path:
            return []
        return sorted(self.path.parent.glob(self.path.name + ".bak.*"), reverse=True)


def included_paths(root: Path) -> list[Path]:
    """Discover Include sources, not effective Host/Match evaluation."""
    found: list[Path] = []
    visited: set[Path] = set()

    def visit(path: Path):
        path = path.expanduser().resolve()
        if path in visited:
            return
        visited.add(path)
        found.append(path)
        if not path.exists():
            return
        for raw in path.read_text(encoding="utf-8").splitlines():
            tokens = shlex.split(raw, comments=True)
            if tokens and tokens[0].lower() == "include":
                for pattern in tokens[1:]:
                    expanded = Path(pattern).expanduser()
                    if not expanded.is_absolute():
                        expanded = Path.home() / ".ssh" / expanded
                    for child in sorted(glob.glob(str(expanded))):
                        if Path(child).is_file():
                            visit(Path(child))
    visit(root)
    return found


def parse_extra_options(text: str) -> list[ConfigOption]:
    options: list[ConfigOption] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        enabled = True
        if line.startswith("#"):
            enabled = False
            line = line[1:].strip()
        match = DIRECTIVE_RE.match(line)
        if not match:
            if raw.strip().startswith("#"):
                options.append(ConfigOption("", raw.strip(), True))
                continue
            raise ConfigError(_("Line {number} in additional settings is invalid: {line}").format(number=number, line=raw))
        if match.group("key").lower() in ("host", "match"):
            raise ConfigError(_("Do not add Host or Match lines to additional settings."))
        options.append(ConfigOption(match.group("key"), match.group("value"), enabled))
    return options


def merge_options(values: dict[str, str], extras: Iterable[ConfigOption]) -> list[ConfigOption]:
    labels = {
        "hostname": "HostName",
        "user": "User",
        "port": "Port",
        "identityfile": "IdentityFile",
        "proxyjump": "ProxyJump",
    }
    result = [ConfigOption(labels[key], value.strip()) for key, value in values.items() if value.strip()]
    result.extend(extras)
    return result
