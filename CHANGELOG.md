# Değişiklik Notları (Changelog)

## [Unreleased]

### Yapılan Değişiklikler

#### 2025-01-XX - connector.py readCs() Metodu Düzeltildi

**Dosya:** `scripts/connector.py`

**Sorun:**
- `readCs()` metodu çok basitti, sadece 1024 byte okuyordu
- Timeout yoktu, Unity yanıt vermezse sonsuz bekliyordu
- Unity state newline ile bitmiyor, state tam okunmayabiliyordu
- State bir sonraki mesajla karışabiliyordu

**Çözüm:**
- Timeout eklendi (2 saniye)
- Buffer mekanizması eklendi, state tam okunana kadar bekliyor
- State 13 değer içerir (12 virgül), bu kontrol ediliyor
- Maksimum iterasyon sayısı ile sonsuz döngü koruması
- Hata yönetimi iyileştirildi (ConnectionError, TimeoutError)

**Etki:**
- Unity'den gelen state artık tam olarak okunuyor
- Timeout sayesinde program donmuyor
- Senkronizasyon sorunları azaldı

#### 2025-01-XX - env.py initialStart() ve step() Gereksiz Parametreler Kaldırıldı

**Dosya:** `scripts/env.py`

**Sorun:**
- `initialStart()` 14 parametre gönderiyordu ama Unity sadece 6 parametre bekliyor (mode, x, y, z, pitch, yaw)
- `step()` 13 parametre gönderiyordu ama Unity sadece 4 parametre bekliyor (mode, pitch, yaw, thrust)
- Roll parametresi gönderiliyordu ama Unity henüz roll desteği yok

**Çözüm:**
- `initialStart()`: Sadece 6 parametre gönderiyor (1, x, y, z, pitch, yaw)
- `step()`: Sadece 4 parametre gönderiyor (0, pitch, yaw, thrust) - roll kaldırıldı
- Debug print'leri eklendi

**Etki:**
- Protokol uyumsuzluğu giderildi
- Unity mesajları doğru parse edebiliyor
- Gereksiz veri gönderimi azaldı

**Not:** Unity henüz roll kontrolünü desteklemiyor. Roll desteği eklendiğinde Unity tarafı da güncellenmeli.

#### 2025-01-XX - Roll Kontrolü Eklendi (4 Action)

**Dosyalar:** `rocket-env/Assets/Scripts/env.cs`, `scripts/env.py`

**Değişiklik:**
- Unity'de `ApplyPhysics()` metoduna roll parametresi eklendi
- Unity'de doAction() case 0: 4 parametre yerine 5 parametre bekliyor (mode, pitch, yaw, thrust, roll)
- Python'da step() fonksiyonu artık 4 parametre gönderiyor (mode, pitch, yaw, thrust, roll)
- Roll kontrolü transform.up ekseninde tork uyguluyor

**Etki:**
- Agent artık 4 action kontrolü yapabiliyor (pitch, yaw, thrust, roll)
- Roket kendi ekseni etrafında dönebilir (roll)
- Daha fazla kontrol özgürlüğü

#### 2026-01-02 - Açılı Ayaklar İçin Gerçek Ayak Pozisyonu Hesaplama (DENEYSEL)

**Dosya:** `rocket-env/Assets/Scripts/env.cs`

**Sorun:**
- `feetOffset` hesaplaması sadece roket gövdesinin alt ucunu (collider'ın yarı yüksekliği) kullanıyordu
- Ancak roketin ayakları açılı bir şekilde gövdeden çıkıyor (30° açıyla)
- Bu yüzden ayakların gerçek temas noktası, gövdenin alt ucundan daha aşağıda
- `dy` (yükseklik) ölçümü yanlış olabilir ve iniş kontrolü etkilenebilir

**Çözüm:**
- `FindLowestLegPoint()` metodu eklendi
- Bu metod tüm child objeleri tarayarak "Leg" içeren objeleri buluyor
- Her bir ayağın collider'ını kontrol ediyor ve `bounds.min.y` ile en alt noktayı hesaplıyor
- Collider yoksa, açılı ayaklar için yaklaşık hesaplama yapıyor (30° açı varsayımı)
- `getStates()` metodunda artık `feetOffset` yerine `FindLowestLegPoint()` kullanılıyor

**Etki:**
- `dy` (yükseklik) ölçümü artık ayakların gerçek temas noktasına göre yapılıyor
- İniş kontrolü daha doğru çalışmalı

**ÖNEMLİ NOT:**
- Bu değişiklik deneyseldir ve test edilmesi gerekiyor
- Eğer sorun çıkarsa (hata, yanlış hesaplama, performans sorunu) geri alınabilir
- Unity'de ayakların collider yapısı veya hiyerarşisi farklıysa kod uyarlanmalı
- Eğer sorun çıkarsa `getStates()` metodunda `FindLowestLegPoint()` yerine eski `transform.TransformPoint(feetOffset)` kullanılabilir

#### 2026-01-02 - State Normalizasyonu Eklendi (Log-compress Yöntemi)

**Dosya:** `scripts/env.py`

**Sorun:**
- State'ler normalize edilmiyordu, raw değerler neural network'e gidiyordu
- Farklı ölçeklerdeki state'ler (dx/dz: [-45, +45], dy: [0, 100], hızlar: farklı ölçekler) eğitimi zorlaştırıyordu
- Büyük değerli özellikler (dy, hızlar) daha baskın görünebiliyordu

**Çözüm:**
- `normalize_state()` metodu eklendi
- `log_norm()` fonksiyonu eklendi (log-compress normalizasyon)
- State normalizasyon ölçekleri tanımlandı:
  - `dx_scale = 45.0` (yatay pozisyon limiti)
  - `dy_scale = 50.0` (yükseklik ölçeği)
  - `v_scale = 25.0` (doğrusal hız ölçeği, m/s)
  - `w_scale = 4.0` (açısal hız ölçeği, rad/s)

**Normalizasyon Stratejisi:**
- **dx, dz**: Basit normalize (`/45`) → `[-1, 1]`
- **dy**: Log-compress (scale=50) → `[-1, 1]`
- **vx, vy, vz**: Log-compress (scale=25 m/s) → `[-1, 1]`
- **wx, wy, wz**: Log-compress (scale=4 rad/s) → `[-1, 1]`
- **qx, qy, qz, qw**: Zaten `[-1, 1]` aralığında, dokunulmadı

**Etki:**
- Agent'a gönderilen state'ler artık normalize ediliyor
- Eğitim daha stabil olmalı
- Farklı ölçeklerdeki state'ler eşit ağırlıkta

**ÖNEMLİ NOTLAR:**
- `compute_reward_done()` raw state kullanmaya devam ediyor (reward hesaplaması için doğru)
- `step()` ve `readStates()` normalize edilmiş state döndürüyor
- **LOGLARDA NORMALIZE EDİLMİŞ STATE'LER GÖRÜNECEK**: STATE_LOG_FILE, DETAILED_LOG_FILE ve konsol çıktılarında normalize edilmiş değerler (`[-1, 1]` aralığında) görünecek, raw değerler değil
- Log-compress yöntemi: Düşük değerler hassas kalır, yüksek değerler aşırı saturate olmaz
- Detaylı tartışma için `state_normalization_discussion.txt` dosyasına bakın

---