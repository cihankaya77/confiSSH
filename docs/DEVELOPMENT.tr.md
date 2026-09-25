# Geliştirme ve doğrulama

```bash
sudo apt install python3 python3-gi python3-cairo python3-gi-cairo gir1.2-gtk-3.0 \
  openssh-client desktop-file-utils xauth xvfb libx11-6 libxtst6
make run
make test
make lint
make check-ui
make check-drag
```

GTK kontrolleri geçici config ve veri dizinlerinde çalışır. Gerçek sürükleme
testi X11/XWayland, libX11 ve libXtst kullanır. Örnek SSH dosyasıyla çalıştırmak
için `CONFISSH_CONFIG="$PWD/examples/config" make run` kullanılabilir;
ilk açılışta bu dosyaya da bağlantı kimlikleri eklenir.

## Kaynak koddan paket oluşturma

```bash
make deb
version=$(python3 -c 'from confissh import __version__; print(__version__)')
sudo apt install ./dist/confissh_${version}_amd64.deb
```

Fedora üzerinde RPM oluşturmak ve kurmak için (aynı paket Fedora 42, 43 ve 44 üzerinde test edilir):

```bash
sudo dnf install rpm-build python3
make rpm
version=$(python3 -c 'from confissh import __version__; print(__version__)')
sudo dnf install ./dist/confissh-${version}-2.noarch.rpm
```

Ubuntu üzerinde Docker ile aynı Fedora RPM'si üretilebilir:

```bash
make rpm-docker
make check-rpm
```

AppImage oluşturmak ve çalıştırmak için:

```bash
sudo apt install squashfs-tools curl
make appimage
version=$(python3 -c 'from confissh import __version__; print(__version__)')
./dist/ConfiSSH-${version}-x86_64.AppImage
```

AppImage, uygulama kodunu tek dosyada taşır ve sandbox kullanmadığı için
`~/.ssh` ile sistem terminaline doğrudan erişir. Bu ince paket sistemde Python
3.10+, PyGObject, GTK 3 ve OpenSSH istemcisinin kurulu olmasını bekler; eksikse
çalıştırırken dağıtıma uygun kurulum komutunu gösterir. İlk derlemede resmî
AppImage type-2 runtime `build/appimage` altına indirilir ve sabit SHA-256
özetiyle doğrulanır. `APPIMAGE_RUNTIME`
ile önceden indirilmiş bir runtime da verilebilir. x86_64 ve aarch64 desteklenir.

Üç biçimi birlikte üretmek için gerekli araçlar kurulduktan sonra
`make packages` kullanılabilir. `rpmbuild` ve RPM ile kurulmuş Python yoksa
RPM otomatik olarak Fedora Docker container içinde oluşturulur. Çıktılar `dist/`
dizinine yazılır.

## CI/CD ve sürümleme

Her push ve pull request'te birim testleri, statik kontroller, GTK iş akışı,
gerçek sürükle-bırak testi ve üç paket biçiminin derlenmesi GitHub Actions ile
doğrulanır. Derleme çıktıları kaynak kontrolüne alınmaz.

Yeni sürüm hazırlamak için `confissh/__init__.py` ve `CHANGELOG.md`
güncellenip değişiklikler ana dala alınır. Ardından sürümle aynı etiketi itin:

```bash
version=$(python3 -c 'from confissh import __version__; print(__version__)')
git tag -a "v$version" -m "ConfiSSH v$version"
git push origin "v$version"
```

Etiket iş akışı DEB, Fedora RPM ve AppImage dosyalarını üretir; SHA-256
özetleriyle birlikte GitHub Release olarak yayımlar. Katkı süreci
[CONTRIBUTING.md](../CONTRIBUTING.md), hassas hata bildirimleri ise [SECURITY.md](../SECURITY.md) içinde açıklanır.

[English overview](../README.md) · [Türkçe tanıtım](../README.tr.md)
