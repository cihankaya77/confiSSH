# Technical reference

[Back to overview](../README.md) · [Türkçe](TECHNICAL.tr.md)

## Data model

- `~/.ssh/config` and its `Include` files contain `HostName`, `User`, `Port`,
  `IdentityFile`, `ProxyJump`, tunnels, and all other standard SSH directives.
- `~/.config/confissh/connections.json` contains UUID-based connection metadata,
  groups, environments, tags, notes, favorites, and recent-use timestamps.
- `~/.config/confissh/preferences.json` contains theme, language, sidebar, and
  ordering preferences.
- `~/.config/confissh/backups/` contains timestamped snapshots of SSH files and
  application metadata. Backups may contain sensitive connection details, are
  written with `0600` permissions, and are not deleted automatically.

`XDG_CONFIG_HOME` is supported. On first launch, ConfiSSH adds an identifier to
hosts that do not have one and creates a backup before writing. The only
application-specific field written to an SSH file is a comment:

```ssh-config
# confissh-key: 24e6b5d6-99c2-43dd-abcc-ad7eeef59a32
Host prod-api
  HostName 192.0.2.12
  User deploy
  IdentityFile ~/.ssh/id_ed25519
```

Example application metadata:

```json
{
  "version": 1,
  "groups": {
    "a0d217fa-861c-42ad-b2b9-d13ba50153c2": {
      "name": "Operations",
      "order": 0
    }
  },
  "environments": {
    "b0d217fa-861c-42ad-b2b9-d13ba50153c2": {
      "name": "Production",
      "color": "#e35d6a"
    }
  },
  "connections": {
    "24e6b5d6-99c2-43dd-abcc-ad7eeef59a32": {
      "group_id": "a0d217fa-861c-42ad-b2b9-d13ba50153c2",
      "environment_id": "b0d217fa-861c-42ad-b2b9-d13ba50153c2",
      "tags": ["redis", "mysql"],
      "note": "Primary server",
      "favorite": true
    }
  }
}
```

Group and environment names are labels, not identifiers. Renaming them does not
change connection relationships or SSH files. Connection metadata follows its
UUID if the host alias or source file changes. Duplicating a connection creates
a new UUID.

## Usage notes

- SSH fields and the destination config file are under the Connection tab.
  Group, environment, tags, and note are under Organization.
- Create empty groups with the plus button beside Groups. Move a connection by
  dragging it onto a group or using its context menu.
- Right-click a group to rename it, change its color, move it, or delete it.
  Deleting a group can move its connections to another group or leave them
  ungrouped; it never deletes the connections.
- Choose alphabetical or custom group ordering. Alphabetical view does not erase
  the stored custom order.
- Define environments under Settings → Environments. Production, Sandbox, and
  Development are created as examples on first launch but are not assigned
  automatically. Reset to defaults restores missing defaults and their colors
  while preserving custom environments and assignments.
- Tags are comma-separated and searchable. Environment colors appear on the
  left edge of connection rows.
- ProxyJump can be selected from active connections, including entries from
  `Include` files, or entered manually as an address or jump chain.
- Backups under Settings → Backups restore SSH files and metadata together.
  A restore first shows a diff and also backs up the current state.
- Search starts with the first character. Keyboard shortcuts are listed in
  Settings → Shortcuts.

Writes use file locks, atomic replacement, and a transaction journal. If one
part of a paired SSH/JSON write fails, the previous state is restored. Multiple
files cannot form one operating-system-level atomic operation, so interrupted
transactions are checked and recovered on the next launch.

## Localization

English is the source and fallback language. Select `System default`, `English`,
or `Türkçe` under Settings → Appearance → Language. The open window refreshes
immediately when the language changes.

Turkish translations live in
`confissh/resources/locales/tr.json`. New user-facing strings should be written
in English and passed through `_(...)`; plural messages use `ngettext(...)`.
Unknown or unavailable translations fall back to the English source text.

For deterministic automation, set `CONFISSH_LANGUAGE=en` or
`CONFISSH_LANGUAGE=tr`.


Screenshots in the README use disposable test data from the GTK workflow checks.
