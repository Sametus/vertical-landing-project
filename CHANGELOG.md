# Değişiklik Notları (Changelog)

## [Unreleased]

### Yapılan Değişiklikler

#### 2026-01-10 - Curriculum Learning: High Altitude Training Stage

**Dosya:** `scripts/env.py`

**Değişiklik:**
- Yüksek irtifa eğitim aşamasına geçildi
- Başlangıç yüksekliği: `init_y_min = 44.5m`, `init_y_max = 47.0m`
- Yüksek irtifa ödül/ceza eşikleri güncellendi:
  - `height_penalty` threshold: `43.0m` → `50.0m`
  - `high_altitude_penalty` threshold: `47.0m` → `48.0m`
  - `CeilingHit` threshold: `53.0m` → `54.0m`
- `max_steps`: `975` → `1000`

**Etki:**
- Agent artık 44-47m yükseklik aralığında eğitiliyor
- Curriculum learning'in son aşaması

---

#### 2026-01-10 - Low Altitude Stage Model Checkpoints

**Dosya:** `models/v*-low/`

**Değişiklik:**
- Low stage için 17 checkpoint eklendi (v1-low to v17-low)
- Her checkpoint: model, state, ve env-icerik.txt içeriyor
- Curriculum learning'in farklı aşamalarında model kayıtları

**Etki:**
- Low stage eğitimi için referans modeller mevcut
- Aşama bazlı geri dönüş imkanı

---

#### 2026-01-09 - Training Analysis Scripts: Update Analysis ve Thrust Requirements

**Dosyalar:** 
- `scripts/analyze_updates_from_1361.py`
- `scripts/analyze_thrust_requirements.py`

**Özellikler:**
- **Update Analysis**: Belirli bir update'ten itibaren her update için başarı oranı ve ortalama başlangıç yüksekliği analizi
- **Thrust Analysis**: Teorik ve gerçek thrust kullanımı analizi, başarılı iniş olasılığı hesaplama

**Etki:**
- Eğitim sürecini daha iyi anlama
- Thrust yeterliliği kontrolü

---

#### 2026-01-09 - High Altitude Failure Analysis Scripts

**Dosyalar:**
- `scripts/analyze_high_altitude_failures.py`
- `scripts/analyze_spin_collapse.py`
- `scripts/analyze_crash_spike.py`
- `scripts/analyze_start_altitude_success.py`

**Özellikler:**
- Yüksek irtifa başarısızlık sebepleri analizi (40m+, 45m+)
- Spin çökmesi analizi (policy collapse tespiti)
- Crash patlaması analizi
- Başlangıç yüksekliği bazlı başarı oranı analizi

**Etki:**
- Yüksek irtifa performans problemlerini anlama
- Policy collapse tespiti ve geri dönüş önerileri

---

#### 2026-01-04 - Training Log Analizi ve Görselleştirme (Matplotlib/Seaborn)

**Dosya:** `scripts/analyze_training.py`

**Özellikler:**
- Matplotlib ve Seaborn kullanarak 6 farklı grafik:
  1. Success Rate Trendi (Update bazlı)
  2. Başlangıç Yüksekliği vs Başarı Oranı
  3. Başlangıç Yüksekliği Scatter Plot
  4. Termination Reasons Dağılımı
  5. Loss Trend (Policy, Value, Total)
  6. Return Distribution
- PNG formatında görsel çıktı
- CSV sütun kayması otomatik düzeltme
- Windows encoding desteği

**Dosyalar:** `images/*.png`

**Etki:**
- Eğitim sürecini görsel olarak takip etme
- README'ye görseller eklenebilir

---

#### 2026-01-04 - Analiz Dosyaları Organizasyonu

**Değişiklik:**
- Tüm `.txt` analiz dosyaları `analyses/` klasörüne taşındı
- Daha organize dosya yapısı

**Etki:**
- Proje yapısı daha temiz ve organize

---

#### 2026-01-04 - Play Test Script Geliştirmeleri

**Dosya:** `scripts/play_test.py`

**Eklenen Özellikler:**
- **Stabilizasyon Kontrolü**: Serbest düşüş sırasında roketin dengede kalması için otomatik RCS kontrolü
  - Tilt ve spin kontrolü
  - Yan yatma durumunda agresif düzeltme
- **Detaylı Action/State Formatı**: Thrust yüzde ve birim (kN), RCS değerleri
- **Temiz Loglama**: Episode yerine "Test" terminolojisi, sadece episode sonu loglama
- **Success Sonrası Serbest Düşüş**: Başarılı iniş sonrası roketin yere düşmesi ve yeni test başlatma
- **Training Mantığına Uyum**: Step-step ilerleme, time.sleep yok

**Sorunlar ve Çözümler:**
- Ardışık başlatma sorunu: Serbest düşüş sonrası state temizleme kaldırıldı, training mantığına uyum
- Roket donma sorunu: Stabilizasyon kontrolü ile çözüldü
- Time.sleep kaldırıldı: Training mantığına uygun step-step ilerleme

**Etki:**
- Model testleri daha güvenilir ve gerçekçi
- Serbest düşüş sırasında roket stabil kalıyor

---

#### 2026-01-04 - Curriculum Learning: Medium Stage Güncellemeleri

**Dosya:** `scripts/env.py`

**Değişiklik:**
- Medium stage parametreleri güncellendi
- Başlangıç yüksekliği: 5-20m aralığı
- Rollout length analizi ve optimizasyonu

**Etki:**
- Curriculum learning'in ikinci aşaması tamamlandı

---

#### 2026-01-04 - Training Analysis Güncellemeleri

**Değişiklikler:**
- Rollout length analizi eklendi
- Loss calculation doğrulaması
- Success rate düşüşü analizi
- Console output sorunu dokümantasyonu
- Update 781-970 için kapsamlı analizler

---

#### 2026-01-04 - Reward Function: Dead Code Temizliği ve Exponential Center Bonus

**Dosya:** `scripts/env.py`

**Değişiklikler:**
- `compute_reward_done()` içindeki ulaşılamaz dead code kaldırıldı
- Exponential merkeze yaklaşma bonusu eklendi (dead code analizinden)
- OutOfBounds threshold: `25m` → `35m` → `20m`
- Success threshold'ları gevşetildi
- Success bonus artırıldı

**Etki:**
- Kod daha temiz ve bakımı kolay
- Merkeze yaklaşma ödüllendiriliyor

---

#### 2026-01-04 - BottomSensor Implementation ve Play Test Fix

**Dosyalar:**
- `rocket-env/Assets/Scripts/env.cs`
- `scripts/play_test.py`

**Değişiklikler:**
- Unity'de `feetOffset` yerine `BottomSensor` Transform kullanımına geçildi
- Daha doğru yükseklik ölçümü
- Play test: Success sonrası bloklamama sorunu düzeltildi

**Etki:**
- Yükseklik ölçümü daha hassas
- Play test düzgün çalışıyor

---

#### 2026-01-04 - Play Test Script Eklendi

**Dosya:** `scripts/play_test.py` (Yeni)

**Özellikler:**
- Eğitilmiş modelleri test etme
- Deterministik action (exploration yok)
- Episode sonu istatistikleri
- Model checkpoint yükleme

**Etki:**
- Eğitilmiş modelleri kolayca test etme

---

#### 2026-01-03 - Reward Function İyileştirmeleri (Update 360 sonrası)

**Dosya:** `scripts/env.py`

**Değişiklikler:**
- Çeşitli reward parametreleri optimize edildi
- Update 360 checkpoint'ten sonra yapılan iyileştirmeler

---

#### 2026-01-03 - MissedZone Threshold ve Progressive Mesafe Cezası

**Dosya:** `scripts/env.py`

**Değişiklikler:**
- MissedZone threshold: `4.5m` → `6.0m` → `15.2m` (daha da gevşetildi)
- Progressive mesafe cezası eklendi:
  - Zone sınırında (8.5m): `-150.0` base penalty
  - Her 1m uzaklık için: `-30.0` ek ceza
  - Maksimum ceza: `-350.0` cap
- Zone kontrolü: kare yerine daire (15.2m yarıçap)

**Etki:**
- Normal inişleri başarı sayıyor
- Zone'a yakın inişler daha az ceza alıyor

---

#### 2026-01-03 - KRİTİK: Roll-Pitch Coupling Sorunu Çözüldü

**Dosyalar:**
- `rocket-env/Assets/Scripts/env.cs`

**Sorun:**
- Roll ve pitch torkları birbirini etkiliyordu
- Vector3 yerine transform vektörleri kullanılmıyordu
- Unity eksen eşleşmesi hatası vardı

**Çözüm:**
- `transform.right`, `transform.up`, `transform.forward` kullanıldı (local space)
- `AddRelativeTorque` ile roll coupling otomatik handle ediliyor
- Pitch ve yaw torkları doğru eksenlerde uygulanıyor

**Etki:**
- Roket kontrolü çok daha stabil
- Roll-pitch coupling sorunu tamamen çözüldü

---

#### 2026-01-03 - CeilingHit ve Yukarı Kaçma Sorunları Çözüldü

**Dosya:** `scripts/env.py`

**Değişiklikler:**
- `CeilingHit` threshold: `50.0m` → `54.0m` (daha erken yakalama)
- `CeilingHit` penalty: `-1000.0` → `-1200.0` (daha sert ceza)
- Yukarı gitme cezası artırıldı: `0.35` → `0.38`
- Yüksek irtifa cezaları optimize edildi

**Etki:**
- Agent yukarı kaçmayı daha az deniyor
- CeilingHit daha erken tespit ediliyor

---

#### 2026-01-03 - Exploration Sorunu Düzeltildi

**Dosya:** `scripts/agent.py`

**Değişiklikler:**
- `log_std` artırıldı (daha fazla exploration)
- Entropy coefficient artırıldı

**Etki:**
- Agent daha fazla keşif yapıyor
- Eğitim daha stabil

---

#### 2026-01-03 - Fizik Parametreleri Optimize Edildi

**Dosya:** `rocket-env/Assets/Scripts/env.cs`

**Değişiklikler:**
- Damping azaltıldı
- Thrust gücü artırıldı

**Etki:**
- Roket hareketi daha gerçekçi
- Kontrol daha responsive

---

#### 2026-01-03 - Reward Function Yeniden Tasarlandı

**Dosya:** `scripts/env.py`

**Büyük Değişiklikler:**

1. **Vertical Velocity - Her İrtifada Aktif (Progressive)**:
   - Artık tüm irtifalarda hız kontrolü var
   - Progressive penalty: İrtifa azaldıkça ceza artıyor
   - Formula: `altitude_factor = 1.0 + (15.0 / (dy + 1.0))`

2. **Reward Scaling**: `0.1x` → `0.5x` → `0.35x`
   - Shaping signal'lar görünür
   - Value loss riski düşük

3. **Distance Penalty**: `0.05` → `0.02` (hız kontrolüne yer açmak için)

4. **Horizontal Velocity Penalty**: `0.03` → `0.09` (drift'i azaltmak için)

5. **Tilt Penalty/Bonus Dengelendi**: 
   - Penalty: `-0.10` → `-0.08`
   - Bonus: `+0.04` → `+0.08` (eşit ağırlıkta)

6. **Yere Yaklaşma Bonusu Eklendi**: `dy < 35.0m` iken exponential bonus

7. **Yavaş İniş Bonusu Eklendi**: `vy > -2 m/s` iken bonus

8. **Merkeze Yaklaşma Bonusu**: Exponential, `0.37 * exp(-dist_h / 15.0)`

9. **Success Criteria**: 
   - `vy <= 4.5 m/s` (gevşetildi, önce 2.5 idi)
   - `v_h <= 4.0 m/s` (gevşetildi, önce 2.0 idi)
   - `dist_h <= 15.2m` (zone genişletildi)

10. **Terminal Conditions**:
    - `OutOfBounds`: `25m` → `20m` (sınır daraltıldı)
    - `CeilingHit`: `54.0m` threshold, `-1200.0` penalty
    - `Spin`: `7.3 rad/s` threshold, `-675.0` penalty
    - `Tilted`: `up_y < 0.35`, `-500.0` penalty

**Etki:**
- Agent yüksek irtifada bile hız kontrolü yapıyor
- Progressive penalty ile erken fren teşvik ediliyor
- Yumuşak iniş bonusu ile daha kontrollü iniş
- Drift sorunu azaldı

---

#### 2026-01-02 - Low Stage İçin Reward Sistem Güncellemesi

**Dosya:** `scripts/env.py`

**Değişiklik:**
- Low stage için özel reward parametreleri
- İlk deneme olarak işaretlendi

---

#### 2026-01-02 - Normalize İşlemi Loglardan Ayrıldı

**Dosyalar:** `scripts/env.py`, `scripts/train_main.py`

**Değişiklik:**
- Loglar artık raw state kullanıyor
- Normalize işlemi sadece agent'a gönderilirken yapılıyor
- `STATE_LOG_FILE`, `DETAILED_LOG_FILE` ve konsol çıktılarında raw değerler

**Etki:**
- Loglar fiziksel gerçek değerleri gösteriyor
- Analiz daha doğru

---

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

---

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

---

#### 2025-01-XX - Roll Kontrolü Eklendi (4 Action)

**Dosyalar:** `rocket-env/Assets/Scripts/env.cs`, `scripts/env.py`

**Değişiklik:**
- Unity'de `ApplyPhysics()` metoduna roll parametresi eklendi
- Unity'de `doAction()` case 0: 4 parametre yerine 5 parametre bekliyor (mode, pitch, yaw, thrust, roll)
- Python'da `step()` fonksiyonu artık 4 parametre gönderiyor (mode, pitch, yaw, thrust, roll)
- Roll kontrolü transform.forward ekseninde tork uyguluyor
- Roll gücü: `rcsPower * 0.1f` (pitch/yaw'dan 10x daha zayıf)

**Etki:**
- Agent artık 4 action kontrolü yapabiliyor (pitch, yaw, thrust, roll)
- Roket kendi ekseni etrafında dönebilir (roll)
- Daha fazla kontrol özgürlüğü

---

#### 2025-01-XX - connector.py readCs() Metodu Düzeltildi

**Dosya:** `scripts/connector.py`

**Sorun:**
- `readCs()` metodu çok basitti, sadece 1024 byte okuyordu
- Timeout yoktu, Unity yanıt vermezse sonsuz bekliyordu
- Unity state newline ile bitmiyor, state tam okunmayabiliyordu
- State bir sonraki mesajla karışabiliyordu

**Çözüm:**
- Buffer mekanizması eklendi, state tam okunana kadar bekliyor
- State newline ile bitiyor, buffer'da saklanıyor
- Boş satır gelirse yutuluyor ve tekrar okunuyor
- ConnectionError ve TimeoutError yönetimi

**Etki:**
- Unity'den gelen state artık tam olarak okunuyor
- Senkronizasyon sorunları azaldı
- Daha güvenilir iletişim

---

#### 2025-01-XX - env.py initialStart() ve step() Protokol Düzeltmeleri

**Dosya:** `scripts/env.py`

**Sorun:**
- `initialStart()` 14 parametre gönderiyordu ama Unity sadece 6 parametre bekliyor (mode, x, y, z, pitch, yaw)
- `step()` 13 parametre gönderiyordu ama Unity sadece 5 parametre bekliyor (mode, pitch, yaw, thrust, roll)
- Gereksiz parametreler Unity tarafında parse edilmiyordu

**Çözüm:**
- `initialStart()`: Sadece 6 parametre gönderiyor (1, x, y, z, pitch, yaw)
- `step()`: Sadece 5 parametre gönderiyor (0, pitch, yaw, thrust, roll)
- Protokol uyumlu hale getirildi

**Etki:**
- Protokol uyumsuzluğu giderildi
- Unity mesajları doğru parse edebiliyor
- Gereksiz veri gönderimi azaldı

---

#### 2025-01-XX - MissedZone Threshold Gevşetildi (Low Stage için Tolerans Artırıldı)

**Dosya:** `scripts/env.py`

**Sorun:**
- MissedZone threshold 3.0m çok sıkıydı (max yatay genişlik 5m)
- Agent düşük yükseklikte (≤5m) ve büyük mesafede (>3.0m) hiç Success deneyimleyemiyordu
- Analiz sonucu: Düşük yükseklik + büyük mesafe kombinasyonunda 0% başarı
- Agent "bu senaryo başarılabilir" sinyali alamıyordu

**Çözüm:**
- MissedZone threshold: `3.0m` → `4.5m` → `6.0m` → `15.2m` (zone genişletildi)
- Agent'a daha fazla tolerans verildi
- Düşük yükseklik + büyük mesafe senaryolarında Success deneyimi sağlandı
- Progressive mesafe cezası eklendi (zone'a yakınlığa göre)

**Etki:**
- Agent artık daha fazla Success durumu deneyimleyebilecek
- Curriculum learning: Low stage'de gevşek, sonra sıkılaştırılabilir
- Öğrenme hızlanması bekleniyor

---

## Gelecek Değişiklikler (Planlanan)

- [ ] Serbest düşüş sırasında Unity episode reset sorununun kalıcı çözümü
- [ ] Curriculum learning otomasyonu (difficulty level otomatik artışı)
- [ ] Daha detaylı analiz scriptleri
- [ ] Model karşılaştırma araçları
- [ ] Hyperparameter tuning araçları

---

---

#### 2025-01-XX - DETAILED_LOG_FILE Format Güncellemesi

**Dosya:** `scripts/train_main.py`

**Değişiklik:**
- `DETAILED_LOG_FILE` başlığı: `"Episode,Update,Return,Reason,StartAlt,StartDist,Difficulty"`
- Ancak gerçek yazılan format: `"Episode,Update,Return,Reason,StartAlt,StartDist,FinalDist,FinalVel"`
- Başlık ile veri uyumsuzluğu var (Difficulty yazıyor ama FinalDist ve FinalVel yazılıyor)

**Not:** Bu uyumsuzluk mevcut, gelecekte düzeltilmesi gerekiyor.

---

## Gelecek Değişiklikler (Planlanan)

- [ ] DETAILED_LOG_FILE başlık/veri uyumsuzluğu düzeltilmesi
- [ ] Serbest düşüş sırasında Unity episode reset sorununun kalıcı çözümü
- [ ] Curriculum learning otomasyonu (difficulty level otomatik artışı)
- [ ] Daha detaylı analiz scriptleri
- [ ] Model karşılaştırma araçları
- [ ] Hyperparameter tuning araçları

---

## Notlar

- Tüm değişiklikler commit geçmişine göre kronolojik olarak sıralanmıştır (en yeni en üstte)
- Her değişiklik için etki analizi ve notlar eklenmiştir
- Önemli değişiklikler için detaylı açıklamalar mevcuttur
- Bazı tarihler yaklaşık (commit mesajlarından çıkarıldı)
- Tüm değişiklikler mevcut kod durumuna göre doğrulanmıştır
