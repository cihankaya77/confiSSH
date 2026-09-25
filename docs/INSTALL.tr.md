# ConfiSSH kurulumu

Hazır paketleri [GitHub Releases](https://github.com/cihankaya77/confiSSH/releases/latest) sayfasından indirin. Kaynak kodu
indirmeniz veya `make` çalıştırmanız gerekmez.

## Ubuntu ve Debian (.deb)

Aşağıdaki komutlar GitHub'daki son sürümü bulur, AMD64 DEB asset adını
otomatik üretir ve paketi kurar. Sürüm numarasını değiştirmeniz gerekmez:

```bash
release_url=$(curl -fsSL -o /dev/null -w '%{url_effective}' \
  https://github.com/cihankaya77/confiSSH/releases/latest)
release_tag=${release_url##*/}
version=${release_tag#v}
package="/tmp/confissh_${version}_amd64.deb"
curl -fL \
  "https://github.com/cihankaya77/confiSSH/releases/download/${release_tag}/confissh_${version}_amd64.deb" \
  -o "$package"
sudo apt install "$package"
```

`apt`, gerekli Python, GTK 3 ve OpenSSH paketlerini otomatik olarak kurar.
Kurulumdan sonra uygulama menüsünden **ConfiSSH** seçilebilir veya terminalde
şu komut çalıştırılabilir:

```bash
confissh
```

## Fedora (.rpm)

Aşağıdaki komutlar GitHub'daki son sürümü bulur, RPM asset adını otomatik
üretir ve paketi kurar:

```bash
release_url=$(curl -fsSL -o /dev/null -w '%{url_effective}' \
  https://github.com/cihankaya77/confiSSH/releases/latest)
release_tag=${release_url##*/}
version=${release_tag#v}
package="/tmp/confissh-${version}-2.noarch.rpm"
curl -fL \
  "https://github.com/cihankaya77/confiSSH/releases/download/${release_tag}/confissh-${version}-2.noarch.rpm" \
  -o "$package"
sudo dnf install "$package"
```

RPM, sistemin Python sürümünü (3.10+) kullanır; uygulama kaynakları derleme
ortamının Python sürümünden bağımsız olarak `/usr/share/confissh` altına kurulur.
`dnf`, gerekli Python, GTK 3 ve OpenSSH paketlerini otomatik olarak kurar.
Kurulumdan sonra uygulama menüsünden veya `confissh` komutuyla açabilirsiniz.

## AppImage

AppImage sistem paket yöneticisine kurulum yapmaz. Bu ince paket Python, GTK 3
ve OpenSSH istemcisini sistemden kullanır. Önce çalışma zamanı bağımlılıklarını
kurun.

Ubuntu/Debian:

```bash
sudo apt install python3 python3-gi gir1.2-gtk-3.0 openssh-client
```

Fedora üzerinde:

```bash
sudo dnf install python3 python3-gobject gtk3 openssh-clients
```

Ardından son GitHub sürümündeki x86_64 AppImage dosyasını indirip çalıştırın:

```bash
release_url=$(curl -fsSL -o /dev/null -w '%{url_effective}' \
  https://github.com/cihankaya77/confiSSH/releases/latest)
release_tag=${release_url##*/}
version=${release_tag#v}
appimage="ConfiSSH-${version}-x86_64.AppImage"
curl -fL \
  "https://github.com/cihankaya77/confiSSH/releases/download/${release_tag}/${appimage}" \
  -o "$appimage"
chmod +x "$appimage"
"./$appimage"
```

AppImage'i kaldırmak için indirdiğiniz dosyayı silmeniz yeterlidir.

## Güncelleme ve kaldırma

Yeni sürüm çıktığında yeni DEB veya RPM dosyasını aynı kurulum komutuyla
kurabilirsiniz. Paket yöneticisi mevcut kurulumu günceller. AppImage için eski
dosyayı yenisiyle değiştirin.

```bash
# Ubuntu/Debian
sudo apt remove confissh

# Fedora
sudo dnf remove confissh
```

Kaldırma işlemi `~/.ssh/config` dosyasına veya
`~/.config/confissh` altındaki uygulama bilgileri ve yedeklere dokunmaz.
Bu veriler istenmiyorsa kullanıcı tarafından ayrıca silinmelidir.


[Tanıtıma dön](../README.tr.md) · [English installation guide](INSTALL.md)
