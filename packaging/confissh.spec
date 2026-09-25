Name:           confissh
Version:        %{_confissh_version}
Release:        2
Summary:        OpenSSH connection manager
License:        MIT
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  python3

Requires:       python3 >= 3.10
Requires:       python3-gobject
Requires:       gtk3
Requires:       openssh-clients

%description
Displays and edits connections from existing OpenSSH config files and stores
them with application metadata and safe backups.

%prep
%setup -q

%build

%install
install -Dm0755 packaging/rpm/confissh %{buildroot}%{_bindir}/confissh
install -Dm0644 packaging/confissh.desktop %{buildroot}%{_datadir}/applications/confissh.desktop
install -Dm0644 packaging/confissh.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/confissh.svg
# Private sources avoid a versioned site-packages path and exact python(abi).
install -d %{buildroot}%{_datadir}/confissh/confissh/resources/locales
install -m0644 confissh/__init__.py confissh/core.py confissh/storage.py confissh/keys.py confissh/app.py confissh/i18n.py \
    %{buildroot}%{_datadir}/confissh/confissh/
install -m0644 confissh/resources/style.css %{buildroot}%{_datadir}/confissh/confissh/resources/style.css
install -m0644 confissh/resources/locales/tr.json %{buildroot}%{_datadir}/confissh/confissh/resources/locales/tr.json

%files
%{_bindir}/confissh
%{_datadir}/confissh/
%{_datadir}/applications/confissh.desktop
%{_datadir}/icons/hicolor/scalable/apps/confissh.svg
%license LICENSE

%changelog
* Thu Sep 24 2026 ConfiSSH Contributors - 0.1.2-2
- Detect the preferred terminal and Fedora Ptyxis for SSH connections.

* Thu Sep 24 2026 ConfiSSH Contributors - 0.1.1-2
- Install private Python sources independently of the build Python version.

* Wed Sep 23 2026 ConfiSSH Contributors - 0.1.0-1
- Initial public release.
