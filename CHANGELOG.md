# Changelog

All notable changes to this project are documented here. Versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.3] - 2026-09-25

- Add a fixed, non-deletable Ungrouped connections sidebar group that hides when empty.
- Select identity files from disk and validate numeric ports in the connection editor.
- Disable Save for unchanged connections and save directly with automatic backups.
- Discover local private and public SSH keys and copy their contents or file paths.
- Update English/Turkish documentation, translations, packaging, and workflow tests.

## [0.1.2] - 2026-09-24

- Open SSH connections in the system-selected terminal or Fedora Ptyxis.

## [0.1.1] - 2026-09-24

- Install RPM application sources independently of the build Python version;
  validate the same RPM on Fedora 42, 43, and 44.
- Use English as the source and fallback language.
- Add English, Turkish, and system-default interface language options.

## [0.1.0] - 2026-09-23

- Add and edit connections without reformatting unrelated OpenSSH config data.
- Manage UUID-based groups, environments, tags, notes, and favorites.
- Manage groups with drag and drop and context menus.
- Back up and restore SSH files and application metadata together.
- Build DEB, RPM, and thin AppImage packages.
