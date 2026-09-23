# ConfiSSH

[English README](README.md)

Ubuntu için GTK tabanlı OpenSSH bağlantı yöneticisi. Terminalde normal
`ssh host-adı` kullanımı korunur. SSH ayarları SSH dosyalarında, uygulama bilgileri
ayrı JSON dosyasında tutulur.

## Veri yapısı

- `~/.ssh/config` ve Include dosyaları: HostName, User, Port, IdentityFile,
  ProxyJump, tüneller ve diğer standart SSH direktifleri.
- `~/.config/confissh/connections.json`: UUID tabanlı bağlantılar, gruplar,
  ortamlar, etiketler, notlar, favoriler ve son kullanım zamanı.
- `~/.config/confissh/preferences.json`: tema, dil, panel görünümü ve sıralama tercihleri.
- `~/.config/confissh/backups/`: SSH dosyaları ve JSON verisinin birlikte
  alınmış, zaman damgalı yedekleri. Yedekler de hassas bağlantı bilgisi içerir
  ve 0600 izinleriyle yazılır. Otomatik silinmezler.

`XDG_CONFIG_HOME` desteklenir. Yeni sürüm eski uygulama metadata biçimini veya
eski tercih kayıtlarını dönüştürmez. SSH dosyalarındaki diğer yorumlar korunur.
İlk açılışta kimliği olmayan hostlara UUID eklenir ve işlemden önce yedek alınır.
Bu bağlantılar başlangıçta bir gruba atanmadan Tüm bağlantılar içinde görünür.

SSH dosyasına eklenen tek uygulama alanı bir yorumdur:

```ssh-config
# confissh-key: 24e6b5d6-99c2-43dd-abcc-ad7eeef59a32
Host prod-api
  HostName 192.0.2.12
  User deploy
  IdentityFile ~/.ssh/id_ed25519
```

Uygulama dosyasının örnek yapısı:

```json
{
  "version": 1,
  "groups": {
    "a0d217fa-861c-42ad-b2b9-d13ba50153c2": {
      "name": "Operations",
      "order": 0
    }
  },
  "environments": {
    "b0d217fa-861c-42ad-b2b9-d13ba50153c2": {
      "name": "Production",
      "color": "#e35d6a"
    }
  },
  "connections": {
    "24e6b5d6-99c2-43dd-abcc-ad7eeef59a32": {
      "group_id": "a0d217fa-861c-42ad-b2b9-d13ba50153c2",
      "environment_id": "b0d217fa-861c-42ad-b2b9-d13ba50153c2",
      "tags": ["redis", "mysql"],
      "note": "Ana sunucu",
      "favorite": true
    }
  }
}
```

Grup ve ortam adları kimlik değildir. Ad değiştirmek bağlantı ilişkilerini veya
SSH dosyasını değiştirmez. Host adı/dosya konumu değişse de aynı bağlantı UUID'si
metadata'yı korur. Çoğaltma yeni UUID üretir. Dışarıdan kopyalanmış yinelenen
kimliklerde ilk host kimliğini korur, sonrakilere yeni kimlik atanır.
Config'ten kaldırılmış bağlantıların metadata kayıtları, aynı kimlikle geri
eklenme ve yedekten dönüş için saklanır.

## Kullanım

- Bağlantı formunda SSH alanları ve config dosyası Bağlantı sekmesindedir.
  Grup, ortam, etiketler ve not Organizasyon sekmesinde düzenlenir.
- Sol menüde Gruplar başlığındaki + ile bağlantısı olmayan bir grup oluşturun.
  Bağlantı satırını soldaki grubun üzerine sürükleyip bırakarak taşıyın.
  Satıra sağ tık → Grubu değiştir ile de taşıyabilir veya grup atamasını kaldırabilirsiniz.
  Grup atamasını kaldırmak için bağlantı düzenleme formunda Grupsuz seçilir.
  Taşıma işlemi yalnızca JSON'daki
  group_id alanını değiştirir; SSH dosyası ve bağlantının UUID'si korunur.

- Grup üzerinde sağ tık → Yeniden adlandır / Grubu sil: ad değiştirme veya
  bağlantıları başka gruba ya da Grupsuz'a taşıyarak silme. Boş gruplar sol
  menüde kalır; oluşturma için Gruplar başlığındaki + kullanılır.
  Sağ tık → Rengi düzenle ile grup adına özel renk verilebilir. Özel renk
  kapatılırsa tema rengine dönülür; bağlantının ortam rengi ayrı kalır.
- Gruplar sürükle-bırak ve sağ tık menüsüyle sıralanır. Üç nokta menüsünden
  Alfabetik sıra veya Özel sıra seçilir. Alfabetik görünüm özel sırayı silmez;
  tekrar Özel sıra seçilince elle düzenlenen sıra geri gelir. Sürükleme özel
  sıralamaya geçirir. Özel sıra JSON içindeki grup kayıtlarına yazılır;
  SSH Host sırası değişmez. Gruba atanmamış bağlantılar Tüm bağlantılar içinde
  görünür; sol menüde ayrı bir Grupsuz grubu bulunmaz.
- Ayarlar → Ortamlar: ortam oluşturma, ad/renk düzenleme ve kullanılmayan
  ortamı silme. Bağlantıda grup ve ortam UUID tabanlı açılır listelerden seçilir.
  İlk açılışta Production (kırmızı), Sandbox (sarı) ve Development (yeşil)
  örnek olarak oluşturulur; bağlantılara otomatik atanmaz. Mevcut ortamlar
  korunur ve kullanıcı tarafından silinen örnekler yeniden eklenmez.
  Varsayılanlara dön düğmesi eksik örnekleri ekler ve aynı adlı ortamların
  renklerini sıfırlar. Özel/yeniden adlandırılmış ortamlar ve bağlantı atamaları
  korunur; bu işlem mevcut kurulumlarda da kullanılabilir.
- Etiketler virgülle ayrılır: rabbit, redis, mysql. Rozetler bağlantı adresinin
  yanında görünür ve aramaya dahildir. Ortam rengi satırın solunda gösterilir.
- Favoriler sol menüde ayrı görünür, diğer listelerde de üstte sıralanır.
- ProxyJump alanında mevcut etkin SSH bağlantılarından seçim yapılabilir
  (Include dosyaları dahil). Özel adresler ve virgülle ayrılmış atlama zincirleri
  elle yazılabilir; alanı boş bırakmak ProxyJump direktifini kaldırır.
  Son kullanılanlar terminal başlatıldığında güncellenir; uzak bağlantının
  başarıyla kurulduğu anlamına gelmez.
- Bağlantı, Gelişmiş ve Tüneller sekmelerinde SSH ayarları düzenlenir.
  Yeni bağlantı oluşturulurken hedef Include dosyası seçilebilir.
- Kayıttan önce SSH ve metadata farkı birlikte gösterilir. İptal dosyaya yazmaz.
  Dış değişiklik varsa Ctrl+R ile yeniden yüklemek gerekir.
- Ayarlar → Yedekler çalışma alanının SSH dosyalarını ve metadata'sını birlikte
  geri yükler. Önce fark gösterilir, mevcut durum da yedeklenir.
  Yedekteki kaynak dosya artık çalışma alanında yoksa geri yükleme durdurulur.
  Seçili yedek veya tüm yedekler onaydan sonra kalıcı silinebilir. Bu işlem
  geri alınamaz; mevcut bağlantılar ve ayarlar silinmez.
- Arama ilk karakterden itibaren anında uygulanır.
- Tema, dil ve kısayollar Ayarlar'dadır. Dil için sistem varsayılanı, English veya Türkçe seçilebilir; dil değişikliği açık pencereye anında uygulanır. Ctrl+F arama, Ctrl+N ekleme, Ctrl+R yeniden yükleme, Esc aramayı temizleme.

Kayıtlar kilit, atomik dosya değişimi ve işlem günlüğü kullanır. SSH/JSON
yazımlarından biri başarısız olursa önceki durum geri alınır. Kesintiye uğramış
işlem sonraki açılışta geri alınır; araya dış değişiklik girdiyse otomatik geri
alma durur ve `connections.pending.json` ile yedeklerin incelenmesi istenir.
Birden çok dosya işletim sistemi düzeyinde tek atomik işlem değildir.

Include dosyaları glob ve döngü kontrolüyle keşfedilir; bağıl yollar ~/.ssh
altında çözülür. Host/Match koşullarının etkin sonucu ana dosya üzerinden
`ssh -G` ekranında hesaplanır. Bu komut Match exec çalıştırabileceği için
çalıştırmadan önce onay gösterilir.

## Son kullanıcı kurulumu

Hazır paketleri GitHub deposundaki **Releases** sayfasından indirin. Kaynak kodu
indirmeniz veya `make` çalıştırmanız gerekmez.

### Ubuntu ve Debian (.deb)

İndirdiğiniz DEB dosyasının bulunduğu dizinde:

```bash
sudo apt install ./confissh_0.1.0_amd64.deb
```

`apt`, gerekli Python, GTK 3 ve OpenSSH paketlerini otomatik olarak kurar.
Kurulumdan sonra uygulama menüsünden **ConfiSSH** seçilebilir veya terminalde
şu komut çalıştırılabilir:

```bash
confissh
```

### Fedora (.rpm)

İndirdiğiniz RPM dosyasının bulunduğu dizinde:

```bash
sudo dnf install ./confissh-0.1.0-1.fc42.noarch.rpm
```

`dnf`, gerekli Python, GTK 3 ve OpenSSH paketlerini otomatik olarak kurar.
Kurulumdan sonra uygulama menüsünden veya `confissh` komutuyla açabilirsiniz.

### AppImage

AppImage sistem paket yöneticisine kurulum yapmaz. Bu ince paket Python, GTK 3
ve OpenSSH istemcisini sistemden kullanır. Ubuntu/Debian üzerinde gerekli
çalışma zamanı paketleri şöyle kurulabilir:

```bash
sudo apt install python3 python3-gi gir1.2-gtk-3.0 openssh-client
chmod +x ConfiSSH-0.1.0-x86_64.AppImage
./ConfiSSH-0.1.0-x86_64.AppImage
```

Fedora üzerinde:

```bash
sudo dnf install python3 python3-gobject gtk3 openssh-clients
chmod +x ConfiSSH-0.1.0-x86_64.AppImage
./ConfiSSH-0.1.0-x86_64.AppImage
```

AppImage'i kaldırmak için indirdiğiniz dosyayı silmeniz yeterlidir.

### Güncelleme ve kaldırma

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

## Geliştirme ve doğrulama

```bash
sudo apt install python3 python3-gi python3-cairo gir1.2-gtk-3.0 \
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
sudo apt install ./dist/confissh_0.1.0_amd64.deb
```

Fedora 42 üzerinde RPM oluşturmak ve kurmak için:

```bash
sudo dnf install rpm-build python3-devel
make rpm
sudo dnf install ./dist/confissh-0.1.0-1.fc42.noarch.rpm
```

Ubuntu üzerinde Docker ile aynı Fedora RPM'si üretilebilir:

```bash
make rpm-docker
```

AppImage oluşturmak ve çalıştırmak için:

```bash
sudo apt install squashfs-tools curl
make appimage
./dist/ConfiSSH-0.1.0-x86_64.AppImage
```

AppImage, uygulama kodunu tek dosyada taşır ve sandbox kullanmadığı için
`~/.ssh` ile sistem terminaline doğrudan erişir. Bu ince paket sistemde Python
3.10+, PyGObject, GTK 3 ve OpenSSH istemcisinin kurulu olmasını bekler; eksikse
çalıştırırken dağıtıma uygun kurulum komutunu gösterir. İlk derlemede resmî
AppImage type-2 runtime `build/appimage` altına indirilir ve sabit SHA-256
özetiyle doğrulanır. `APPIMAGE_RUNTIME`
ile önceden indirilmiş bir runtime da verilebilir. x86_64 ve aarch64 desteklenir.

Üç biçimi birlikte üretmek için gerekli araçlar kurulduktan sonra `make packages`
kullanılabilir. Çıktılar `dist/` dizinine yazılır.

## CI/CD ve sürümleme

Her push ve pull request'te birim testleri, statik kontroller, GTK iş akışı,
gerçek sürükle-bırak testi ve üç paket biçiminin derlenmesi GitHub Actions ile
doğrulanır. Derleme çıktıları kaynak kontrolüne alınmaz.

Yeni sürüm hazırlamak için `confissh/__init__.py` ve `CHANGELOG.md`
güncellenip değişiklikler ana dala alınır. Ardından sürümle aynı etiketi itin:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Etiket iş akışı DEB, Fedora 42 RPM ve AppImage dosyalarını üretir; SHA-256
özetleriyle birlikte GitHub Release olarak yayımlar. Katkı süreci
`CONTRIBUTING.md`, hassas hata bildirimleri ise `SECURITY.md` içinde açıklanır.
