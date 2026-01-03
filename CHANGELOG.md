# Değişiklik Notları (Changelog)

## [Unreleased]

### Yapılan Değişiklikler

#### 2026-01-XX - Reward Function Yeniden Tasarlandı (Hız Kontrolü ve Shaping İyileştirmeleri)

**Dosya:** `scripts/env.py`

**Sorun:**
- Vertical velocity penalty sadece `dy < 15m` iken aktifti, yüksek irtifada hız kontrolü yoktu
- Agent serbest düşüş yapıp son anda fren yapmaya çalışıyordu
- Reward scaling çok aggressive (0.1x) → shaping signal'lar görünmüyordu
- Distance penalty çok dominant (0.05), hız kontrolüne yer bırakmıyordu
- Horizontal velocity penalty yetersizdi (0.03), drift sorunu devam ediyordu
- Success criteria çok gevşekti (vy <= 4.5 m/s), agent bunu bile tutturamıyordu
- Tilt penalty/bonus dengesizdi (-0.10 vs +0.04)

**Çözüm:**

1. **Vertical Velocity - Her İrtifada Aktif (Progressive):**
   - Artık tüm irtifalarda hız kontrolü var (sadece dy < 15m değil)
   - Progressive penalty: İrtifa azaldıkça ceza artıyor
   - Formula: `altitude_factor = 1.0 + (15.0 / (dy + 1.0))`
   - Agent yüksek irtifada bile erken fren yapacak

2. **Reward Scaling Artırıldı:**
   - 0.1x → 0.5x (5x artış)
   - Shaping signal'lar artık görünür olacak
   - Agent intermediate reward'ları görebilecek

3. **Distance Penalty Azaltıldı:**
   - 0.05 → 0.02 (hız kontrolüne yer açmak için)

4. **Horizontal Velocity Penalty Artırıldı:**
   - 0.03 → 0.06 (drift'i azaltmak için, 2x)

5. **Tilt Penalty/Bonus Dengelendi:**
   - Penalty: -0.10 → -0.08
   - Bonus: +0.04 → +0.08 (eşit ağırlıkta)

6. **Yere Yaklaşma Bonusu Eklendi:**
   - `dy < 20m` iken exponansiyel bonus
   - Agent'ı inişe teşvik eder

7. **Yavaş İniş Bonusu Eklendi:**
   - `vy > -2 m/s` iken bonus
   - Yumuşak inişi ödüllendirir

8. **Success Criteria Sıkılaştırıldı:**
   - `vy <= 4.5` → `2.5 m/s` (daha yumuşak iniş)
   - `v_h <= 3.0` → `2.0 m/s` (daha kontrollü)
   - `dist_h <= 4.0` → `3.0 m` (daha hassas iniş)

**Etki:**
- Agent artık yüksek irtifada bile hız kontrolü yapacak
- Progressive penalty ile erken fren teşvik edilecek
- Shaping signal'lar görünür olacak (0.5x scaling)
- Yumuşak iniş bonusu ile daha kontrollü iniş
- Multi-objective optimization daha dengeli çalışacak
- Drift sorunu azalacak (horizontal velocity penalty 2x)

**Notlar:**
- İlk başta success rate düşük olabilir (daha sıkı criteria)
- Progressive velocity penalty test edilmeli (hover davranışı riski)
- Reward scaling artışı value loss patlaması riski taşır (ama 0.5x güvenli aralıkta)
- Detaylı analiz için `reward_function_detailed_analysis.txt` dosyasına bakın

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
- `step()` ve `readStates()` raw state döndürüyor (loglar için)
- Normalize işlemi `train_main.py` içinde agent'a gönderilmeden önce yapılıyor
- **LOGLARDA RAW STATE'LER GÖRÜNECEK**: STATE_LOG_FILE, DETAILED_LOG_FILE ve konsol çıktılarında raw değerler (gerçek fiziksel değerler) görünecek
- Normalize edilmiş state'ler sadece agent'a gönderilirken kullanılıyor
- Log-compress yöntemi: Düşük değerler hassas kalır, yüksek değerler aşırı saturate olmaz
- Detaylı tartışma için `state_normalization_discussion.txt` dosyasına bakın

---