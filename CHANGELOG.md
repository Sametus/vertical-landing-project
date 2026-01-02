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

---