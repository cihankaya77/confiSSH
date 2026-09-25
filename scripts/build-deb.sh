#!/bin/sh
set -eu

DEFAULT_VERSION=$(sed -n 's/^__version__ = "\([^"]*\)"/\1/p' "$(dirname "$0")/../confissh/__init__.py")
VERSION="${1:-$DEFAULT_VERSION}"
ARCH="${2:-$(dpkg --print-architecture)}"
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BUILD_DIR=$(mktemp -d)
ROOT="$BUILD_DIR/confissh_${VERSION}_${ARCH}"
trap 'rm -rf "$BUILD_DIR"' EXIT INT TERM

mkdir -p \
  "$ROOT/DEBIAN" \
  "$ROOT/usr/bin" \
  "$ROOT/usr/lib/python3/dist-packages/confissh/resources/locales" \
  "$ROOT/usr/share/applications" \
  "$ROOT/usr/share/doc/confissh" \
  "$ROOT/usr/share/icons/hicolor/scalable/apps"

cp "$PROJECT_DIR/confissh/__init__.py" "$ROOT/usr/lib/python3/dist-packages/confissh/"
cp "$PROJECT_DIR/confissh/core.py" "$ROOT/usr/lib/python3/dist-packages/confissh/"
cp "$PROJECT_DIR/confissh/storage.py" "$ROOT/usr/lib/python3/dist-packages/confissh/"
cp "$PROJECT_DIR/confissh/keys.py" "$ROOT/usr/lib/python3/dist-packages/confissh/"
cp "$PROJECT_DIR/confissh/app.py" "$ROOT/usr/lib/python3/dist-packages/confissh/"
cp "$PROJECT_DIR/confissh/i18n.py" "$ROOT/usr/lib/python3/dist-packages/confissh/"
cp "$PROJECT_DIR/confissh/resources/style.css" "$ROOT/usr/lib/python3/dist-packages/confissh/resources/"
cp "$PROJECT_DIR/confissh/resources/locales/tr.json" "$ROOT/usr/lib/python3/dist-packages/confissh/resources/locales/"
cp "$PROJECT_DIR/packaging/confissh" "$ROOT/usr/bin/confissh"
cp "$PROJECT_DIR/packaging/confissh.desktop" "$ROOT/usr/share/applications/"
cp "$PROJECT_DIR/packaging/confissh.svg" "$ROOT/usr/share/icons/hicolor/scalable/apps/"
cp "$PROJECT_DIR/LICENSE" "$ROOT/usr/share/doc/confissh/copyright"
chmod 0755 "$ROOT/usr/bin/confissh"
chmod 0644 \
  "$ROOT/usr/lib/python3/dist-packages/confissh/__init__.py" \
  "$ROOT/usr/lib/python3/dist-packages/confissh/core.py" \
  "$ROOT/usr/lib/python3/dist-packages/confissh/storage.py" \
  "$ROOT/usr/lib/python3/dist-packages/confissh/keys.py" \
  "$ROOT/usr/lib/python3/dist-packages/confissh/app.py" \
  "$ROOT/usr/lib/python3/dist-packages/confissh/i18n.py" \
  "$ROOT/usr/lib/python3/dist-packages/confissh/resources/style.css" \
  "$ROOT/usr/lib/python3/dist-packages/confissh/resources/locales/tr.json" \
  "$ROOT/usr/share/applications/confissh.desktop" \
  "$ROOT/usr/share/doc/confissh/copyright" \
  "$ROOT/usr/share/icons/hicolor/scalable/apps/confissh.svg"
find "$ROOT" -type d -exec chmod 0755 {} +

INSTALLED_SIZE=$(du -sk "$ROOT/usr" | cut -f1)
cat > "$ROOT/DEBIAN/control" <<EOF
Package: confissh
Version: $VERSION
Section: net
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-3.0, openssh-client
Installed-Size: $INSTALLED_SIZE
Maintainer: ConfiSSH Contributors
Description: Simple OpenSSH configuration manager
 Groups and edits connections from existing OpenSSH config files and
 stores them with safe backups.
EOF

mkdir -p "$PROJECT_DIR/dist"
dpkg-deb --root-owner-group --build "$ROOT" "$PROJECT_DIR/dist/confissh_${VERSION}_${ARCH}.deb"
echo "$PROJECT_DIR/dist/confissh_${VERSION}_${ARCH}.deb"
