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

---

