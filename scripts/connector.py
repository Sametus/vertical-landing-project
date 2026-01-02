import socket
import time

class Connector():
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        print(f"Unity ({self.ip}:{self.port}) aranıyor...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.ip, self.port))
        print("Bağlandı!")

    def sendCs(self, data):
        msg = ",".join(map(str, data)) + "\n"
        self.sock.sendall(msg.encode("utf-8"))

    def readCs(self):
        """
        Unity'den state okur. Unity state newline ile bitmez, bu yüzden 
        state'in tamamını okumak için timeout ve buffer mekanizması kullanır.
        State formatı: dx,dy,dz,vx,vy,vz,wx,wy,wz,qx,qy,qz,qw (13 değer, 12 virgül)
        """
        buffer = b""
        self.sock.settimeout(2.0)  # 2 saniye timeout
        
        max_iterations = 50  # Maksimum okuma döngüsü
        iteration = 0
        
        while iteration < max_iterations:
            try:
                chunk = self.sock.recv(1024)
                if not chunk:
                    raise ConnectionError("Unity bağlantısı kapandı")
                
                buffer += chunk
                message = buffer.decode("utf-8")
                
                # State 13 değer içerir (12 virgül)
                # Eğer 12+ virgül varsa state tamamlanmış demektir
                if message.count(',') >= 12:
                    # Biraz daha bekle, belki daha fazla veri gelir
                    iteration += 1
                    if iteration >= 3:  # 3 iterasyon yeterli
                        break
                else:
                    iteration = 0  # Reset counter if data is incomplete
                    
            except socket.timeout:
                # Timeout oldu, eğer yeterli veri varsa state tamamlanmış olabilir
                if len(buffer) > 0:
                    message = buffer.decode("utf-8", errors='ignore')
                    if message.count(',') >= 12:
                        break
                raise TimeoutError("Unity'den state alınamadı (timeout)")
            except Exception as e:
                raise ConnectionError(f"Unity bağlantı hatası: {e}")
        
        # Timeout'u kaldır (bir sonraki çağrı için)
        self.sock.settimeout(None)
        
        message = buffer.decode("utf-8", errors='ignore').strip()
        if not message:
            raise ValueError("Unity'den boş state alındı")
        
        return message
