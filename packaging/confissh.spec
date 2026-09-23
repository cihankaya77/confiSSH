Name:           confissh
Version:        %{_confissh_version}
Release:        1%{?dist}
Summary:        OpenSSH connection manager
License:        MIT
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  python3-devel

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
install -Dm0755 packaging/confissh %{buildroot}%{_bindir}/confissh
install -Dm0644 packaging/confissh.desktop %{buildroot}%{_datadir}/applications/confissh.desktop
install -Dm0644 packaging/confissh.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/confissh.svg
install -d %{buildroot}%{python3_sitelib}/confissh/resources/locales
install -m0644 confissh/__init__.py confissh/core.py confissh/storage.py confissh/app.py confissh/i18n.py \
    %{buildroot}%{python3_sitelib}/confissh/
install -m0644 confissh/resources/style.css %{buildroot}%{python3_sitelib}/confissh/resources/style.css
install -m0644 confissh/resources/locales/tr.json %{buildroot}%{python3_sitelib}/confissh/resources/locales/tr.json

%files
%{_bindir}/confissh
%{python3_sitelib}/confissh/
%{_datadir}/applications/confissh.desktop
%{_datadir}/icons/hicolor/scalable/apps/confissh.svg
%license LICENSE

%changelog
* Wed Sep 23 2026 ConfiSSH Contributors - 0.1.0-1
- Initial public release.
