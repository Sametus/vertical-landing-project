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
    """Deterministik action (exploration yok, sadece mean)"""
    s = tf.convert_to_tensor(state[None,:], tf.float32)
    mu, _ = agent.model(s)
    mu = tf.squeeze(mu, 0)
    # Tanh uygula (action space [-1, 1])
    a = tf.tanh(mu)
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
                
                # Serbest düşüş: Success sonrası roketin yere düşmesi için
                # ÖNEMLİ: Training'de serbest düşüş yok, ama test için ekliyoruz
                # Unity'nin episode reset mekanizmasını tetiklememek için dikkatli olmalıyız
                free_fall_steps = 0
                max_free_fall_steps = 200
                
                # Serbest düşüş döngüsü
                while free_fall_steps < max_free_fall_steps:
                    free_fall_action = compute_stability_action(state_raw)
                    
                    # Step gönder - Unity'den state al
                    next_state_raw, step_done, reward = environment.step(free_fall_action)
                    state_raw = as_float32(next_state_raw)
                    free_fall_steps += 1
                    
                    # State kontrolü
                    free_fall_info = format_state(state_raw)
                    dy = state_raw[1]
                    up_y = free_fall_info['up_y']
                    
                    if dy <= 0.2:
                        break
                    if dy < -0.5:
                        break
                    if up_y < 0.2:
                        break
            elif reason == "Crash":
                crash_count += 1
            else:
                other_count += 1
            
            print(f"{'*'*80}\n")
            
            # Training mantığı: Episode bitince direkt initialStart() çağrılıyor
            # environment.done ve step_count'u initialStart() içinde zaten sıfırlanıyor
            # Bu yüzden burada manuel sıfırlama gereksiz ve sorun çıkarabilir
            
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

