# Install ConfiSSH

Download a ready-made package from [GitHub Releases](https://github.com/cihankaya77/confiSSH/releases/latest). You
do not need the source tree or `make`.

## Ubuntu and Debian (.deb)

The following commands resolve the latest GitHub release, generate its AMD64
DEB asset name, and install it. The version number does not need to be updated:

```bash
release_url=$(curl -fsSL -o /dev/null -w '%{url_effective}' \
  https://github.com/cihankaya77/confiSSH/releases/latest)
release_tag=${release_url##*/}
version=${release_tag#v}
package="/tmp/confissh_${version}_amd64.deb"
curl -fL \
  "https://github.com/cihankaya77/confiSSH/releases/download/${release_tag}/confissh_${version}_amd64.deb" \
  -o "$package"
sudo apt install "$package"
```

`apt` installs the required Python, GTK 3, and OpenSSH packages. Launch ConfiSSH
from the application menu or run:

```bash
confissh
```

## Fedora (.rpm)

The following commands resolve the latest GitHub release, generate its RPM
asset name, and install it:

```bash
release_url=$(curl -fsSL -o /dev/null -w '%{url_effective}' \
  https://github.com/cihankaya77/confiSSH/releases/latest)
release_tag=${release_url##*/}
version=${release_tag#v}
package="/tmp/confissh-${version}-2.noarch.rpm"
curl -fL \
  "https://github.com/cihankaya77/confiSSH/releases/download/${release_tag}/confissh-${version}-2.noarch.rpm" \
  -o "$package"
sudo dnf install "$package"
```

The RPM uses the system Python (3.10+) and installs its application sources in
`/usr/share/confissh`, independently of the build environment’s Python version.
`dnf` installs the required Python, GTK 3, and OpenSSH packages. Launch ConfiSSH
from the application menu or with `confissh`.

## AppImage

The AppImage does not install system packages. It is intentionally thin and
uses Python, GTK 3, and OpenSSH from the host system. First install its runtime
dependencies.

Ubuntu/Debian:

```bash
sudo apt install python3 python3-gi gir1.2-gtk-3.0 openssh-client
```

Fedora:

```bash
sudo dnf install python3 python3-gobject gtk3 openssh-clients
```

Then download and run the x86_64 AppImage from the latest GitHub release:

```bash
release_url=$(curl -fsSL -o /dev/null -w '%{url_effective}' \
  https://github.com/cihankaya77/confiSSH/releases/latest)
release_tag=${release_url##*/}
version=${release_tag#v}
appimage="ConfiSSH-${version}-x86_64.AppImage"
curl -fL \
  "https://github.com/cihankaya77/confiSSH/releases/download/${release_tag}/${appimage}" \
  -o "$appimage"
chmod +x "$appimage"
"./$appimage"
```

Delete the AppImage file to remove it.

## Updating and uninstalling

Install a newer DEB or RPM with the same installation command. Replace the old
file for AppImage updates.

```bash
# Ubuntu/Debian
sudo apt remove confissh

# Fedora
sudo dnf remove confissh
```

Uninstalling does not remove `~/.ssh/config` or data and backups under
`~/.config/confissh`. Delete those files separately only if you no longer need
them.


[Back to overview](../README.md) · [Türkçe kurulum](INSTALL.tr.md)
