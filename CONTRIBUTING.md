# Contributing

Contributions are welcome. Before sending a change, open a related issue when
possible or discuss the approach in an existing issue.

## Development environment

Install the required packages and run the checks on Ubuntu:

```bash
sudo apt install python3 python3-gi python3-cairo gir1.2-gtk-3.0 \
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
