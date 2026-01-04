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
            print(f"  log_std yüklendi: {agent.log_std.numpy()}")
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

def format_action(action):
    """Action'ı okunabilir formata çevir"""
    pitch, yaw, thrust, roll = action
    thrust_pct = (thrust + 1) / 2 * 100  # 0-100% arası
    return f"P:{pitch:+.2f} Y:{yaw:+.2f} T:{thrust_pct:.0f}% R:{roll:+.2f}"

def format_state(state_raw):
    """State'i okunabilir formata çevir"""
    dx, dy, dz = state_raw[0], state_raw[1], state_raw[2]
    vx, vy, vz = state_raw[3], state_raw[4], state_raw[5]
    dist_h = np.sqrt(dx**2 + dz**2)
    return {
        'alt': dy,
        'dist': dist_h,
        'vy': vy,
        'vx': vx,
        'vz': vz,
    }

def print_episode_info(episode, step, state_info, action, reward, reason=None):
    """Episode bilgilerini konsola yazdır"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    alt_str = f"Alt:{state_info['alt']:.2f}m"
    dist_str = f"Dist:{state_info['dist']:.2f}m"
    vy_str = f"Vy:{state_info['vy']:.2f}m/s"
    action_str = format_action(action)
    reward_str = f"R:{reward:+.1f}"
    
    line = f"[{timestamp}] EP:{episode} Step:{step:3d} | {alt_str} {dist_str} {vy_str} | {action_str} | {reward_str}"
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
                        help='Kaç episode çalıştırılacak (-1 = süresiz)')
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
    print("=" * 80)
    print("PLAY-TEST BAŞLATILIYOR")
    print("=" * 80)
    print(f"Model: {os.path.basename(model_path)}")
    print(f"Başlangıç koşulları: Yükseklik {environment.init_y_min}-{environment.init_y_max}m, Yatay ±{environment.init_x_max}m")
    print(f"Success bekleme süresi: {args.wait_on_success}s")
    print(f"Episode limiti: {'Süresiz' if args.episodes == -1 else args.episodes}")
    print("=" * 80)
    print("\nÇıkmak için Ctrl+C basın.\n")
    
    episode = 0
    success_count = 0
    crash_count = 0
    other_count = 0
    
    try:
        while args.episodes == -1 or episode < args.episodes:
            episode += 1
            
            # Yeni episode başlat
            environment.initialStart()
            state_raw = as_float32(environment.readStates())
            state_norm = as_float32(environment.normalize_state(state_raw))
            
            # Başlangıç bilgileri
            start_info = format_state(state_raw)
            print(f"\n{'='*80}")
            print(f"EPISODE {episode} BAŞLADI")
            print(f"   Başlangıç: Alt:{start_info['alt']:.2f}m, Dist:{start_info['dist']:.2f}m")
            print(f"{'='*80}")
            
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
                
                # Her adımı göster (eğer isteniyorsa) veya her 10 adımda bir
                if args.show_steps or step % 10 == 0 or done:
                    state_info = format_state(state_raw)
                    reason = getattr(environment, 'termination_reason', None) if done else None
                    print_episode_info(episode, step, state_info, action, reward, reason)
                
                # State güncelle
                state_raw = as_float32(next_state_raw)
                state_norm = as_float32(environment.normalize_state(state_raw))
            
            # Episode sonu - son state zaten elimizde (next_state_raw'dan gelen)
            reason = getattr(environment, 'termination_reason', 'Unknown')
            final_info = format_state(state_raw)  # Son state'i kullan (step()'den gelen)
            
            print(f"\n{'='*80}")
            print(f"EPISODE {episode} BİTTİ")
            print(f"   Sonuç: {reason}")
            print(f"   Step sayısı: {step}")
            print(f"   Toplam reward: {total_reward:.2f}")
            print(f"   Son durum: Alt:{final_info['alt']:.2f}m, Dist:{final_info['dist']:.2f}m, Vy:{final_info['vy']:.2f}m/s")
            
            # İstatistikler
            if reason == "Success":
                success_count += 1
                print(f"   BAŞARILI İNİŞ! ({success_count}. başarı)")
                print(f"   {args.wait_on_success} saniye bekleniyor...")
                time.sleep(args.wait_on_success)
            elif reason == "Crash":
                crash_count += 1
            else:
                other_count += 1
            
            print(f"   İstatistikler: Success:{success_count} | Crash:{crash_count} | Diğer:{other_count} | Başarı Oranı: {success_count/episode*100:.1f}%")
            print(f"{'='*80}\n")
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print("[INFO] TEST DURDURULDU")
        print("=" * 80)
        print(f"Toplam episode: {episode}")
        print(f"Başarı: {success_count} ({success_count/episode*100:.1f}%)")
        print(f"Crash: {crash_count}")
        print(f"Diğer: {other_count}")
        print("=" * 80)

if __name__ == "__main__":
    main()

