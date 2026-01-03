import connector
import numpy as np
ip = "127.0.0.1"
port = 5000

# SINIRLAR
# dx max = 1200
# dy max = 80
# dz max = 80
# vx min = -2 (aşağı doğru en az 2 ile gitmeli) max = yok
# vy, vz = yok
# qx,qy,qz,qw ise pitch max 50, yaw=50 olacak şekilde.
# wx, wy, wz belirlenecek

class Env():

    def __init__(self):
        self.con = connector.Connector(ip,port)
        self.done = False
        self.termination_reason = "TimeLimit"
        self.max_steps = 800
        self.step_count = 0
        
        # Başlangıç değerleri - kolayca değiştirilebilir
        self.init_y_min = 5.0
        self.init_y_max = 15.0
        self.init_z_min = -5.0
        self.init_z_max = 5.0
        self.init_x_min = -5.0
        self.init_x_max = 5.0
        self.init_pitch_min = -2.0
        self.init_pitch_max = 2.0
        self.init_yaw_min = -2.0
        self.init_yaw_max = 2.0
        
        # State normalizasyon ölçekleri (log-compress için)
        # Konuşma bazlı: state_normalization_discussion.txt
        self.dx_scale = 45.0  # Yatay pozisyon limiti
        self.dy_scale = 50.0  # Yükseklik ölçeği
        self.v_scale = 25.0   # Doğrusal hız ölçeği (m/s)
        self.w_scale = 4.0    # Açısal hız ölçeği (rad/s)

    def log_norm(self, x, scale):
        """
        Log-compress normalizasyon: np.clip(np.sign(x) * np.log1p(abs(x)/scale), -1.0, 1.0)
        Düşük değerler hassas kalır, yüksek değerler aşırı saturate olmaz.
        """
        return np.clip(np.sign(x) * np.log1p(np.abs(x) / scale), -1.0, 1.0)
    
    def normalize_state(self, states):
        """
        State normalizasyonu: Agent'a gönderilen state'leri normalize eder.
        State format: [dx, dy, dz, vx, vy, vz, wx, wy, wz, qx, qy, qz, qw]
        
        Normalizasyon stratejisi:
        - dx, dz: Basit normalize (/45)
        - dy: Log-compress (scale=50)
        - vx, vy, vz: Log-compress (scale=25 m/s)
        - wx, wy, wz: Log-compress (scale=4 rad/s)
        - qx, qy, qz, qw: Zaten [-1, 1] aralığında, dokunma
        """
        states_norm = states.copy().astype(np.float32)
        
        # Pozisyon: dx, dz -> basit normalize
        states_norm[0] = np.clip(states[0] / self.dx_scale, -1.0, 1.0)  # dx
        states_norm[2] = np.clip(states[2] / self.dx_scale, -1.0, 1.0)  # dz
        
        # Yükseklik: dy -> log-compress
        states_norm[1] = self.log_norm(states[1], self.dy_scale)  # dy (sadece pozitif, ama sign korunur)
        
        # Doğrusal hız: vx, vy, vz -> log-compress
        states_norm[3] = self.log_norm(states[3], self.v_scale)  # vx
        states_norm[4] = self.log_norm(states[4], self.v_scale)  # vy
        states_norm[5] = self.log_norm(states[5], self.v_scale)  # vz
        
        # Açısal hız: wx, wy, wz -> log-compress
        states_norm[6] = self.log_norm(states[6], self.w_scale)  # wx
        states_norm[7] = self.log_norm(states[7], self.w_scale)  # wy
        states_norm[8] = self.log_norm(states[8], self.w_scale)  # wz
        
        # Quaternion: qx, qy, qz, qw -> zaten normalize, dokunma
        # states_norm[9:13] = states[9:13]  # Değişiklik yok
        
        return states_norm

    def parse_states(self,s:str):
        s = s.strip().replace('\n', '').replace('\r', '')
        if not s:
            raise ValueError("Boş state string alındı")
        arr = s.split(",")
        arr = [x.strip() for x in arr if x.strip()]
        if len(arr) != 13:
            raise ValueError(f"Beklenen 13 eleman, ancak {len(arr)} eleman alındı. State: {s[:100]}")
        states = np.array([float(x) for x in arr], dtype=np.float32)
        return states
        
    def compute_reward_done(self, states):
        self.termination_reason = "Running"
        reward = 0.0
        done = False

        dx, dy, dz = map(float, states[0:3])
        vx, vy, vz = map(float, states[3:6])
        wx, wy, wz = map(float, states[6:9])
        qx, qy, qz, qw = map(float, states[9:13])

        # Quaternion normalize
        qnorm = (qx*qx + qy*qy + qz*qz + qw*qw) ** 0.5
        if qnorm > 1e-6:
            qx/=qnorm; qy/=qnorm; qz/=qnorm; qw/=qnorm

        up_y = 1.0 - 2.0*(qx*qx + qz*qz)

        dist_h = (dx*dx + dz*dz) ** 0.5
        v_h    = (vx*vx + vz*vz) ** 0.5
        w_mag  = (wx*wx + wy*wy + wz*wz) ** 0.5

        # --- TERMINAL ---
        # Ceiling: Daha erken yakala ve çok sert cezalandır (yukarı kaçmayı önle)
        if dy >= 50.0 and vy > 0.3:  # Threshold düşürüldü: 75→50, 0.5→0.3
            self.termination_reason = "CeilingHit"
            return -1000.0, True  # Penalty 2x artırıldı: -500 → -1000

        if abs(dx) >= 25.0 or abs(dz) >= 25.0:
            self.termination_reason = "OutOfBounds"
            return -500.0, True

        # Tilt: low'da çok devrildiyse bitir
        if up_y < 0.35:
            self.termination_reason = "Tilted"
            return -500.0, True

        if w_mag > 10.0:
            self.termination_reason = "Spin"
            return -500.0, True

        # --- LANDING CHECK ---
        if dy <= 1.5:
            # zone: kare yerine daire daha stabil
            in_zone = (dist_h < 4.5)  # gevşetildi: 3.0 → 4.5 (low stage için daha fazla tolerans)

            if not in_zone:
                self.termination_reason = "MissedZone"
                return -350.0, True

            ok_vy   = (abs(vy) <= 2.5)   # sıkılaştırıldı: 4.5 → 2.5 (daha yumuşak iniş)
            ok_vh   = (v_h <= 2.0)       # sıkılaştırıldı: 3.0 → 2.0 (daha kontrollü)
            ok_tilt = (up_y >= 0.85)     # aynı
            ok_spin = (w_mag <= 4.0)     # aynı

            if ok_vy and ok_vh and ok_tilt and ok_spin:
                bonus = (self.max_steps - self.step_count) * 0.1
                self.termination_reason = "Success"
                return 1500.0 + bonus, True
            else:
                self.termination_reason = "Crash"
                return -300.0, True

        # --- SHAPING ---
        reward += -0.02

        # YUKARI GİTME CEZASI (yukarı kaçmayı önle)
        if vy > 0.0:  # Yukarı gidiyorsa
            # İrtifa arttıkça artan penalty: dy=20m → küçük, dy=40m → büyük
            up_penalty = 0.15 * vy * (dy / 20.0)  # dy=40m, vy=2 → ~0.6 ceza
            reward -= up_penalty

        # merkeze uzaklık cezası (azaltıldı: hız kontrolüne yer açmak için)
        reward += -0.02 * dist_h

        # yatay hız cezası (artırıldı: drift'i azaltmak için)
        reward += -0.06 * v_h

        # VERTICAL VELOCITY: HER İRTİFADA AKTİF (PROGRESSIVE)
        # Yüksek irtifada küçük ceza, düşük irtifada büyük ceza
        if vy < 0.0:  # Aşağı düşüyorsa
            # İrtifa azaldıkça artan penalty: dy=20m → ~0.5x, dy=5m → ~1.5x, dy=1.5m → ~2.0x
            altitude_factor = 1.0 + (15.0 / (dy + 1.0))
            reward -= 0.08 * abs(vy) * altitude_factor

        # stabilite: penalty ve bonus dengeli
        if up_y < 0.85:
            reward += -0.08 * (0.85 - up_y)
        else:
            reward += 0.08 * (up_y - 0.85)  # Bonus eşit ağırlıkta

        # küçük spin cezası
        reward += -0.01 * w_mag
        
        # YERE YAKLAŞMA BONUSU (agent'ı inişe teşvik et)
        if dy < 20.0:
            approach_bonus = 0.05 * np.exp(-dy / 5.0)  # Max ~0.05
            reward += approach_bonus
        
        # YAVAŞ İNİŞ BONUSU (vy > -2 m/s iken)
        if vy < 0.0 and abs(vy) < 2.0:
            slow_descent_bonus = 0.03 * (2.0 - abs(vy)) / 2.0  # Max ~0.03
            reward += slow_descent_bonus

        if self.step_count >= self.max_steps:
            self.termination_reason = "TimeLimit"
            return reward - 60.0, True

        return reward, False


        # --- 3. ADIM BAŞI ÖDÜL/CEZA (SHAPING) ---
        # Buraya geldiyse havada demektir (dy > 1.0) ve oyun bitmemiştir.

        # Temel Yaşam Maliyeti (Az olsun ki hemen intihar etmesin)
        step_penalty = -0.02 

        # Merkeze Uzaklık Cezası (Sürekli merkeze çekmek için)
        dist_horizontal = np.sqrt(dx**2 + dz**2)
        dist_penalty = dist_horizontal * 0.05
        
        # Shaping (Doğru yoldaysa ufak ödüller)
        shaping_pos = 0.0
        shaping_pos += 0.05 * np.exp(-1.0 * abs(dy) / 30.0)      # Yere yaklaştıkça artar
        shaping_pos += 0.05 * np.exp(-1.0 * dist_horizontal / 10.0) # Merkeze yaklaştıkça artar
        
        # Stabilite Bonusu (Dik durduğu için aferin)
        shaping_stab = 0.04 * up_vector_y if up_vector_y > 0.5 else 0.0

        # Dikey Hız Cezası (Sadece yere yakınken çok hızlıysa devreye girer)
        velocity_penalty = 0.0
        if vy < 0 and dy < 15.0: 
            # Yere yaklaştıkça hızlanmak daha pahalı olur
            velocity_penalty = abs(vy) * (1.0 / (dy + 1.0)) * 0.05

        # Yatay Hız Cezası (GÜNCELLENDİ: 0.1 -> 0.03)
        # Rahat manevra yapsın diye gevşettik.
        horizontal_speed = np.sqrt(vx**2 + vz**2)
        horizontal_penalty = horizontal_speed * 0.03 
        
        # Toplam Adım Ödülü Hesaplama
        current_step_reward = (
            step_penalty 
            - dist_penalty 
            + shaping_pos 
            + shaping_stab 
            - velocity_penalty 
            - horizontal_penalty 
            - (0.01 * abs_roll)
        )
        
        reward += current_step_reward

        # Zaman sınırı kontrolü
        if self.step_count >= self.max_steps:
            self.termination_reason = "TimeLimit"
            reward += -60.0  # Zaman doldu cezası
            done = True
            return reward, done

        return reward, done
    
    
    def step(self, action):
        """
        Action format: [pitch, yaw, thrust_raw, roll]
        - pitch: [-1, 1] -> RCS pitch control
        - yaw: [-1, 1] -> RCS yaw control  
        - thrust_raw: [-1, 1] -> normalized to [0, 1] for main engine
        - roll: [-1, 1] -> RCS roll control
        """
        self.step_count += 1
        pitch = float(action[0])
        yaw = float(action[1])

        thrust_yaw = float(action[2])
        thrust = 0.5 * (thrust_yaw + 1.0)
        thrust = float(np.clip(thrust, 0.0, 1.0))
        
        roll = float(action[3])  # Roll kontrolü

        # Unity'e gönder
        self.con.sendCs((0, pitch, yaw, thrust, roll, 0, 0, 0, 0, 0, 0, 0, 0))  
        
        # Unity'den gelen yeni durumu oku
        states = self.parse_states(self.con.readCs())
        
        # Ödülü hesapla
        reward_step, done = self.compute_reward_done(states)
        
        # --- KRİTİK EKLEME: REWARD SCALING ---
        # Ödülü 2'ye bölüyoruz (0.1 → 0.5). (+500 -> +250, -500 -> -250)
        # Shaping signal'ların görünür olması için scaling artırıldı.
        # Value Loss patlaması riski düşük (0.5x güvenli aralıkta).
        reward_step *= 0.5 
        # -------------------------------------

        self.done = bool(done)
        
        # Raw state döndür (loglar için). Normalize işlemi train_main.py'de yapılacak
        return states.tolist(), self.done, float(reward_step)
    

    def initialStart(self):
        self.done = False
        self.step_count = 0
        # Başlangıç değerleri sınıf parametrelerinden alınıyor
        y = np.random.uniform(self.init_y_min, self.init_y_max)
        z = np.random.uniform(self.init_z_min, self.init_z_max)
        x = np.random.uniform(self.init_x_min, self.init_x_max)
        pitch = np.random.uniform(self.init_pitch_min, self.init_pitch_max)
        yaw = np.random.uniform(self.init_yaw_min, self.init_yaw_max)

        self.con.sendCs((1,x,y,z,pitch,yaw,0,0,0,0,0,0,0,0))

    def readStates(self):
        states = self.parse_states(self.con.readCs())
        return states.tolist()

    



