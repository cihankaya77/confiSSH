# Development and verification

On Ubuntu:

```bash
sudo apt install python3 python3-gi python3-cairo python3-gi-cairo gir1.2-gtk-3.0 \
  openssh-client desktop-file-utils xauth xvfb libx11-6 libxtst6
make run
make test
make lint
make check-ui
make check-drag
```

GTK checks use temporary config and data directories. The real drag-and-drop
check requires X11/XWayland, libX11, and libXtst. To run with the example SSH
file:

```bash
CONFISSH_CONFIG="$PWD/examples/config" make run
```

ConfiSSH adds connection identifiers to that file on first launch.

## Building packages from source

DEB:

```bash
make deb
version=$(python3 -c 'from confissh import __version__; print(__version__)')
sudo apt install ./dist/confissh_${version}_amd64.deb
```

RPM on Fedora (the same package is tested on Fedora 42, 43, and 44):

```bash
sudo dnf install rpm-build python3
make rpm
version=$(python3 -c 'from confissh import __version__; print(__version__)')
sudo dnf install ./dist/confissh-${version}-2.noarch.rpm
```

Build the same Fedora RPM from Ubuntu with Docker:

```bash
make rpm-docker
make check-rpm
```

AppImage:

```bash
sudo apt install squashfs-tools curl
make appimage
version=$(python3 -c 'from confissh import __version__; print(__version__)')
./dist/ConfiSSH-${version}-x86_64.AppImage
```

The thin AppImage is not sandboxed, so it can access `~/.ssh` and the system
terminal. It expects Python 3.10+, PyGObject, GTK 3, and OpenSSH on the host. The
first build downloads the official AppImage type-2 runtime into
`build/appimage` and verifies its pinned SHA-256 digest. Set `APPIMAGE_RUNTIME`
to use a pre-downloaded runtime. x86_64 and aarch64 are supported.

Run `make packages` to build all three formats. On systems without
`rpmbuild` and an RPM-managed Python installation, the RPM is built in the Fedora Docker container
automatically. Outputs are written to `dist/`.

## CI/CD and releases

Every push and pull request runs unit tests, static checks, GTK workflow tests,
the real drag-and-drop check, and package builds in GitHub Actions.

To prepare a release, update `confissh/__init__.py` and `CHANGELOG.md`, merge the
changes into the main branch, and push a matching tag:

```bash
version=$(python3 -c 'from confissh import __version__; print(__version__)')
git tag -a "v$version" -m "ConfiSSH v$version"
git push origin "v$version"
```

The tag workflow publishes DEB, Fedora RPM, AppImage, and SHA-256 checksums in
a GitHub Release. See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines and
[SECURITY.md](../SECURITY.md) for private vulnerability reporting.

[English overview](../README.md) · [Türkçe tanıtım](../README.tr.md)
