import os
import re
import glob
import gzip
import pickle
import warnings
import numpy as np
import tensorflow as tf
warnings.filterwarnings("ignore")

from agent import PPOAgent
from env import Env


def setup_gpu():
    """GPU kullanımını yapılandırır ve etkinleştirir"""
    gpus = tf.config.experimental.list_physical_devices('GPU')
    
    if gpus:
        try:
            # Tüm GPU'lar için bellek büyümesini etkinleştir
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            
            print(f"✓ {len(gpus)} GPU bulundu ve yapılandırıldı:")
            for i, gpu in enumerate(gpus):
                print(f"  - GPU {i}: {gpu.name}")
            print(f"  TensorFlow GPU kullanımını otomatik olarak etkinleştirecek.")
            return True
        except RuntimeError as e:
            print(f"GPU yapılandırma uyarısı: {e}")
            return True
    else:
        print("⚠ GPU bulunamadı, CPU kullanılacak")
        return False


MODELS_DIR = "models"

# --- LOG DOSYALARI ---
EP_LOG_FILE = os.path.join(MODELS_DIR, "episode_logs.csv") # Klasik özet log
UP_LOG_FILE = os.path.join(MODELS_DIR, "update_logs.csv")  # PPO eğitim verileri
DETAILED_LOG_FILE = os.path.join(MODELS_DIR, "detailed_log.csv") # Sebep sonuç analizi
STATE_LOG_FILE = os.path.join(MODELS_DIR, "state_log.csv") # Saniye saniye grafik verisi

if not os.path.exists(MODELS_DIR):
    os.makedirs(MODELS_DIR)

def as_float32(x):
    return np.asarray(x, dtype=np.float32)

def save_agent_state(agent, path, extra=None):
    state = {
        "log_std": agent.log_std.numpy().tolist(),
    }
    if extra:
        state.update(extra)

    tmp = path + ".tmp"
    with gzip.open(tmp, "wb") as f:
        pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)


def load_agent_state(agent: PPOAgent, path: str):
    if not os.path.exists(path):
        return {}
    with gzip.open(path, "rb") as f:
        state = pickle.load(f)

    if "log_std" in state:
        loaded_log_std = np.array(state["log_std"], dtype=np.float32)
        expected_size = agent.action_size
        
        if len(loaded_log_std) != expected_size:
            print(f"⚠ UYARI: log_std boyutu uyuşmuyor. Varsayılanlar kullanılacak.")
        else:
            agent.log_std.assign(loaded_log_std)
            print(f"Agent state yüklendi. log_std: {agent.log_std.numpy()}")
    else:
        print("log_std bulunamadı, varsayılan değerler kullanılıyor.")
        
    return state


def latest_index(pattern, regex=r"_up(\d+)\.keras$"):
    files = glob.glob(pattern)
    if not files:
        return None
    nums = []
    for p in files:
        m = re.search(regex, os.path.basename(p))
        if m:
            nums.append(int(m.group(1)))
    return max(nums) if nums else None

if __name__ == "__main__":
    setup_gpu()
    
    enviroment = Env()
    ajan = PPOAgent()

    ROLLOUT_LEN = 1024
    TOTAL_UPDATES = 5000
    SAVE_EVERY_UPDATES = 20

    # Resume işlemleri
    start_update = 0
    last_up = latest_index(os.path.join(MODELS_DIR, "rocket_model_up*.keras"))

    if last_up is not None:
        print(f"Kayıtlı model bulundu: Update {last_up}. Yükleniyor...")
        model_path = os.path.join(MODELS_DIR, f"rocket_model_up{last_up}.keras")
        
        model_loaded = False
        try:
            loaded_model = tf.keras.models.load_model(model_path, compile=False)
            test_input = tf.zeros((1, ajan.state_size), dtype=tf.float32)
            mu_output, v_output = loaded_model(test_input)
            
            if mu_output.shape[-1] != ajan.action_size:
                print(f"⚠ KRİTİK UYARI: Action size uyuşmazlığı! Sıfırdan başlanıyor.")
                model_loaded = False
            else:
                ajan.model = loaded_model
                print(f"Model başarıyla yüklendi. Action size: {mu_output.shape[-1]}")
                model_loaded = True
        except Exception as e:
            print(f"⚠ Model yüklenirken hata: {e}")
            model_loaded = False

        if model_loaded:
            state_path = os.path.join(MODELS_DIR, f"rocket_state_up{last_up}.pkl.gz")
            extra_state = load_agent_state(ajan, state_path)
            start_update = last_up + 1
            print(f"Devam: start_update={start_update}")
        else:
            start_update = 0
            last_up = None
    
    # --- LOG BAŞLIKLARI OLUŞTURMA ---
    if last_up is None:
        with open(EP_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("Episode,Return,EpisodeLen,Update\n")
        with open(UP_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("Update,Loss,PolicyLoss,ValueLoss,Entropy,KL,ClipFrac\n")

    # Yeni eklenen log dosyaları için başlık kontrolü (Resume olsa bile yoksa oluştur)
    if not os.path.exists(DETAILED_LOG_FILE):
        with open(DETAILED_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("Episode,Update,Return,Length,Reason,StartAlt\n")
            
    if not os.path.exists(STATE_LOG_FILE):
        with open(STATE_LOG_FILE, "w", encoding="utf-8") as f:
            # Zaman, Yükseklik, KonumX, HızY, Motor Gücü, Pitch Açısı, Anlık Ödül
            f.write("Update,Episode,Step,dy,dx,vy,thrust,pitch,reward\n")


    # Episode sayaçları
    episode = 0
    ep_return = 0.0
    ep_len = 0

    # İlk reset
    enviroment.initialStart()
    state = as_float32(enviroment.readStates())
    start_altitude = state[1] # Başlangıç irtifasını kaydet

    for up in range(start_update, TOTAL_UPDATES):
        # ---- rollout buffers ----
        states = np.zeros((ROLLOUT_LEN, ajan.state_size), dtype=np.float32)
        actions = np.zeros((ROLLOUT_LEN, ajan.action_size), dtype=np.float32)
        old_logps = np.zeros((ROLLOUT_LEN,), dtype=np.float32)
        rewards = np.zeros((ROLLOUT_LEN,), dtype=np.float32)
        dones = np.zeros((ROLLOUT_LEN,), dtype=np.float32)
        values = np.zeros((ROLLOUT_LEN,), dtype=np.float32)

        # ---- collect rollout ----
        for t in range(ROLLOUT_LEN):
            action, logp, value = ajan.act(state)

            next_state, done, reward = enviroment.step(action)

            # --- STATE LOGGING (RAM dostu: Anlık yaz ve kapat) ---
            # Sadece analiz etmek istediğinde bu bloğu açık tut. Çok hızlı veri yazar.
            # Şu an "append" modunda olduğu için RAM şişirmez.
            with open(STATE_LOG_FILE, "a", encoding="utf-8") as f:
                thrust_val = (action[2] + 1) / 2 # Normalize thrust (0-1 arası görmek için)
                # state[1]=dy, state[0]=dx, state[4]=vy, state[9]=qx(pitch related approx)
                f.write(f"{up},{episode},{t},{state[1]:.2f},{state[0]:.2f},{state[4]:.2f},{thrust_val:.2f},{state[9]:.2f},{reward:.3f}\n")
            # -----------------------------------------------------

            states[t] = state
            actions[t] = action
            old_logps[t] = logp
            rewards[t] = reward
            dones[t] = 1.0 if done else 0.0
            values[t] = value

            ep_return += reward
            ep_len += 1

            state = as_float32(next_state)

            if done:
                episode += 1
                
                # Env.py içindeki termination_reason'ı al (Eğer yoksa 'Unknown' yazar)
                reason = getattr(enviroment, 'termination_reason', 'Unknown')
                
                print(f"[EP {episode}] {reason} | Return={ep_return:.2f} | Alt={start_altitude:.1f}m (up={up})")

                with open(EP_LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{episode},{ep_return:.6f},{ep_len},{up}\n")

                # --- DETAILED LOGGING (Detaylı Rapor) ---
                with open(DETAILED_LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{episode},{up},{ep_return:.4f},{ep_len},{reason},{start_altitude:.2f}\n")
                # ----------------------------------------

                # reset episode
                enviroment.initialStart()
                state = as_float32(enviroment.readStates())
                start_altitude = state[1] # Yeni bölümün başlangıç yüksekliğini al
                
                ep_return = 0.0
                ep_len = 0

        # ---- bootstrap last_value ----
        s_tf = tf.convert_to_tensor(state[None, :], dtype=tf.float32)
        _, v_tf = ajan.model(s_tf)
        last_value = float(tf.squeeze(v_tf, axis=0).numpy()[0])

        # ---- PPO update ----
        logs = ajan.train(
            states=states,
            actions=actions,
            old_logps=old_logps,
            rewards=rewards,
            dones=dones,
            values=values,
            last_value=last_value,
        )

        with open(UP_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{up},{logs['loss']:.6f},{logs['policy_loss']:.6f},{logs['value_loss']:.6f},{logs['entropy']:.6f},{logs['kl']:.6f},{logs['clip_frac']:.6f}\n")

        if (up + 1) % 10 == 0:
            print(f"[UP {up+1}] loss={logs['loss']:.4f} pl={logs['policy_loss']:.4f} vl={logs['value_loss']:.4f} ent={logs['entropy']:.4f} kl={logs['kl']:.4f}")

        # ---- save checkpoint ----
        if (up + 1) % SAVE_EVERY_UPDATES == 0:
            print(f"[SAVE] Update {up+1}: Model kaydediliyor...")
            m_path = os.path.join(MODELS_DIR, f"rocket_model_up{up+1}.keras")
            ajan.model.save(m_path)
            s_path = os.path.join(MODELS_DIR, f"rocket_state_up{up+1}.pkl.gz")
            save_agent_state(ajan, s_path, extra={"update": up + 1, "episode": episode})


########################################################
# start_episode = 0
# if not os.path.exists(MODELS_DIR):
#     os.makedirs(MODELS_DIR)

# def save_agent_state(agent, path):
#     state = {
#         "epsilon": agent.epsilon,
#         "memory": list(agent.memory),
#     }
#     tmp = path + ".tmp"
#     with gzip.open(tmp, "wb") as f:
#         pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
#     os.replace(tmp, path)

# def load_agent_state(agent, path):
#     if not os.path.exists(path): return
#     with gzip.open(path, "rb") as f:
#         state = pickle.load(f)
#     agent.epsilon = state.get("epsilon", agent.epsilon)
#     agent.memory = deque(state.get("memory", []), maxlen=agent.memory.maxlen)
#     print(f"Agent state yüklendi. Epsilon: {agent.epsilon:.4f}, Memory: {len(agent.memory)}")

# def latest_episode(pattern):
#     files = glob.glob(pattern)
#     if not files: return None
#     nums = []
#     for p in files:
#         m = re.search(r"_ep(\d+)\.keras$", os.path.basename(p))
#         if m: nums.append(int(m.group(1)))
#     return max(nums) if nums else None

# def as_float32(x):
#     return np.asarray(x, dtype=np.float32)
# EPISODES = 5000

# enviroment = env.Env()
# ajan = agent.Agent()
# last_ep = latest_episode(os.path.join(MODELS_DIR, "rocket_model_ep*.keras"))

# initİal_states = ""
# if last_ep is not None:
#     print(f"Kayıtlı model bulundu: Episode {last_ep}. Yükleniyor")
#     model_path = os.path.join(MODELS_DIR, f"rocket_model_ep{last_ep}.keras")
#     ajan.load(model_path) 
#     state_path = os.path.join(MODELS_DIR, f"rocket_state_ep{last_ep}.pkl.gz")
#     load_agent_state(ajan, state_path)
    
#     start_episode = last_ep + 1
# else:
#     print("Kayıt bulunamadı, sıfırdan başlanıyor.")
#     with open(LOG_FILE, "w") as f:
#         f.write("Episode,Reward,Epsilon\n")


# for e in range(start_episode, EPISODES):
        
#     total_rewards = 0
#     enviroment.initialStart()

#     initİal_states = enviroment.readStates() 

#     states = initİal_states
#     while True:
            
#         action = ajan.act(states)

#         next_state, done, reward = enviroment.step(action)
#         total_rewards += reward

#         ajan.remember(states,action,reward,next_state,done)

#         states = next_state
#         ajan.replay()

#         ajan.adaptiveEGreedy()

#         if done == True:
#             break

#     print(f"Episode: {e+1} - Total Reward: {total_rewards}")

#     with open(LOG_FILE, "a") as f:
#         f.write(f"{e+1},{total_rewards},{ajan.epsilon:.5f}\n")

#     if (e + 1) % 20 == 0:
#         print(f"Episode {e+1}: Model kaydediliyor")
            

#         m_path = os.path.join(MODELS_DIR, f"rocket_model_ep{e+1}.keras")
#         ajan.save(m_path)
            
#         s_path = os.path.join(MODELS_DIR, f"rocket_state_ep{e+1}.pkl.gz")
#         save_agent_state(ajan, s_path)

#     e +=1



########################
# create agent

#######################
# epsiode loop
# save model
# save log

#######################
