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

        # State'leri çek
        dx = float(states[0])
        dy = float(states[1])
        dz = float(states[2])
        vx = float(states[3])
        vy = float(states[4])
        vz = float(states[5])
        
        wx = float(states[6]) 
        wy = float(states[7]) 
        wz = float(states[8]) 
        
        qx = float(states[9])
        qy = float(states[10])
        qz = float(states[11])
        qw = float(states[12])

        # --- GÜVENLİK MARJI ---
        # Ajan uzaklaştıkça adım başı ceza artacağı için,
        # toplam birikmiş zarar artacaktır. İntiharı önlemek için
        # Terminal cezaları -300'den -500'e çektik (GARANTİ OLSUN).

        # 1. Tavan Kontrolü
        if dy >= 100:
            print(f"TAVANA VURDU (dy={dy:.1f})")
            self.termination_reason = "CeilingHit"
            reward = -500.0 
            done = True
            return reward, done 

        # 2. Saha Dışı Kontrolü
        if abs(dx) >= 60 or abs(dz) >= 60:
            print(f"SINIR DIŞI (dx={dx:.1f}, dz={dz:.1f})")
            self.termination_reason = "OutOfBounds"
            reward = -500.0
            done = True
            return reward, done

        # 3. Yere Çakılma Kontrolü
        if dy <= 1.0 and vy <= -5.0:
            print(f"SERT İNİŞ (Hız={vy:.1f})")
            self.termination_reason = "Crash"
            reward = -500.0 
            done = True
            return reward, done

        # 4. Devrilme Kontrolü
        up_vector_y = 1.0 - 2.0 * (qx*qx + qz*qz)
        if up_vector_y < 0.5:
            print(f"DEVRİLDİ")
            self.termination_reason = "Tilted"
            reward = -500.0
            done = True
            return reward, done
            
        # 5. Spin Kontrolü
        abs_roll = abs(wy)
        if abs_roll > 10.0:
            print("FAZLA DÖNDÜ")
            self.termination_reason = "Spin"
            reward = -500.0
            done = True
            return reward, done

        # --- BAŞARILI İNİŞ ---
        if dy < 0.8 and abs(dx) < 5.0 and abs(dz) < 5.0 and abs(vy) < 4.0:
            reward = 500.0 
            reward += (self.max_steps - self.step_count) * 0.1
            print(">>> BAŞARILI İNİŞ! <<<")
            self.termination_reason = "Success"
            done = True
            return reward, done

        # --- STEP REWARDS (ADIM BAŞI HESAPLAMA) ---
        
        # 1. Sabit Gider (Living Penalty)
        step_penalty = -0.2 
        
        # 2. YENİ: MESAFE KORKUSU (Distance Penalty)
        # Hedefe olan yatay uzaklık
        dist_horizontal = np.sqrt(dx**2 + dz**2)
        
        # Formül: En uzakta (60m) -0.3 ceza yesin. Merkezde (0m) 0 ceza.
        # Bu, ajanı merkeze doğru iten "görünmez bir el" gibi çalışır.
        dist_penalty = (dist_horizontal / 60.0) * 0.3
        
        # 3. Shaping (Pozitif Teşvik)
        # Ajanı doğru yolda olduğu için hafifçe "teselli" ediyoruz.
        shaping_pos = 0.0
        shaping_pos += 0.05 * np.exp(-1.0 * abs(dy) / 20.0) 
        shaping_pos += 0.05 * np.exp(-1.0 * dist_horizontal / 10.0) # Merkeze yaklaştıkça artar
        
        # Stabilite
        shaping_stab = 0.04 * up_vector_y if up_vector_y > 0.5 else 0.0

        # Hız cezası (Yere yakın ve hızlıysa)
        velocity_penalty = 0.0
        if vy < 0 and dy < 15.0: 
            velocity_penalty = abs(vy) * (1.0 / (dy + 1.0)) * 0.05

        # TOPLAM HESAP
        # reward = Sabit Ceza - Mesafe Cezası + Teselli Puanları - Hız/Dönüş Cezaları
        # NOT: Mesafe cezası eklendiği için reward eksiye daha meyillidir.
        # Bu durum ajanı merkeze (cezasız bölgeye) gitmeye zorlar.
        
        current_step_reward = step_penalty - dist_penalty + shaping_pos + shaping_stab - velocity_penalty - (0.01 * abs_roll)
        
        reward += current_step_reward

        # Zaman sınırı
        if self.step_count >= self.max_steps:
            self.termination_reason = "TimeLimit"
            reward += -50.0 
            done = True

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

        # Unity'e gönder (sadece gerekli parametreler: mode, pitch, yaw, thrust)
        # NOT: Unity şu anda roll parametresini beklemiyor, sadece pitch, yaw, thrust
        self.con.sendCs((0, pitch, yaw, thrust))  
        
        # Unity'den gelen yeni durumu oku
        states = self.parse_states(self.con.readCs())
        
        # Ödülü hesapla
        reward_step, done = self.compute_reward_done(states)
        
        # --- KRİTİK EKLEME: REWARD SCALING ---
        # Ödülü 10'a bölüyoruz. (+500 -> +50, -500 -> -50)
        # Bu işlem Value Loss patlamasını önler ve eğitimi stabilize eder.
        reward_step *= 0.1 
        # -------------------------------------

        self.done = bool(done)
        
        # Sıralama senin kodundaki gibi: State, Done, Reward
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

        # Unity sadece 6 parametre bekliyor: mode, x, y, z, pitch, yaw
        print(f"Reset gönderiliyor: mode=1, x={x:.2f}, y={y:.2f}, z={z:.2f}, pitch={pitch:.2f}, yaw={yaw:.2f}")
        self.con.sendCs((1, x, y, z, pitch, yaw))

    def readStates(self):
        states = self.parse_states(self.con.readCs())
        return states.tolist()

    



