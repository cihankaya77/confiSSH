.PHONY: run test lint check-ui check-drag ci deb rpm rpm-docker rpm-auto check-rpm appimage packages clean

RPM_TEST_FEDORAS ?= 42 43 44

run:
	PYTHONPATH=. python3 -m confissh.app

test:
	PYTHONPATH=. python3 -m unittest discover -s tests -v

lint:
	python3 -m compileall -q confissh tests
	python3 -m json.tool confissh/resources/locales/tr.json >/dev/null
	desktop-file-validate packaging/confissh.desktop
	sh -n scripts/build-deb.sh scripts/build-rpm.sh scripts/build-appimage.sh scripts/check-rpm.sh

check-ui:
	xvfb-run -a env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 scripts/check-ui.py

check-drag:
	xvfb-run -a env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 scripts/check-drag.py

ci: test lint check-ui check-drag

deb:
	sh scripts/build-deb.sh

rpm:
	sh scripts/build-rpm.sh

rpm-docker:
	docker run --rm -v "$(CURDIR):/src" -w /src fedora:42 bash -lc 'dnf -y install rpm-build python3 >/tmp/dnf.log && sh scripts/build-rpm.sh && owner=$$(stat -c %u:%g /src) && chown "$$owner" /src/dist/*.rpm'

check-rpm:
	@set -e; for release in $(RPM_TEST_FEDORAS); do \
		docker run --rm -v "$(CURDIR):/src:ro" -w /tmp "fedora:$$release" sh /src/scripts/check-rpm.sh; \
	done

rpm-auto:
	@if command -v rpmbuild >/dev/null 2>&1 && rpm -q python3 >/dev/null 2>&1; then \
		$(MAKE) rpm; \
	elif command -v docker >/dev/null 2>&1; then \
		$(MAKE) rpm-docker; \
	else \
		echo "Error: RPM build requires Fedora rpm-build/python3 or Docker." >&2; \
		exit 1; \
	fi

appimage:
	sh scripts/build-appimage.sh

packages: deb appimage rpm-auto

clean:
	rm -rf build dist
