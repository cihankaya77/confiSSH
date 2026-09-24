#!/bin/sh
# Run in a disposable Fedora container with the repository mounted at /src.
set -eu

VERSION=$(sed -n 's/^__version__ = "\([^" ]*\)"/\1/p' /src/confissh/__init__.py)
PACKAGE="/src/dist/confissh-$VERSION-2.noarch.rpm"

cat /etc/fedora-release
rpm -K "$PACKAGE"
rpm -qpR "$PACKAGE" > /tmp/confissh-requires
cat /tmp/confissh-requires
grep -Fx 'python3 >= 3.10' /tmp/confissh-requires
if grep -F 'python(abi)' /tmp/confissh-requires; then
    echo 'Error: RPM depends on a specific Python ABI.' >&2
    exit 1
fi
rpm -qpl "$PACKAGE" > /tmp/confissh-files
grep -Fx /usr/bin/confissh /tmp/confissh-files
grep -Fx /usr/share/confissh/confissh/resources/locales/tr.json /tmp/confissh-files
grep -F /usr/share/licenses/confissh/ /tmp/confissh-files
if grep -E 'site-packages|\.pyc$' /tmp/confissh-files; then
    echo 'Error: RPM includes Python-version-specific files.' >&2
    exit 1
fi

# Resolve application dependencies from this Fedora's repositories.
dnf -y install "$PACKAGE" xorg-x11-server-Xvfb xorg-x11-xauth
python3 --version

# Never import from the checkout or write bytecode to the installed package.
cd /tmp
unset PYTHONPATH
export PYTHONDONTWRITEBYTECODE=1
timeout 30 xvfb-run -a /usr/bin/confissh --help
timeout 90 xvfb-run -a /usr/bin/python3 -s - <<'PYTHON'
import runpy
from pathlib import Path

# Use the installed launcher's import setup, then exercise the installed UI.
runpy.run_path('/usr/bin/confissh', run_name='package_check')
import confissh
assert Path(confissh.__file__).parent == Path('/usr/share/confissh/confissh')
runpy.run_path('/src/scripts/check-ui.py', run_name='__main__')
PYTHON
