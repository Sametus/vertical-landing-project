import os
import re
import glob
import gzip
import pickle
import warnings
import numpy as np
import tensorflow as tf
from datetime import datetime
warnings.filterwarnings("ignore")

from agent import PPOAgent
from env import Env

def setup_gpu():
    """GPU kullanımını yapılandırır ve etkinleştirir"""
    gpus = tf.config.experimental.list_physical_devices('GPU')
    if gpus:
        try:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            print(f"✓ {len(gpus)} GPU bulundu ve yapılandırıldı.")
            return True
        except RuntimeError as e:
            print(f"GPU yapılandırma uyarısı: {e}")
            return True
    else:
        print("⚠ GPU bulunamadı, CPU kullanılacak")
        return False

MODELS_DIR = "models"

# --- LOG DOSYALARI ---
EP_LOG_FILE = os.path.join(MODELS_DIR, "episode_logs.csv") 
UP_LOG_FILE = os.path.join(MODELS_DIR, "update_logs.csv")  
DETAILED_LOG_FILE = os.path.join(MODELS_DIR, "detailed_log.csv") # <-- ÖNEMLİ OLAN BU
STATE_LOG_FILE = os.path.join(MODELS_DIR, "state_log.csv") 

if not os.path.exists(MODELS_DIR):
    os.makedirs(MODELS_DIR)

def as_float32(x):
    return np.asarray(x, dtype=np.float32)

def save_agent_state(agent, path, extra=None):
    state = { "log_std": agent.log_std.numpy().tolist() }
    if extra: state.update(extra)
    tmp = path + ".tmp"
    with gzip.open(tmp, "wb") as f:
        pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)

def load_agent_state(agent: PPOAgent, path: str):
    if not os.path.exists(path): return {}
    with gzip.open(path, "rb") as f:
        state = pickle.load(f)
    if "log_std" in state:
        agent.log_std.assign(np.array(state["log_std"], dtype=np.float32))
    return state

def latest_index(pattern, regex=r"_up(\d+)\.keras$"):
    files = glob.glob(pattern)
    if not files: return None
    nums = []
    for p in files:
        m = re.search(regex, os.path.basename(p))
        if m: nums.append(int(m.group(1)))
    return max(nums) if nums else None

if __name__ == "__main__":
    setup_gpu()
    
    enviroment = Env()
    ajan = PPOAgent()

    ROLLOUT_LEN = 1800
    TOTAL_UPDATES = 10000 # Uzun soluklu eğitim için artırdım
    SAVE_EVERY_UPDATES = 20

    # Resume işlemleri
    start_update = 0
    last_up = latest_index(os.path.join(MODELS_DIR, "rocket_model_up*.keras"))

    if last_up is not None:
        print(f"Kayıtlı model bulundu: Update {last_up}. Yükleniyor...")
        try:
            ajan.model = tf.keras.models.load_model(os.path.join(MODELS_DIR, f"rocket_model_up{last_up}.keras"), compile=False)
            load_agent_state(ajan, os.path.join(MODELS_DIR, f"rocket_state_up{last_up}.pkl.gz"))
            start_update = last_up + 1
            print(f">>> Başarılı! Update {start_update}'den devam ediliyor.")
        except Exception as e:
             print(f"HATA: Model yüklenemedi! Sıfırdan başlanıyor. {e}")
    
    # --- LOG BAŞLIKLARI (Yoksa Oluştur) ---
    if not os.path.exists(EP_LOG_FILE):
        with open(EP_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("Episode,Return,EpisodeLen,Update\n")
            
    if not os.path.exists(UP_LOG_FILE):
        with open(UP_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("Update,Loss,PolicyLoss,ValueLoss,Entropy,KL,ClipFrac\n")

    # DETAYLI LOG BAŞLIĞI
    if not os.path.exists(DETAILED_LOG_FILE):
        with open(DETAILED_LOG_FILE, "w", encoding="utf-8") as f:
            # Difficulty sütunu ekledim
            f.write("Episode,Update,Return,Reason,StartAlt,StartDist,Difficulty\n")
            
    if not os.path.exists(STATE_LOG_FILE):
        with open(STATE_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("Update,Episode,Step,dy,dx,vy,thrust,pitch,reward\n")

    # Değişkenler
    episode = 0
    ep_return = 0.0
    ep_len = 0

    # İlk Reset
    enviroment.initialStart()
    state_raw = as_float32(enviroment.readStates())
    state_norm = as_float32(enviroment.normalize_state(state_raw))
    
    # --- BAŞLANGIÇ KOŞULLARINI KAYDET (Start Conditions) ---
    start_alt = state_raw[1]  # Raw state loglar için
    start_dist = np.sqrt(state_raw[0]**2 + state_raw[2]**2)
    # -------------------------------------------------------

    for up in range(start_update, TOTAL_UPDATES):
        states = np.zeros((ROLLOUT_LEN, ajan.state_size), dtype=np.float32)
        actions = np.zeros((ROLLOUT_LEN, ajan.action_size), dtype=np.float32)
        old_logps = np.zeros((ROLLOUT_LEN,), dtype=np.float32)
        rewards = np.zeros((ROLLOUT_LEN,), dtype=np.float32)
        dones = np.zeros((ROLLOUT_LEN,), dtype=np.float32)
        values = np.zeros((ROLLOUT_LEN,), dtype=np.float32)

        for t in range(ROLLOUT_LEN):
            action, logp, value = ajan.act(state_norm)  # Agent normalize state kullanır
            next_state_raw, done, reward = enviroment.step(action)

            # --- 1. DETAYLI ADIM LOGU (State & Actions) ---
            # Her adımı kaydeder: Ne yaptı? (Thrust, Pitch) -> Ne Oldu? (dy, dx, vy)
            # LOGLAR RAW STATE KULLANIR
            with open(STATE_LOG_FILE, "a", encoding="utf-8") as f:
                thrust_val = (action[2] + 1) / 2 # Normalize (0-1 arası okumak için)
                pitch_cmd = action[0]
                # Format: up, ep, step, dy(yükseklik), dx(konum), vy(hız), thrust, pitch, reward
                f.write(f"{up},{episode},{t},{state_raw[1]:.2f},{state_raw[0]:.2f},{state_raw[4]:.2f},{thrust_val:.2f},{pitch_cmd:.2f},{reward:.3f}\n")

            # Agent training için normalize edilmiş state sakla
            states[t] = state_norm
            actions[t] = action
            old_logps[t] = logp
            rewards[t] = reward
            dones[t] = 1.0 if done else 0.0
            values[t] = value

            ep_return += reward
            ep_len += 1
            
            # Raw ve normalize state'leri güncelle
            state_raw = as_float32(next_state_raw)
            state_norm = as_float32(enviroment.normalize_state(state_raw))

            if done:
                episode += 1
                reason = getattr(enviroment, 'termination_reason', 'Unknown')
                
                # --- SONUÇ ANALİZİ (Post-Mortem) ---
                # Bölüm bittiğinde roketin son durumu neydi?
                # LOGLAR RAW STATE KULLANIR
                final_alt = state_raw[1]
                final_dist = np.sqrt(state_raw[0]**2 + state_raw[2]**2)
                final_vel = state_raw[4] # Yere çarpma hızı (vy)
                
                # --- TEMİZ KONSOL ÇIKTISI ---
                # Örnek: [EP 10] Crash | Ret: -500 | Start: 40m/5m | End: 0m/12m | Vel: -9.5
                # Format: Start: [Dikey (Alt)] / [Yatay (Dist)], End: [Dikey (Alt)] / [Yatay (Dist)]
                # PID ve timestamp eklendi: multiple instance'ları ayırt etmek için
                pid = os.getpid()
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                log_str = f"[PID {pid}] [EP {episode:<5}] {reason:<12} | Ret: {ep_return:>7.1f} | "
                log_str += f"Start: {start_alt:>4.1f}m / {start_dist:>4.1f}m | "
                log_str += f"End: {final_alt:>4.1f}m / {final_dist:>4.1f}m | Vel: {final_vel:>5.1f} m/s | {timestamp}"
                
                # Başarılı ise YEŞİL yap, dikkat çeksin
                # flush=True: Buffer sorununu çözer, output hemen görünür
                if reason == "Success":
                    print(f"\033[92m{log_str}\033[0m", flush=True) 
                else:
                    print(log_str, flush=True)

                # 1. Özet CSV (Excel için)
                with open(EP_LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{episode},{ep_return:.6f},{ep_len},{up}\n")

                # 2. Detaylı CSV (Analiz için)
                with open(DETAILED_LOG_FILE, "a", encoding="utf-8") as f:
                    # Low/Med etiketlerini kaldırdım, saf veri ekledim
                    f.write(f"{episode},{up},{ep_return:.4f},{reason},{start_alt:.2f},{start_dist:.2f},{final_dist:.2f},{final_vel:.2f}\n")

                # --- YENİ BÖLÜM ---
                enviroment.initialStart()
                state_raw = as_float32(enviroment.readStates())
                state_norm = as_float32(enviroment.normalize_state(state_raw))
                
                # Yeni başlangıç şartlarını al (RAW STATE)
                start_alt = state_raw[1]
                start_dist = np.sqrt(state_raw[0]**2 + state_raw[2]**2)
                
                ep_return = 0.0
                ep_len = 0

        # PPO Update Loop (normalize edilmiş state kullan)
        s_tf = tf.convert_to_tensor(state_norm[None, :], dtype=tf.float32)
        _, v_tf = ajan.model(s_tf)
        last_value = float(tf.squeeze(v_tf, axis=0).numpy()[0])

        logs = ajan.train(states, actions, old_logps, rewards, dones, values, last_value)

        with open(UP_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{up},{logs['loss']:.6f},{logs['policy_loss']:.6f},{logs['value_loss']:.6f},{logs['entropy']:.6f},{logs['kl']:.6f},{logs['clip_frac']:.6f}\n")

        if (up + 1) % 10 == 0:
            pid = os.getpid()
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[PID {pid}] [UP {up+1}] loss={logs['loss']:.4f} ent={logs['entropy']:.4f} kl={logs['kl']:.4f} | {timestamp}", flush=True)

        if (up + 1) % SAVE_EVERY_UPDATES == 0:
            print(f"[SAVE] Update {up+1}: Model kaydediliyor...")
            ajan.model.save(os.path.join(MODELS_DIR, f"rocket_model_up{up+1}.keras"))
            save_agent_state(ajan, os.path.join(MODELS_DIR, f"rocket_state_up{up+1}.pkl.gz"), {"update": up + 1})