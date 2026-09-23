.PHONY: run test lint check-ui check-drag ci deb rpm rpm-docker appimage packages clean

run:
	PYTHONPATH=. python3 -m confissh.app

test:
	PYTHONPATH=. python3 -m unittest discover -s tests -v

lint:
	python3 -m compileall -q confissh tests
	python3 -m json.tool confissh/resources/locales/tr.json >/dev/null
	desktop-file-validate packaging/confissh.desktop
	sh -n scripts/build-deb.sh scripts/build-rpm.sh scripts/build-appimage.sh

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
	docker run --rm -v "$(CURDIR):/src" -w /src fedora:42 bash -lc 'dnf -y install rpm-build python3-devel >/tmp/dnf.log && sh scripts/build-rpm.sh && owner=$$(stat -c %u:%g /src) && chown "$$owner" /src/dist/*.rpm'

appimage:
	sh scripts/build-appimage.sh

packages: deb rpm appimage

clean:
	rm -rf build dist
