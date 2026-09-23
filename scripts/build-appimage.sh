#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DEFAULT_VERSION=$(sed -n 's/^__version__ = "\([^"]*\)"/\1/p' "$PROJECT_DIR/confissh/__init__.py")
VERSION="${1:-$DEFAULT_VERSION}"
MACHINE="${2:-$(uname -m)}"

case "$MACHINE" in
    x86_64|amd64)
        APPIMAGE_ARCH=x86_64
        RUNTIME_SHA256=1cc49bcf1e2ccd593c379adb17c9f85a36d619088296504de95b1d06215aebbf
        ;;
    aarch64|arm64)
        APPIMAGE_ARCH=aarch64
        RUNTIME_SHA256=7d5d772b7c32f0c84caf0a452a3072a5709027d7eac5856feb89a7a7a8881372
        ;;
    *) echo "Error: unsupported AppImage architecture: $MACHINE" >&2; exit 1 ;;
esac

if ! command -v mksquashfs >/dev/null 2>&1; then
    echo "Error: mksquashfs is required to build the AppImage (Ubuntu: sudo apt install squashfs-tools)." >&2
    exit 1
fi

BUILD_DIR=$(mktemp -d)
APPDIR="$BUILD_DIR/ConfiSSH.AppDir"
RUNTIME=${APPIMAGE_RUNTIME:-"$PROJECT_DIR/build/appimage/runtime-$APPIMAGE_ARCH"}
RUNTIME_TMP="$RUNTIME.tmp"
trap 'rm -rf "$BUILD_DIR"; rm -f "$RUNTIME_TMP"' EXIT INT TERM

if [ ! -x "$RUNTIME" ]; then
    if ! command -v curl >/dev/null 2>&1; then
        echo "Error: AppImage runtime not found. Set APPIMAGE_RUNTIME or install curl." >&2
        exit 1
    fi
    mkdir -p "$(dirname "$RUNTIME")"
    echo "Downloading AppImage runtime: $APPIMAGE_ARCH" >&2
    curl --fail --location --retry 3 \
        "https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-$APPIMAGE_ARCH" \
        --output "$RUNTIME_TMP"
    printf '%s  %s\n' "$RUNTIME_SHA256" "$RUNTIME_TMP" | sha256sum --check --status
    chmod 0755 "$RUNTIME_TMP"
    mv "$RUNTIME_TMP" "$RUNTIME"
fi

if ! printf '%s  %s\n' "$RUNTIME_SHA256" "$RUNTIME" | sha256sum --check --status; then
    echo "Error: AppImage runtime SHA-256 verification failed: $RUNTIME" >&2
    exit 1
fi

mkdir -p \
    "$APPDIR/usr/bin" \
    "$APPDIR/usr/lib/confissh/confissh/resources/locales" \
    "$APPDIR/usr/share/applications" \
    "$APPDIR/usr/share/doc/confissh" \
    "$APPDIR/usr/share/icons/hicolor/scalable/apps"

cp "$PROJECT_DIR/confissh/__init__.py" "$APPDIR/usr/lib/confissh/confissh/"
cp "$PROJECT_DIR/confissh/core.py" "$APPDIR/usr/lib/confissh/confissh/"
cp "$PROJECT_DIR/confissh/storage.py" "$APPDIR/usr/lib/confissh/confissh/"
cp "$PROJECT_DIR/confissh/app.py" "$APPDIR/usr/lib/confissh/confissh/"
cp "$PROJECT_DIR/confissh/i18n.py" "$APPDIR/usr/lib/confissh/confissh/"
cp "$PROJECT_DIR/confissh/resources/style.css" "$APPDIR/usr/lib/confissh/confissh/resources/"
cp "$PROJECT_DIR/confissh/resources/locales/tr.json" "$APPDIR/usr/lib/confissh/confissh/resources/locales/"
cp "$PROJECT_DIR/packaging/appimage/AppRun" "$APPDIR/AppRun"
cp "$PROJECT_DIR/packaging/appimage/confissh" "$APPDIR/usr/bin/confissh"
cp "$PROJECT_DIR/packaging/confissh.desktop" "$APPDIR/confissh.desktop"
cp "$PROJECT_DIR/packaging/confissh.desktop" "$APPDIR/usr/share/applications/confissh.desktop"
cp "$PROJECT_DIR/packaging/confissh.svg" "$APPDIR/confissh.svg"
cp "$PROJECT_DIR/packaging/confissh.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/confissh.svg"
cp "$PROJECT_DIR/LICENSE" "$APPDIR/usr/share/doc/confissh/LICENSE"
ln -s confissh.svg "$APPDIR/.DirIcon"
chmod 0755 "$APPDIR/AppRun" "$APPDIR/usr/bin/confissh"
find "$APPDIR" -type d -exec chmod 0755 {} +

mkdir -p "$PROJECT_DIR/dist"
SQUASHFS="$BUILD_DIR/confissh.squashfs"
OUTPUT="$PROJECT_DIR/dist/ConfiSSH-$VERSION-$APPIMAGE_ARCH.AppImage"
# The current type-2 runtime supports zlib and zstd SquashFS images.
mksquashfs "$APPDIR" "$SQUASHFS" -noappend -all-root -comp zstd -quiet
cp "$RUNTIME" "$OUTPUT"
dd if="$SQUASHFS" of="$OUTPUT" oflag=append conv=notrunc status=none
chmod 0755 "$OUTPUT"

echo "$OUTPUT"
