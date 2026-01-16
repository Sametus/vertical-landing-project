"""
Play-Test Script: Train edilmiş modeli test etmek için
- Model yüklenir
- Episode'lar çalıştırılır (random başlangıç)
- Success durumunda 2-3 saniye bekler
- Otomatik olarak yeni episode başlatır
"""

import os
import sys
import time
import argparse
import numpy as np
import tensorflow as tf
from datetime import datetime

from agent import PPOAgent
from env import Env

# GPU setup
def setup_gpu():
    """GPU kullanımını yapılandırır"""
    gpus = tf.config.experimental.list_physical_devices('GPU')
    if gpus:
        try:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            print(f"[OK] {len(gpus)} GPU bulundu ve yapılandırıldı.")
            return True
        except RuntimeError as e:
            print(f"GPU yapılandırma uyarısı: {e}")
            return True
    else:
        print("[WARN] GPU bulunamadı, CPU kullanılacak")
        return False

MODELS_DIR = "models"

def as_float32(x):
    return np.asarray(x, dtype=np.float32)

def load_checkpoint(model_path, state_path, agent):
    """Checkpoint yükler"""
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model dosyası bulunamadı: {model_path}")
    
    print(f"Model yükleniyor: {model_path}")
    agent.model = tf.keras.models.load_model(model_path, compile=False)
    
    if os.path.exists(state_path):
        import gzip
        import pickle
        print(f"State yükleniyor: {state_path}")
        with gzip.open(state_path, "rb") as f:
            state = pickle.load(f)
        if "log_std" in state:
            agent.log_std.assign(np.array(state["log_std"], dtype=np.float32))
    else:
        print(f"[WARN] State dosyası bulunamadı: {state_path} (log_std varsayılan değerde kalacak)")
    
    print("[OK] Model başarıyla yüklendi!\n")

def act_deterministic(agent, state):
    """
    Deterministik action - Training'deki gibi exploration ekleniyor ama deterministik seed ile
    Training'de agent.act() kullanılıyor, bu da exploration ekliyor. Test'te de aynı mantığı kullanalım
    ama seed'i sabitleyerek deterministik yapalım (her episode aynı sonuçlar için).
    """
    s = tf.convert_to_tensor(state[None,:], tf.float32)
    mu, v = agent.model(s)
    mu = tf.squeeze(mu, 0)
    
    # Training'deki gibi: std ile exploration ekle, sonra tanh uygula
    # Training'de: pre_tanh = mu + std * eps, a = tanh(pre_tanh)
    # Test'te: Deterministik için epsilon'u küçült ama sıfırlama (tam deterministik spin'e yol açabilir)
    std = tf.exp(agent.log_std)
    
    # Deterministik için: epsilon = 0 kullan (sadece mean)
    # Ama training'deki tanh(pre_tanh) mantığını koru
    eps = tf.zeros((agent.action_size,), dtype=tf.float32)  # Deterministik: epsilon = 0
    pre_tanh = mu + std * eps  # eps=0 olduğu için pre_tanh = mu
    a = tf.tanh(pre_tanh)  # Training'deki gibi tanh uygula
    
    return a.numpy().astype(np.float32)

def format_action(action, detailed=False):
    """Action'ı okunabilir formata çevir"""
    pitch, yaw, thrust_raw, roll = action
    # Thrust: [-1, 1] -> [0, 1] -> [0, 100]%
    thrust_normalized = (thrust_raw + 1) / 2  # 0-1 arası
    thrust_pct = thrust_normalized * 100  # 0-100% arası
    thrust_kn = thrust_normalized * 15.0  # Max 15kN thrust (Unity'deki max thrust değeri)
    
    # RCS: [-1, 1] direkt birim olarak kullanılabilir (normalize edilmiş)
    if detailed:
        return (f"Thrust:{thrust_pct:.1f}% ({thrust_kn:.2f}kN) | "
                f"RCS-Pitch:{pitch:+.3f} | RCS-Yaw:{yaw:+.3f} | RCS-Roll:{roll:+.3f}")
    else:
        return f"T:{thrust_pct:.1f}%/{thrust_kn:.2f}kN | P:{pitch:+.3f} Y:{yaw:+.3f} R:{roll:+.3f}"

def format_state(state_raw, detailed=False):
    """State'i okunabilir formata çevir"""
    dx, dy, dz = state_raw[0], state_raw[1], state_raw[2]
    vx, vy, vz = state_raw[3], state_raw[4], state_raw[5]
    wx, wy, wz = state_raw[6], state_raw[7], state_raw[8]
    qx, qy, qz, qw = state_raw[9], state_raw[10], state_raw[11], state_raw[12]
    
    # Quaternion normalize
    qnorm = (qx*qx + qy*qy + qz*qz + qw*qw) ** 0.5
    if qnorm > 1e-6:
        qx /= qnorm; qy /= qnorm; qz /= qnorm; qw /= qnorm
    
    # up_y: roketin yukarı doğru oryantasyonu (1.0 = dikey, 0.0 = yatay)
    up_y = 1.0 - 2.0*(qx*qx + qz*qz)
    
    dist_h = np.sqrt(dx**2 + dz**2)
    v_h = np.sqrt(vx**2 + vz**2)
    w_mag = np.sqrt(wx**2 + wy**2 + wz**2)
    
    result = {
        'alt': dy,
        'dist': dist_h,
        'vy': vy,
        'vx': vx,
        'vz': vz,
        'v_h': v_h,
        'wx': wx,
        'wy': wy,
        'wz': wz,
        'w_mag': w_mag,
        'up_y': up_y,
        'qx': qx,
        'qy': qy,
        'qz': qz,
        'qw': qw,
    }
    return result

def compute_upright_action(state_raw, target_up_y=1.0, strength=3.0):
    """
    Roketi dik konuma yumuşak bir şekilde geçirmek için kontrol action'ı hesapla
    target_up_y=1.0: Tam dik konum
    strength: Kontrol kuvveti (yüksek = daha agresif, düşük = daha yumuşak)
    """
    # State'ten tilt ve açısal hızı hesapla
    qx, qy, qz, qw = state_raw[9], state_raw[10], state_raw[11], state_raw[12]
    wx, wy, wz = state_raw[6], state_raw[7], state_raw[8]
    
    # Quaternion normalize
    qnorm = (qx*qx + qy*qy + qz*qz + qw*qw) ** 0.5
    if qnorm > 1e-6:
        qx /= qnorm; qy /= qnorm; qz /= qnorm; qw /= qnorm
    
    # up_y: roketin yukarı doğru oryantasyonu
    up_y = 1.0 - 2.0*(qx*qx + qz*qz)
    
    # Tilt hatası: ne kadar uzaktayız hedef konumdan
    tilt_error = target_up_y - up_y
    
    # Eğer zaten dikse, minimal kontrol
    if up_y > 0.99:
        pitch_correction = -0.5 * qx  # Çok hafif
        yaw_correction = -0.5 * qz
        roll_correction = -0.3 * wx
    else:
        # Pitch kontrolü: qx'e göre (ön-arka eğim)
        pitch_correction = -strength * qx
        
        # Yaw kontrolü: qz'e göre (sağ-sol dönüş)
        yaw_correction = -strength * qz
        
        # Roll kontrolü: açısal hızı sıfırlamaya çalış
        roll_correction = -1.0 * wx
    
    # Action: [pitch, yaw, thrust, roll]
    pitch = np.clip(pitch_correction, -1.0, 1.0)
    yaw = np.clip(yaw_correction, -1.0, 1.0)
    roll = np.clip(roll_correction, -1.0, 1.0)
    thrust = -1.0  # Serbest düşüş, thrust yok
    
    return np.array([pitch, yaw, thrust, roll], dtype=np.float32)

def compute_soft_landing_action(state_raw):
    """
    Yumuşak iniş için kontrol action'ı hesapla
    - vy (dikey hız) negatif ve büyükse hafif thrust uygular (yumuşak iniş)
    - RCS ile stabilizasyon sağlar
    - Yere yaklaştıkça thrust'u artırır
    """
    # State'ten bilgileri al
    qx, qy, qz, qw = state_raw[9], state_raw[10], state_raw[11], state_raw[12]
    wx, wy, wz = state_raw[6], state_raw[7], state_raw[8]
    vy = state_raw[4]  # Dikey hız
    dy = state_raw[1]  # Yükseklik
    
    # Quaternion normalize
    qnorm = (qx*qx + qy*qy + qz*qz + qw*qw) ** 0.5
    if qnorm > 1e-6:
        qx /= qnorm; qy /= qnorm; qz /= qnorm; qw /= qnorm
    
    # up_y: roketin yukarı doğru oryantasyonu
    up_y = 1.0 - 2.0*(qx*qx + qz*qz)
    
    # RCS stabilizasyon (compute_stability_action mantığı)
    base_strength = 3.0
    pitch_correction = -base_strength * qx
    yaw_correction = -base_strength * qz
    roll_correction = -1.0 * wx
    
    # Yan yatma durumunda daha agresif düzeltme
    if up_y < 0.7:
        pitch_correction *= 2.0
        yaw_correction *= 2.0
        roll_correction *= 1.5
    elif up_y < 0.85:
        pitch_correction *= 1.5
        yaw_correction *= 1.5
        roll_correction *= 1.2
    elif up_y > 0.95:
        pitch_correction *= 0.2
        yaw_correction *= 0.2
        roll_correction *= 0.2
    elif up_y > 0.90:
        pitch_correction *= 0.5
        yaw_correction *= 0.5
        roll_correction *= 0.5
    
    # Yumuşak iniş için thrust hesaplama
    # vy negatif ve büyükse (hızlı düşüş), AGRESİF thrust uygula (sert çarpmayı önlemek için)
    thrust_val = -1.0  # Varsayılan: thrust yok
    
    if vy < 0.0:  # Aşağı düşüyor
        # Hız ne kadar fazlaysa, o kadar çok thrust
        # vy = -3 m/s -> ~0.3 thrust, vy = -5 m/s -> ~0.5 thrust, vy = -8 m/s -> ~0.7 thrust
        speed_factor = min(abs(vy) / 8.0, 1.0)  # Max 8 m/s için normalize (daha hassas)
        
        # Yükseklik faktörü: yere yaklaştıkça thrust AGRESİF şekilde artır
        # dy = 3m -> orta thrust, dy = 1.5m -> yüksek thrust, dy = 0.5m -> maksimum thrust
        if dy > 1.5:
            height_factor = max(0.5, 1.0 - (dy - 1.5) / 3.0)  # 1.5-4.5m arası (daha geniş aralık)
        elif dy > 0.5:
            height_factor = 0.8 + (1.5 - dy) / 1.0 * 0.2  # 0.5-1.5m arası, 0.8'den 1.0'a
        else:
            height_factor = 1.0  # Çok yakınsa maksimum thrust
        
        # Kombine thrust: Hız ve yükseklik faktörlerini birleştir
        # Thrust: [-1, 1] -> [0, 1] normalize edilmiş
        # -1.0 = 0% thrust, 1.0 = 100% thrust
        # AGRESİF: 0.0-0.75 arası thrust kullan (önceden 0.5'ti, şimdi 0.75)
        # Bu, sert çarpmayı önlemek için daha güçlü thrust sağlar
        base_thrust_max = 0.75  # Max 75% thrust (önceden 50%'ydi)
        target_thrust_normalized = speed_factor * height_factor * base_thrust_max
        
        # Eğer hız çok yüksekse (vy < -6 m/s), ekstra thrust ekle
        if abs(vy) > 6.0:
            extra_factor = min((abs(vy) - 6.0) / 4.0, 0.15)  # Ekstra %15'e kadar
            target_thrust_normalized = min(0.85, target_thrust_normalized + extra_factor)
        
        # Normalize edilmiş değeri [-1, 1] aralığına çevir
        thrust_val = (target_thrust_normalized * 2.0) - 1.0  # 0.0 -> -1.0, 0.75 -> 0.5, 0.85 -> 0.7
        
    elif vy > 0.0 and dy < 0.5:
        # Yukarı gidiyorsa ve yerdeyse, thrust'u kapat
        thrust_val = -1.0
    elif abs(vy) < 1.0 and dy < 0.5:
        # Yerde ve yavaş, minimal thrust (sadece dengeleme için)
        thrust_val = -0.95  # Çok hafif thrust
    
    # Action: [pitch, yaw, thrust, roll]
    pitch = np.clip(pitch_correction, -1.0, 1.0)
    yaw = np.clip(yaw_correction, -1.0, 1.0)
    roll = np.clip(roll_correction, -1.0, 1.0)
    thrust = np.clip(thrust_val, -1.0, 1.0)
    
    return np.array([pitch, yaw, thrust, roll], dtype=np.float32)

def compute_stability_action(state_raw):
    """
    Serbest düşüş sırasında roketin dengede kalması için kontrol action'ı hesapla
    Basit PD kontrolü kullanarak tilt ve spin'i azaltmaya çalışır
    Yan yatma durumunda daha agresif düzeltme yapar
    """
    # State'ten tilt ve açısal hızı hesapla
    qx, qy, qz, qw = state_raw[9], state_raw[10], state_raw[11], state_raw[12]
    wx, wy, wz = state_raw[6], state_raw[7], state_raw[8]
    
    # Quaternion normalize
    qnorm = (qx*qx + qy*qy + qz*qz + qw*qw) ** 0.5
    if qnorm > 1e-6:
        qx /= qnorm; qy /= qnorm; qz /= qnorm; qw /= qnorm
    
    # up_y: roketin yukarı doğru oryantasyonu
    up_y = 1.0 - 2.0*(qx*qx + qz*qz)
    
    # Tilt hatası: ne kadar yatık
    tilt_error = 1.0 - up_y
    
    # Pitch kontrolü: qx'e göre (ön-arka eğim)
    # Eğer qx pozitifse, roket öne eğilmiş, pitch negatif olmalı (geri)
    base_strength = 3.0  # Temel kuvvet katsayısı
    pitch_correction = -base_strength * qx
    
    # Yaw kontrolü: qz'e göre (sağ-sol dönüş)
    # Eğer qz pozitifse, roket sağa dönmüş, yaw negatif olmalı (sola)
    yaw_correction = -base_strength * qz
    
    # Roll kontrolü: açısal hız wx'e göre (x ekseni etrafında dönüş)
    roll_correction = -1.0 * wx  # Açısal hızı sıfırlamaya çalış
    
    # Yan yatma durumunda daha agresif düzeltme
    if up_y < 0.7:  # Çok yatık (>45°)
        pitch_correction *= 2.0  # 2x daha güçlü
        yaw_correction *= 2.0
        roll_correction *= 1.5
    elif up_y < 0.85:  # Orta yatık (30-45°)
        pitch_correction *= 1.5
        yaw_correction *= 1.5
        roll_correction *= 1.2
    elif up_y > 0.95:  # Çok dikey, minimal kontrol
        pitch_correction *= 0.2
        yaw_correction *= 0.2
        roll_correction *= 0.2
    elif up_y > 0.90:  # İyi durum, hafif kontrol
        pitch_correction *= 0.5
        yaw_correction *= 0.5
        roll_correction *= 0.5
    
    # Action: [pitch, yaw, thrust, roll]
    # Thrust = -1 (0% thrust, serbest düşüş)
    pitch = np.clip(pitch_correction, -1.0, 1.0)
    yaw = np.clip(yaw_correction, -1.0, 1.0)
    roll = np.clip(roll_correction, -1.0, 1.0)
    thrust = -1.0  # Serbest düşüş, thrust yok
    
    return np.array([pitch, yaw, thrust, roll], dtype=np.float32)

def print_test_info(test_num, step, state_info, action, reward, reason=None):
    """Test bilgilerini konsola yazdır"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    alt_str = f"Alt:{state_info['alt']:.2f}m"
    dist_str = f"Dist:{state_info['dist']:.2f}m"
    vy_str = f"Vy:{state_info['vy']:.2f}m/s"
    vh_str = f"Vh:{state_info['v_h']:.2f}m/s"
    action_str = format_action(action, detailed=True)
    reward_str = f"Reward:{reward:+.1f}"
    
    line = (f"[{timestamp}] Test:{test_num} Step:{step:3d} | "
            f"State: {alt_str} {dist_str} {vy_str} {vh_str} | "
            f"Action: {action_str} | {reward_str}")
    if reason:
        line += f" | {reason}"
    print(line)

def main():
    parser = argparse.ArgumentParser(description='Train edilmiş modeli test et')
    parser.add_argument('--model', type=str, default=None,
                        help='Model dosyası yolu (örn: models/rocket_model_up300.keras)')
    parser.add_argument('--update', type=int, default=None,
                        help='Update numarası (örn: 300) - en son modeli kullanmak için')
    parser.add_argument('--episodes', type=int, default=-1,
                        help='Kaç test çalıştırılacak (-1 = süresiz)')
    parser.add_argument('--wait-on-success', type=float, default=2.5,
                        help='Success durumunda bekleme süresi (saniye, default: 2.5)')
    parser.add_argument('--show-steps', action='store_true',
                        help='Her adımı göster (default: sadece özet)')
    
    args = parser.parse_args()
    
    # GPU setup
    setup_gpu()
    
    # Model yolu belirleme
    if args.model:
        model_path = args.model
        # State path'i bul: rocket_model_up300.keras -> rocket_state_up300.pkl.gz
        import re
        match = re.search(r"up(\d+)\.keras$", model_path)
        if match:
            update_num = match.group(1)
            state_path = model_path.replace(f"rocket_model_up{update_num}.keras", f"rocket_state_up{update_num}.pkl.gz")
        else:
            # Fallback: model path'in yanında state dosyası ara
            base = model_path.replace('.keras', '')
            state_path = os.path.join(os.path.dirname(model_path), os.path.basename(base).replace('rocket_model_', 'rocket_state_') + '.pkl.gz')
    elif args.update is not None:
        model_path = os.path.join(MODELS_DIR, f"rocket_model_up{args.update}.keras")
        state_path = os.path.join(MODELS_DIR, f"rocket_state_up{args.update}.pkl.gz")
    else:
        # En son modeli bul
        import glob
        import re
        pattern = os.path.join(MODELS_DIR, "rocket_model_up*.keras")
        files = glob.glob(pattern)
        if not files:
            print("[ERROR] Hiç model bulunamadı!")
            sys.exit(1)
        
        # Update numarasına göre sırala
        nums = []
        for p in files:
            m = re.search(r"up(\d+)\.keras$", os.path.basename(p))
            if m:
                nums.append((int(m.group(1)), p))
        
        if not nums:
            print("[ERROR] Geçerli model bulunamadı!")
            sys.exit(1)
        
        latest_update, model_path = max(nums, key=lambda x: x[0])
        state_path = os.path.join(MODELS_DIR, f"rocket_state_up{latest_update}.pkl.gz")
        print(f"[INFO] En son model bulundu: Update {latest_update}")
    
    # Agent ve Environment oluştur
    print("[INFO] Environment ve Agent hazırlanıyor...")
    environment = Env()
    agent = PPOAgent()
    
    # Model yükle
    try:
        load_checkpoint(model_path, state_path, agent)
    except Exception as e:
        print(f"[ERROR] Model yüklenirken hata: {e}")
        sys.exit(1)
    
    # Play-test başlat
    print("*" * 80)
    print("PLAY-TEST BAŞLATILIYOR")
    print("*" * 80)
    print(f"Model: {os.path.basename(model_path)}")
    print(f"Başlangıç koşulları: Yükseklik {environment.init_y_min}-{environment.init_y_max}m, Yatay ±{environment.init_x_max}m")
    print(f"Success bekleme süresi: {args.wait_on_success}s")
    print(f"Test limiti: {'Süresiz' if args.episodes == -1 else args.episodes}")
    print("*" * 80)
    print()
    
    test_num = 0
    success_count = 0
    crash_count = 0
    other_count = 0
    
    try:
        while args.episodes == -1 or test_num < args.episodes:
            test_num += 1
            
            # Yeni test başlat - training mantığı: initialStart() sonrası direkt readStates()
            # KRİTİK: Environment state'ini tamamen temizle (önceki episode'dan kalıntı olmamalı)
            environment.done = False
            environment.step_count = 0
            environment.termination_reason = "Running"
            
            environment.initialStart()
            state_raw = as_float32(environment.readStates())
            state_norm = as_float32(environment.normalize_state(state_raw))
            
            # Başlangıç bilgileri
            start_info = format_state(state_raw)
            
            step = 0
            total_reward = 0.0
            done = False
            
            while not done:
                # Deterministik action al (exploration yok)
                action = act_deterministic(agent, state_norm)
                
                # Step
                next_state_raw, done, reward = environment.step(action)
                
                total_reward += reward
                step += 1
                
                # Sadece episode sonunda göster (veya --show-steps açıksa)
                if args.show_steps or done:
                    state_info = format_state(state_raw)
                    reason = getattr(environment, 'termination_reason', None) if done else None
                    print_test_info(test_num, step, state_info, action, reward, reason)
                
                # State güncelle
                state_raw = as_float32(next_state_raw)
                state_norm = as_float32(environment.normalize_state(state_raw))
            
            # Test sonu - son state zaten elimizde (next_state_raw'dan gelen)
            reason = getattr(environment, 'termination_reason', 'Unknown')
            final_info = format_state(state_raw)  # Son state'i kullan (step()'den gelen)
            
            print(f"\n{'*'*80}")
            print(f"TEST {test_num} BİTTİ")
            print(f"{'*'*80}")
            print(f"Sonuç: {reason}")
            print(f"Step sayısı: {step}")
            print(f"Toplam reward: {total_reward:.2f}")
            print(f"\nBaşlangıç State:")
            print(f"  Alt:{start_info['alt']:.2f}m | Dist:{start_info['dist']:.2f}m | "
                  f"Vy:{start_info['vy']:.2f}m/s | Vh:{start_info['v_h']:.2f}m/s")
            print(f"\nBitiş State:")
            print(f"  Alt:{final_info['alt']:.2f}m | Dist:{final_info['dist']:.2f}m | "
                  f"Vy:{final_info['vy']:.2f}m/s | Vh:{final_info['v_h']:.2f}m/s")
            
            if reason == "Success":
                success_count += 1
                print(f"\nBAŞARILI İNİŞ! ({success_count}. başarı)")
                
                # Success sonrası yumuşak geçiş: Fizik simülasyonu ile roketi dik ve yere değecek şekilde ayarla
                # TEST MODU: Bu geçiş sadece görsel amaçlı. Episode bitince environment state temizlenecek.
                
                # Success anındaki pozisyonu al
                dx = state_raw[0]
                dy = state_raw[1]  # Mevcut yükseklik
                dz = state_raw[2]
                
                # Roket fiziksel özellikleri
                ROCKET_HEIGHT = 6.5
                ROCKET_RADIUS = ROCKET_HEIGHT / 2  # 3.25m
                TARGET_BOTTOM_HEIGHT = 0.15  # Hedef yükseklik
                
                # Yumuşak geçiş parametreleri
                smooth_steps = 0
                max_smooth_steps = 40  # ~4 saniye (10 FPS varsayarak)
                
                while smooth_steps < max_smooth_steps:
                    # Mevcut state bilgileri
                    current_dy = state_raw[1]
                    vy = state_raw[4]  # Dikey hız
                    vx = state_raw[3]
                    vz = state_raw[5]
                    wx = state_raw[6]  # Açısal hızlar
                    wy = state_raw[7]
                    wz = state_raw[8]
                    
                    # Quaternion'dan rotasyon bilgisi
                    qx, qy, qz, qw = state_raw[9], state_raw[10], state_raw[11], state_raw[12]
                    qnorm = (qx*qx + qy*qy + qz*qz + qw*qw) ** 0.5
                    if qnorm > 1e-6:
                        qx /= qnorm; qy /= qnorm; qz /= qnorm; qw /= qnorm
                    up_y = 1.0 - 2.0*(qx*qx + qz*qz)  # 1.0 = dikey, 0.0 = yatay
                    
                    # İlerleme oranı (0 -> 1)
                    progress = smooth_steps / max_smooth_steps
                    
                    # Yumuşak dik durma: Progressive strength ile dik durmaya çalış
                    # Başlangıçta düşük, zamanla artıyor
                    base_strength = 1.5 + progress * 2.0  # 1.5 -> 3.5
                    if up_y < 0.85:  # Çok eğikse
                        base_strength *= 1.3
                    
                    # RCS kontrolü: Dik durma
                    pitch_correction = -base_strength * qx
                    yaw_correction = -base_strength * qz
                    roll_correction = -1.0 * wx  # Açısal hızı sıfırla
                    
                    # Açısal hızları sıfırla
                    if abs(wy) > 0.1:
                        pitch_correction -= 0.3 * np.sign(wy)
                    if abs(wz) > 0.1:
                        yaw_correction -= 0.3 * np.sign(wz)
                    
                    pitch = np.clip(pitch_correction, -1.0, 1.0)
                    yaw = np.clip(yaw_correction, -1.0, 1.0)
                    roll = np.clip(roll_correction, -1.0, 1.0)
                    
                    # Thrust kontrolü: Yumuşak yere değme
                    thrust = -1.0  # Varsayılan: thrust yok
                    
                    # Yükseklik kontrolü: Hedef yüksekliğe yumuşak bir şekilde yaklaş
                    target_dy = TARGET_BOTTOM_HEIGHT
                    height_error = current_dy - target_dy
                    
                    if height_error > 0.1:  # Hedef yüksekliğin üstündeyse
                        # Yumuşak düşüş: Dikey hıza göre thrust ayarla
                        if vy < -1.0:  # Hızlı düşüş varsa
                            # Hafif thrust uygula (yumuşak iniş)
                            thrust_factor = min(0.25, abs(vy) / 12.0)
                            thrust = (thrust_factor * 2.0) - 1.0  # [-1, -0.5]
                        elif vy > 0.5:  # Yukarı gidiyorsa
                            thrust = -1.0  # Thrust kapat
                    elif current_dy < 0.3:  # Yere değmiş
                        # Yere değdikten sonra: Hafif thrust ile yere basınç (sekme önleme)
                        if vy < -0.5:
                            thrust_factor = min(0.2, abs(vy) / 10.0)
                            thrust = (thrust_factor * 2.0) - 1.0
                        elif abs(vy) < 0.2:
                            thrust = -0.98  # Çok hafif thrust (yer çekimi dengeleme)
                    
                    # Yatay hızları sıfırla
                    if abs(vx) > 0.2:
                        pitch -= 0.2 * np.sign(vx)
                    if abs(vz) > 0.2:
                        yaw -= 0.2 * np.sign(vz)
                    
                    pitch = np.clip(pitch, -1.0, 1.0)
                    yaw = np.clip(yaw, -1.0, 1.0)
                    thrust = np.clip(thrust, -1.0, 1.0)
                    
                    # Action gönder - KRİTİK: environment.step() kullanma, direkt Unity'ye gönder
                    # Çünkü success sonrası yumuşak geçiş episode dışında olmalı,
                    # environment.step() step_count'u artırır ve reward hesaplaması yapar
                    # Bu bir sonraki episode'u etkileyebilir
                    
                    # Thrust normalizasyonu: Unity [0, 1] bekliyor, biz [-1, 1] kullanıyoruz
                    # env.py'deki gibi: thrust = 0.5 * (thrust_raw + 1.0)
                    thrust_normalized = 0.5 * (thrust + 1.0)
                    thrust_normalized = np.clip(thrust_normalized, 0.0, 1.0)
                    
                    # Unity'ye direkt komut gönder (Mode 0: Normal step)
                    environment.con.sendCs((0, pitch, yaw, thrust_normalized, roll, 0, 0, 0, 0, 0, 0, 0, 0))
                    
                    # Unity'den state oku
                    state_raw = as_float32(environment.readStates())
                    smooth_steps += 1
                    
                    # Durum kontrolü
                    current_dy_new = state_raw[1]
                    vy_new = state_raw[4]
                    vx_new = state_raw[3]
                    vz_new = state_raw[5]
                    wx_new = state_raw[6]
                    wy_new = state_raw[7]
                    wz_new = state_raw[8]
                    
                    qx, qy, qz, qw = state_raw[9], state_raw[10], state_raw[11], state_raw[12]
                    qnorm = (qx*qx + qy*qy + qz*qz + qw*qw) ** 0.5
                    if qnorm > 1e-6:
                        qx /= qnorm; qy /= qnorm; qz /= qnorm; qw /= qnorm
                    up_y_new = 1.0 - 2.0*(qx*qx + qz*qz)
                    
                    # Hızların büyüklüğü
                    v_mag = np.sqrt(vx_new**2 + vy_new**2 + vz_new**2)
                    w_mag = np.sqrt(wx_new**2 + wy_new**2 + wz_new**2)
                    
                    # Çıkış koşulları: Dik, yerde, hızlar sıfır
                    height_ok = abs(current_dy_new - TARGET_BOTTOM_HEIGHT) < 0.2
                    upright_ok = up_y_new > 0.95
                    velocities_ok = v_mag < 0.5 and w_mag < 0.5
                    enough_steps = smooth_steps > 20
                    
                    if (upright_ok and height_ok and velocities_ok and enough_steps):
                        break
                    
                    # Timeout
                    if smooth_steps >= max_smooth_steps - 1:
                        break
            else:
                # Success dışındaki tüm terminal durumlar (Spin, Crash, CeilingHit, vb.)
                # Roket havada kalabilir, yere düşmesini bekleyelim
                if reason == "Crash":
                    crash_count += 1
                else:
                    other_count += 1
                
                # Terminal durumda roket havada kalabilir, yere düşmesini bekle
                # Unity'de episode bitince roket donuyor ama fizik devam ediyor
                free_fall_steps = 0
                max_free_fall_steps = 300  # Yeterince uzun (~30 saniye)
                dy_start = state_raw[1]  # Başlangıç yüksekliği
                
                # Roket yerde değilse serbest düşüş bekle
                if dy_start > 0.5:  # 0.5m üstündeyse
                    while free_fall_steps < max_free_fall_steps:
                        # Serbest düşüş: Thrust yok, sadece stabilizasyon (isteğe bağlı)
                        # Not: Terminal durumda Unity episode'i bitirmiş olabilir,
                        # ama fizik simülasyonu devam ediyor olabilir
                        free_fall_action = compute_stability_action(state_raw)
                        
                        # Step gönder - Unity'den state al
                        # ÖNEMLİ: Terminal durumda step() yine de çağrılabilir,
                        # ama Unity'nin episode reset mekanizmasını tetiklememeye dikkat
                        try:
                            next_state_raw, step_done, reward = environment.step(free_fall_action)
                            state_raw = as_float32(next_state_raw)
                            free_fall_steps += 1
                            
                            # State kontrolü: Yere düştü mü?
                            dy = state_raw[1]
                            
                            # Yere düştü (0.5m altı) veya Unity reset oldu
                            if dy <= 0.5:
                                break
                            if dy < -1.0:  # Yerin altına geçti (reset olabilir)
                                break
                            
                            # Eğer yükseklik çok değişmedi ve çok adım geçtiyse dur
                            # (Unity reset olmuş olabilir)
                            if free_fall_steps > 50:
                                dy_current = state_raw[1]
                                if abs(dy_current - dy_start) < 0.1:
                                    # Yükseklik değişmiyor, muhtemelen Unity reset oldu
                                    break
                        except Exception as e:
                            # Unity bağlantı hatası veya reset durumu
                            # Serbest düşüşü durdur
                            break
            
            print(f"{'*'*80}\n")
            
            # Episode limiti kontrolü
            if args.episodes != -1 and test_num >= args.episodes:
                # Limit doldu, otomatik çık
                print(f"\nTest limiti ({args.episodes}) doldu. Test sonlandırılıyor...")
                break
            
            # Episode bitince kullanıcıya soru sor
            while True:
                try:
                    response = input("Tekrar deneyin? (E/H veya Evet/Hayır): ").strip().lower()
                    if response in ['e', 'evet', 'yes', 'y']:
                        # Yeni test başlatılacak - while loop devam edecek ve initialStart() çağrılacak
                        break
                    elif response in ['h', 'hayır', 'no', 'n', 'çıkış', 'çık', 'exit', 'quit', 'q']:
                        # Programı sonlandır
                        print("\nTest sonlandırılıyor...")
                        return
                    else:
                        print("Lütfen 'E' (Evet) veya 'H' (Hayır) girin.")
                except (EOFError, KeyboardInterrupt):
                    # Ctrl+C veya EOF durumunda da çık
                    print("\n\nTest sonlandırılıyor...")
                    return
            
            # KRİTİK: Yeni episode başlamadan ÖNCE environment state'ini temizle
            # initialStart() çağrılacak, Unity'ye yeni reset gönderilecek
            # Bu yüzden environment state'ini temizlemeliyiz ki Unity düzgün reset olsun
            environment.done = False
            environment.step_count = 0
            environment.termination_reason = "Running"
            
    except KeyboardInterrupt:
        print("\n\n" + "*" * 80)
        print("TEST DURDURULDU")
        print("*" * 80)
        print(f"Toplam test: {test_num}")
        if test_num > 0:
            print(f"Başarı: {success_count} ({success_count/test_num*100:.1f}%)")
            print(f"Crash: {crash_count}")
            print(f"Diğer: {other_count}")
        print("*" * 80)

if __name__ == "__main__":
    main()

