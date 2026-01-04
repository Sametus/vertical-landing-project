# En Başarılı Model Bilgileri

## Özet

Bu dosya, projede eğitilmiş en başarılı modellerin bilgilerini içerir.

## En İyi Model: Update 820 (Düşük Aşama Final)

### Model Dosyası
- **Dosya**: `models/rocket_model_up820.keras`
- **State Dosyası**: `models/rocket_state_up820.pkl.gz`
- **Yedek Konumu**: `models/low_stage_backup/rocket_model_up820_low_stage_final.keras`

### Performans Metrikleri

#### Başarı İstatistikleri (Update 781-820)
- **Başarı Oranı**: ~%24.4
- **CeilingHit Oranı**: %0.0 (Update 781-790 arası)
- **Spin Oranı**: Önemli ölçüde azalmış
- **MissedZone Oranı**: ~%4.4
- **OutOfBounds Oranı**: ~%11.1
- **Crash Oranı**: ~%11.1

#### Eğitim Koşulları
- **Başlangıç İrtifa Aralığı**: 5-15m (düşük aşama)
- **Başlangıç Yatay Aralık**: X: [-5.0, 5.0]m, Z: [-5.5, 5.5]m
- **Maksimum Episode Uzunluğu**: 1000 adım
- **Reward Scaling**: 0.35x

#### Ödül Fonksiyonu Özellikleri
- **Success Ödülü**: +2000 (temel) + zaman bonusu (0-300)
- **Success Koşulları**: 
  - dy ≤ 1.7m
  - dist_h < 10.0m
  - |vy| ≤ 3.5 m/s
  - v_h ≤ 3.0 m/s
  - w_mag ≤ 5.0 rad/s
- **CeilingHit Eşiği**: 50m
- **CeilingHit Cezası**: -1200
- **OutOfBounds Eşiği**: 35m
- **OutOfBounds Cezası**: -650

#### Öne Çıkan Başarılar
1. **CeilingHit Problemi Çözüldü**: Update 781-790 arasında hiç CeilingHit olmadı
2. **Stabil Başarı Oranı**: Düşük irtifa aralığında tutarlı ~%24 başarı
3. **Spin Kontrolü**: Açısal hız kontrolünde önemli iyileşme
4. **Düşük İrtifadan Başarılı İniş**: 1.7-10m aralığından başarılı inişler

### Model Özellikleri

#### PPO Hiperparametreleri
- Learning Rate: 1e-4
- Discount Factor (γ): 0.99
- GAE Lambda (λ): 0.95
- Clip Epsilon: 0.1
- Value Function Coefficient: 0.5
- Entropy Coefficient: 0.02
- Epochs per Update: 4
- Batch Size: 256
- Max Gradient Norm: 0.5

#### Ağ Mimarisi
- Policy Network: 3 katmanlı MLP (LeakyReLU)
- Value Network: 3 katmanlı MLP (aynı mimari)
- State Size: 13 boyut (normalize edilmiş)
- Action Size: 4 boyut (pitch, yaw, thrust, roll)

### Kullanım

Bu modeli test etmek için:

```bash
cd scripts
python play_test.py --model_path ../models/rocket_model_up820.keras
```

Veya yedek kopyayı kullanmak için:

```bash
cd scripts
python play_test.py --model_path ../models/low_stage_backup/rocket_model_up820_low_stage_final.keras
```

### Notlar

- Bu model, düşük irtifa senaryoları (5-15m) için optimize edilmiştir
- Orta irtifa senaryolarına (5-20m) geçişte performans düşmüştür
- CeilingHit önleme mekanizmaları başarıyla uygulanmıştır
- Model, düşük başlangıç irtifalarından (3-10m) en iyi performansı gösterir

## Diğer Not Değer Model Versiyonları

### Update 840
- **Loss Değeri**: 366.58 (çok düşük)
- **Not**: Loss açısından en iyi update, ancak başarı oranı hakkında detaylı bilgi eksik

### Update 900
- **Loss Değeri**: 1036.56
- **KL Divergence**: 0.0289 (yüksek - büyük policy güncellemesi)
- **Not**: Büyük policy güncellemesi sonrası iyileşme gösterdi

## Model Seçim Önerisi

**Düşük İrtifa Senaryoları İçin**: Update 820 modeli önerilir
- Stabil başarı oranı
- CeilingHit kontrolü
- İyi spin kontrolü

**Orta İrtifa Senaryoları İçin**: Devam eden eğitim gereklidir
- Mevcut modeller orta irtifa için yeterli performans göstermemektedir
- Crash oranı yüksektir (~60%)
- Reward tuning ve curriculum learning gerekebilir

## Güncelleme Notu

Son güncelleme: README oluşturma sırasında
Model analiz edildiği tarih: Update 910 sonrası

