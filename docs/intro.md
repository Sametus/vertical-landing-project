# Proje Belgesi: Unity ile 3B Roket İniş Simülasyonu ve RL Entegrasyonu

## 1. Proje Özeti ve Amacı

Bu proje, Unity 3B ortamında geliştirilen dikey inişli bir roket simülasyonunu kapsamaktadır. Roketin hem dikey iniş hızını hem de açısal dengesini (Pitch ve Yaw) kontrol etmek amacıyla tek bir Reinforcement Learning (RL) ajanı eğitilecektir. Ajanın temel görevi, rastgele başlangıç koşullarından başlayarak roketi belirlenmiş bir iniş platformuna güvenli ve yumuşak bir şekilde indirmektir.

## 2. Unity Model Mimarisi (Görsel Yapı)

Görsel estetikten ziyade işlevselliğe odaklanılarak, roket modeli Unity'nin temel 3B nesneleri (primitives) kullanılarak aşağıdaki hiyerarşiyle oluşturulmuştur:

* **`Roket` (Ana Nesne):**
    * Tüm alt parçaları içeren ebeveyn nesnedir.
    * Fiziğin ana merkezi: **`Rigidbody`** ve **`Capsule Collider`** (ana gövde çarpıştırıcısı) bileşenlerini barındırır.
    * Tüm kontrol betikleri (`RocketController.cs`) bu nesneye eklenmiştir.
* **Alt Nesneler (Children):**
    * **`Gövde`:** `Cylinder` nesnesi.
    * **`Burun`:** `Sphere` nesnesi (Koni yerine).
    * **`Nozul (Ana Motor)`:** `Gövde`nin altında yer alan görsel bir `Cylinder` nesnesi.
    * **`Nozul_Kuzey`, `Nozul_Guney`, `Nozul_Dogu`, `Nozul_Bati`:** Açısal kontrolü simgeleyen, gövdenin üst kısmına yerleştirilmiş 4 adet görsel `Cube` nesnesi. Bu nesnelerin çarpıştırıcıları (Collider) yoktur.
    * **(Ertelendi):** İniş ayaklarının eklenmesi daha sonraki bir aşamaya bırakılmıştır.

## 3. Fizik ve Kontrol Modeli (İşlevsel Yapı)

Roketin hareketi, RL ajanının kontrol edeceği iki temel fiziksel eyleme bölünmüştür:

### 3.1. Dikey İtki (Ana Motor)
* Roketin yükselmesini ve yavaşlamasını sağlar.
* **Uygulama:** `Rigidbody.AddRelativeForce(Vector3.up * kuvvet)` komutuyla, roketin kendi dikey ekseninde kuvvet uygulanır.
* **Kontrol:** Ajanın 0 ile 1 arasında ürettiği dikey itki kararı ($f_v$) ile yönetilir.

### 3.2. Açısal Kontrol (RCS İticileri)
* Roketin dengesini (Pitch ve Yaw) sağlar.
* **Kontrol Edilen Eksenler:** Sadece `Pitch` (öne/arkaya eğilme) ve `Yaw` (sağa/sola sapma).
* **Göz Ardı Edilen Eksen:** `Roll` (dikey eksende dönme) ekseni, simülasyonu ve öğrenme problemini basitleştirmek için aktif olarak kontrol *edilmeyecektir*.
* **Uygulama:** 4 adet nozulu tek tek `AddForceAtPosition` (Zor Yol) ile simüle etmek yerine, 4 nozulun yarattığı *kombine etkiyi* simüle eden `Rigidbody.AddTorque()` (Kolay Yol) fonksiyonu tercih edilmiştir. Bu, daha temiz, daha basit ve daha yönetilebilir bir kod yapısı sağlar.
* **Kontrol:** Ajanın -1 ile +1 arasında ürettiği tork kararları ($f_p$ ve $f_y$) ile yönetilir.

## 4. RL Ajan Mimarisi (Girdi/Çıktı)

Roketin tüm kontrolü, aşağıdaki Girdi/Çıktı mimarisine sahip **tek bir RL ajanı** tarafından sağlanacaktır.

### 4.1. 🤖 Gözlem Vektörü ($O$) - GİRDİ (Toplam 13 Eleman)
Ajanın her adımda alacağı ve karar vermek için kullanacağı tam sensör verisi listesidir:

$O = [d_x, d_y, d_z, v_x, v_y, v_z, q_x, q_y, q_z, q_w, \omega_x, \omega_y, \omega_z]$

Bu vektör 4 ana gruptan oluşur:
1.  **🎯 Göreceli Konum ($d$):** `[ $d_x, d_y, d_z$ ]`
    * Roketin, iniş platformuna göre X, Y, Z eksenlerindeki mesafesi.
2.  **💨 Çizgisel Hız ($v$):** `[ $v_x, v_y, v_z$ ]`
    * Roketin `Rigidbody.velocity` değerinden alınan X, Y, Z eksenlerindeki anlık hızı.
3.  **🧭 Yönelim (Quaternion, $q$):** `[ $q_x, q_y, q_z, q_w$ ]`
    * Roketin 3 boyutlu tam dönüşü. Ajanın öğrenmesini stabilize etmek ve "359 derece -> 0 derece" sıçrama sorununu engellemek için Euler Açıları (Pitch, Yaw) yerine 4 değerli **Quaternion** (`transform.rotation`) kullanılmasına karar verilmiştir.
4.  **🌀 Açısal Hız ($\omega$):** `[ $\omega_x, \omega_y, \omega_z$ ]`
    * Roketin `Rigidbody.angularVelocity` değerinden alınan, her eksendeki anlık dönme hızı. Bu, ajanın sadece "eğik" olduğunu değil, "ne hızla devrildiğini" de anlamasını sağlar.

### 4.2. 🦾 Aksiyon Vektörü ($A$) - ÇIKTI (Toplam 3 Eleman)
Ajanın 13 gözlemi aldıktan sonra her adımda üreteceği 3 karardır:

$A = [f_p, f_y, f_v]$

1.  **$f_p$ (Pitch Torku):**
    * Değer Aralığı: `-1.0` ile `+1.0` arası.
    * Etkisi: `ApplyRotation()` fonksiyonu aracılığıyla `AddTorque`'un `transform.right` eksenine uygulanır.
2.  **$f_y$ (Yaw Torku):**
    * Değer Aralığı: `-1.0` ile `+1.0` arası.
    * Etkisi: `ApplyRotation()` fonksiyonu aracılığıyla `AddTorque`'un `transform.up` eksenine uygulanır.
3.  **$f_v$ (Dikey İtki):**
    * Değer Aralığı: `0.0` ile `+1.0` arası (sadece pozitif itki).
    * Etkisi: `ApplyThrust()` fonksiyonu aracılığıyla `AddRelativeForce`'a uygulanır.

## 5. Eğitim Stratejisi

Ajanın "aşırı öğrenmesini" (overfitting) engellemek ve farklı durumlara karşı dayanıklı (robust) olmasını sağlamak için her eğitim bölümü (episode) başında `ResetEpisode()` fonksiyonu çalışacaktır. Bu fonksiyon:
1.  Roketin tüm çizgisel (`velocity`) ve açısal (`angularVelocity`) hızlarını sıfırlar.
2.  Roketi önceden belirlenmiş bir başlangıç pozisyonuna taşır.
3.  Roketin dönüşünü (rotation) sıfırlar ve ardından üzerine **rastgele bir `pitch` ve `yaw` açısı** ekler. Bu sayede ajan her seferinde farklı bir denge probleminden kurtulmayı öğrenmek zorunda kalır.