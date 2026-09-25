# Contributing

Contributions are welcome. Before sending a change, open a related issue when
possible or discuss the approach in an existing issue. Please follow the
[Code of Conduct](CODE_OF_CONDUCT.md) in all project interactions.

See the [development guide](docs/DEVELOPMENT.md) for running the app, building
packages, and preparing releases. The [technical reference](docs/TECHNICAL.md)
describes configuration storage and editing behavior.

## Development environment

Install the required packages and run the checks on Ubuntu:

```bash
sudo apt install python3 python3-gi python3-cairo python3-gi-cairo gir1.2-gtk-3.0 \
  openssh-client desktop-file-utils xauth xvfb libx11-6 libxtst6
make test
make lint
xvfb-run -a env PYTHONPATH=. python3 scripts/check-ui.py
xvfb-run -a env PYTHONPATH=. python3 scripts/check-drag.py
```

Pull requests should describe the purpose of the change, its user impact, and
the checks performed. Add tests for new behavior. Never include real SSH config
files, server addresses, usernames, private keys, or access tokens in issues or
test data.

By contributing code, you agree that it may be distributed under the project's
MIT license.

Repository maintainers can find the prepared description and topic settings in
[GitHub repository metadata](.github/repository-metadata.md).
