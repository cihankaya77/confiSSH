# ConfiSSH — Linux için SSH Bağlantı Yöneticisi

**Sunucularınızı düzenleyin, bağlantınızı bulun ve terminalde açın.**

ConfiSSH, Linux için ücretsiz ve açık kaynaklı bir SSH masaüstü uygulamasıdır.
OpenSSH bağlantılarınızı yönetin, sunucularınızı gruplara ayırın ve SSH
anahtarlarınızı tek yerden bulun. Mevcut `~/.ssh/config` dosyanızla çalışır;
terminalde alıştığınız `ssh host-adı` komutunu kullanmaya devam edebilirsiniz.

**[ConfiSSH indir](https://github.com/cihankaya77/confiSSH/releases/latest)** ·
[Kurulum rehberi](docs/INSTALL.tr.md) ·
[English](README.md) ·
[Sorun bildir](https://github.com/cihankaya77/confiSSH/issues)

Linux masaüstü · DEB / RPM / AppImage · English / Türkçe · [MIT lisansı](LICENSE)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/confissh-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/screenshots/confissh-light.png">
  <img alt="ConfiSSH SSH bağlantı yöneticisinde sunucu grupları, favoriler, arama ve bağlan düğmeleri" src="docs/screenshots/confissh-light.png">
</picture>

## ConfiSSH ile neler yapabilirsiniz?

- **Adres ezberlemeden bağlanın.** Sunucu adı, IP, kullanıcı veya etiketle arayın.
  **Bağlan** düğmesi SSH bağlantısını sistem terminalinizde açar.
- **İş, ev ve bulut sunucularınızı düzenleyin.** Gruplar oluşturun, bağlantıları
  sürükleyip taşıyın. Ortam renkleri, etiketler ve notlarla sunucuları ayırt edin.
  Sık kullandığınız bağlantılara favorilerden veya son kullanılanlardan ulaşın.
- **SSH ayarlarını arayüzden düzenleyin.** Bağlantı ekleyin veya çoğaltın;
  bilgisayarınızdan kimlik dosyası seçin. Port, atlama sunucusu (ProxyJump),
  SSH tünelleri ve bağlantıyı canlı tutma ayarlarını yapılandırın.
- **SSH anahtarlarını bulun ve kopyalayın.** `~/.ssh`, bağlantılarda tanımlı anahtar
  yolları veya seçtiğiniz klasörlerdeki açık ve özel anahtarları listeleyin.
  Anahtar içeriğini ya da dosya yolunu kopyalayın.
- **Mevcut SSH düzeninizi kullanın.** ConfiSSH, OpenSSH yapılandırma dosyanızı ve
  `Include` ile eklenen dosyaları okur. Bağlantılarınız komut satırında da çalışır.
- **Önceki ayarlarınıza dönün.** Değişiklikler otomatik olarak yedeklenir.
  **Ayarlar → Yedekler** bölümünden bir yedeği inceleyip geri yükleyin.
- **Görünümü kendinize göre ayarlayın.** Açık, koyu veya sistem temasını seçin;
  arayüzü Türkçe ya da İngilizce kullanın.

Ev laboratuvarınız, VPS'iniz veya iş sunucularınız için kullandığınız bağlantıları,
her birinin ayarlarıyla birlikte aranabilir bir listede tutabilirsiniz.

## İndirme ve kurulum

**[Son sürümden](https://github.com/cihankaya77/confiSSH/releases/latest)**
sisteminize uygun paketi indirin:

| Linux masaüstünüz | İndirilecek paket | Kurulum adımları |
| --- | --- | --- |
| Ubuntu veya Debian | `.deb` | [apt ile kurulum](docs/INSTALL.tr.md#ubuntu-ve-debian-deb) |
| Fedora | `.rpm` | [dnf ile kurulum](docs/INSTALL.tr.md#fedora-rpm) |
| Diğer Linux masaüstleri | `.AppImage` | [Gerekli paketler ve çalıştırma](docs/INSTALL.tr.md#appimage) |

Rehberdeki indirme komutları x86_64 / AMD64 paketlerini seçer. AppImage,
sistemdeki Python, GTK ve OpenSSH paketlerini kullanır; gerekli paketler
kurulum rehberinde listelenmiştir.

Kurulumdan sonra uygulama menüsünden **ConfiSSH**'ı açın. DEB veya RPM
kurulumunda terminalden `confissh` komutunu da kullanabilirsiniz.

[Güncelleme ve kaldırma](docs/INSTALL.tr.md#güncelleme-ve-kaldırma)

## İlk bağlantınız

1. **ConfiSSH'ı açın.** `~/.ssh/config` içindeki mevcut bağlantılar otomatik görünür.
2. **Bağlantı ekle'ye tıklayın.** Kısa bir host adı, sunucu adresi ve kullanıcı adı
   girin. Anahtarla bağlanıyorsanız kimlik dosyanızı seçin.
3. **İsterseniz düzenleyin.** Organizasyon sekmesinden grup veya ortam seçin;
   etiket ve not ekleyin.
4. **Kaydedin ve bağlanın.** ConfiSSH terminalinizi açarak SSH'ı başlatır.
   Parola, anahtar parolası ve sunucu kimliği soruları terminalde OpenSSH
   tarafından gösterilir.

Bağlantının SSH komutunu kopyalayıp kendiniz de çalıştırabilirsiniz.

## Bağlantılarınızı kolay bulun

Gruplar başlığının yanındaki **+** ile grup oluşturun; bağlantıları üzerine
sürükleyin. Bir gruba sağ tıklayarak adını veya rengini değiştirebilir,
bağlantılarını yönetebilirsiniz. Sabit **Grupsuzlar** satırı grubu olmayan
bağlantıları gösterir; böyle bir bağlantı kalmadığında gizlenir. Bir bağlantıyı
buraya sürüklemek grup atamasını kaldırır.

Sık kullandığınız sunucuları favorilere ekleyin, `veritabanı` veya `homelab` gibi
aranabilir etiketler kullanın. **Ayarlar → Ortamlar** bölümünden üretim ve
geliştirme ortamlarını ayırt edecek renkler belirleyin.

| Bağlantı ayarları | Gruplar, etiketler ve notlar |
| :--: | :--: |
| ![Sunucu, kullanıcı, port ve kimlik dosyası alanlarını gösteren SSH bağlantı düzenleyicisi](docs/screenshots/confissh-editor.png) | ![SSH bağlantıları için grup, ortam, etiket ve not alanları](docs/screenshots/confissh-organization.png) |

| Görünüm | Yedekler |
| :--: | :--: |
| ![Açık ve koyu tema ile dil ayarları](docs/screenshots/confissh-settings.png) | ![SSH yapılandırma yedeklerini listeleme ve geri yükleme](docs/screenshots/confissh-backups.png) |

## Sık sorulan sorular

**Mevcut SSH ayarlarımı kullanabilir miyim?** Evet. ConfiSSH, `~/.ssh/config` ve
bu dosyaya dahil edilen dosyaları okur. İlk açılışta yapılandırmanızı yedekler
ve bağlantıları takip etmek için küçük kimlik yorumları ekler. Alıştığınız SSH
komutları çalışmaya devam eder.

**Uygulamanın içinde terminal var mı?** Bağlan düğmesi sisteminizde kurulu bir
terminali açar. Desteklenen bir terminal bulunamazsa SSH komutunu kopyalayabilirsiniz.

**Bir değişikliği geri alabilir miyim?** **Ayarlar → Yedekler** bölümünden
bağlantı ayarlarını ve gruplandırmayı birlikte inceleyip geri yükleyebilirsiniz.
Yedekler siz silene kadar bilgisayarınızda tutulur.

**Ayarlarım nerede saklanıyor?** SSH ayarları SSH dosyalarınızda kalır. Gruplar,
notlar, tercihler ve yedekler `~/.config/confissh` altında saklanır. Uygulamayı
kaldırmak bu dosyaları silmez.

**Windows veya macOS desteği var mı?** Uygulama ve kurulum paketleri Linux
masaüstleri için hazırlanmıştır.

## Yardım ve proje bilgileri

- [Hata bildirin veya özellik önerin](https://github.com/cihankaya77/confiSSH/issues).
- [Değişiklik günlüğünü](CHANGELOG.md) ve [sürüm notlarını](https://github.com/cihankaya77/confiSSH/releases) inceleyin.
- Geliştirme için [katkı rehberine](CONTRIBUTING.md), [derleme adımlarına](docs/DEVELOPMENT.tr.md)
  ve [teknik başvuruya](docs/TECHNICAL.tr.md) bakın.
- Katılmadan önce [davranış kurallarını](CODE_OF_CONDUCT.md) okuyun.
- Güvenlik açıkları için [güvenlik politikasını](SECURITY.md) izleyin.

ConfiSSH, [MIT lisansıyla](LICENSE) sunulan ücretsiz ve açık kaynaklı bir projedir.
