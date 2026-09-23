#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DEFAULT_VERSION=$(sed -n 's/^__version__ = "\([^"]*\)"/\1/p' "$PROJECT_DIR/confissh/__init__.py")
VERSION="${1:-$DEFAULT_VERSION}"

if ! command -v rpmbuild >/dev/null 2>&1; then
    echo "Error: rpmbuild is required to build the RPM (Fedora: sudo dnf install rpm-build)." >&2
    exit 1
fi
if [ "$(rpm --eval '%{python3_sitelib}')" = '%{python3_sitelib}' ]; then
    echo "Error: Python RPM macros are required (Fedora: sudo dnf install python3-devel)." >&2
    exit 1
fi

BUILD_DIR=$(mktemp -d)
trap 'rm -rf "$BUILD_DIR"' EXIT INT TERM
TOPDIR="$BUILD_DIR/rpmbuild"
mkdir -p "$TOPDIR/BUILD" "$TOPDIR/BUILDROOT" "$TOPDIR/RPMS" "$TOPDIR/SOURCES" "$TOPDIR/SPECS" "$TOPDIR/SRPMS"

tar \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --transform="s,^,confissh-$VERSION/," \
    -czf "$TOPDIR/SOURCES/confissh-$VERSION.tar.gz" \
    -C "$PROJECT_DIR" confissh packaging LICENSE
cp "$PROJECT_DIR/packaging/confissh.spec" "$TOPDIR/SPECS/confissh.spec"

rpmbuild \
    --define "_topdir $TOPDIR" \
    --define "_confissh_version $VERSION" \
    -bb "$TOPDIR/SPECS/confissh.spec"

mkdir -p "$PROJECT_DIR/dist"
RPM=$(find "$TOPDIR/RPMS" -type f -name '*.rpm' -print -quit)
if [ -z "$RPM" ]; then
    echo "Error: rpmbuild did not produce an output." >&2
    exit 1
fi
cp "$RPM" "$PROJECT_DIR/dist/"
echo "$PROJECT_DIR/dist/$(basename "$RPM")"
