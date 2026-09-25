# ConfiSSH — SSH Connection Manager for Linux

**Keep your servers organized. Find a connection. Open it in your terminal.**

ConfiSSH is a free, open-source SSH GUI for Linux. Manage your OpenSSH connections,
organize servers into groups, and find your SSH keys in one desktop app. It works
with your existing `~/.ssh/config`, so you can keep using `ssh host-alias` from the
command line too.

**[Download ConfiSSH](https://github.com/cihankaya77/confiSSH/releases/latest)** ·
[Installation guide](docs/INSTALL.md) ·
[Türkçe](README.tr.md) ·
[Report a problem](https://github.com/cihankaya77/confiSSH/issues)

Linux desktop · DEB / RPM / AppImage · English / Türkçe · [MIT license](LICENSE)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/confissh-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/screenshots/confissh-light.png">
  <img alt="ConfiSSH SSH connection manager showing server groups, favorites, search, and Connect buttons" src="docs/screenshots/confissh-light.png">
</picture>

## What can you do with ConfiSSH?

- **Connect without remembering addresses.** Search by server name, IP, user, or
  tag, then click **Connect** to open SSH in your system terminal.
- **Keep work, home, and cloud servers organized.** Create groups, move connections
  with drag and drop, and distinguish environments with colors, tags, and notes.
  Favorites and recently used connections help you return to frequent hosts.
- **Edit SSH settings visually.** Add or duplicate a connection, choose an identity
  file from disk, and configure ports, jump hosts, SSH tunnels, and keep-alive options.
- **Find and copy SSH keys.** Browse public and private keys from `~/.ssh`, your
  configured identity files, or another folder. Copy a key or its file path.
- **Keep your existing SSH setup.** ConfiSSH is an OpenSSH config editor that also
  reads `Include` files. Your connections remain usable from the command line.
- **Recover earlier settings.** Changes create automatic backups. Preview and
  restore a backup from **Settings → Backups**.
- **Make the app comfortable to use.** Choose a light, dark, or system theme and
  switch between English and Turkish.

Whether you connect to a home lab, a VPS, or servers at work, ConfiSSH gives you a
searchable list of connections with the settings you use for each one.

## Download and install

Choose a package from the **[latest release](https://github.com/cihankaya77/confiSSH/releases/latest)**:

| Your Linux desktop | Download | Installation instructions |
| --- | --- | --- |
| Ubuntu or Debian | `.deb` | [Install with apt](docs/INSTALL.md#ubuntu-and-debian-deb) |
| Fedora | `.rpm` | [Install with dnf](docs/INSTALL.md#fedora-rpm) |
| Other Linux desktops | `.AppImage` | [Dependencies and launch instructions](docs/INSTALL.md#appimage) |

The download commands in the guide select the x86_64 / AMD64 packages. The
AppImage uses system Python, GTK, and OpenSSH; its required packages are listed
in the guide.

After installation, open **ConfiSSH** from your application menu, or run `confissh`
for a DEB or RPM installation.

[Updating or uninstalling](docs/INSTALL.md#updating-and-uninstalling)

## Your first connection

1. **Open ConfiSSH.** Existing connections in `~/.ssh/config` appear automatically.
2. **Click Add connection** to add a server. Enter a short host alias, its address,
   and your username. Select an identity file if you use key authentication.
3. **Organize it if you like.** In the Organization tab, choose a group or
   environment and add tags or a note.
4. **Save, then Connect.** ConfiSSH opens your terminal and starts SSH. Password,
   passphrase, and host-key prompts are handled by OpenSSH there.

You can also copy a connection's SSH command and run it yourself.

## Keep connections easy to find

Use the **+** beside Groups to create a group, then drag connections into it.
Right-click a group to rename it, change its color, or manage its connections.
The fixed **Ungrouped connections** entry shows connections without a group and
hides when there are none. Drag a connection onto it to remove its group assignment.

Star frequently used servers, add searchable tags such as `database` or `homelab`,
and use **Settings → Environments** to distinguish production and development.

| Connection settings | Groups, tags, and notes |
| :--: | :--: |
| ![SSH connection editor with server, user, port, and identity file settings](docs/screenshots/confissh-editor.png) | ![Organize SSH connections with groups, environments, tags, and notes](docs/screenshots/confissh-organization.png) |

| Appearance | Backups |
| :--: | :--: |
| ![Light and dark theme and language settings](docs/screenshots/confissh-settings.png) | ![Browse and restore SSH configuration backups](docs/screenshots/confissh-backups.png) |

## Common questions

**Does it use my existing SSH config?** Yes. ConfiSSH reads `~/.ssh/config` and its
included files. On first launch, it backs up your configuration and adds small
identifier comments to track your connections. Your usual SSH commands still work.

**Does it include a terminal?** Connect opens a terminal installed on your system.
If a supported terminal is unavailable, you can copy the SSH command instead.

**Can I recover a change?** Use **Settings → Backups** to preview and restore
connection settings and organization together. Backups stay on your computer
until you delete them.

**Where are my settings?** SSH settings remain in your SSH config files. Groups,
notes, preferences, and backups live under `~/.config/confissh`. Uninstalling the
app leaves these files in place.

**Does it run on Windows or macOS?** The application and installation packages
target Linux desktops.

## Help and project information

- [Report a bug or request a feature](https://github.com/cihankaya77/confiSSH/issues).
- Read the [changelog](CHANGELOG.md) or [release notes](https://github.com/cihankaya77/confiSSH/releases).
- For development, see [contributing](CONTRIBUTING.md), [build instructions](docs/DEVELOPMENT.md),
  and the [technical reference](docs/TECHNICAL.md).
- Read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.
- Report vulnerabilities using the [security policy](SECURITY.md).

ConfiSSH is free and open source under the [MIT license](LICENSE).
