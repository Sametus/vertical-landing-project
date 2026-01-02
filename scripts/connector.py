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
        recv_msg = self.sock.recv(1024) # Cevabı bekle
        message = recv_msg.decode("utf-8")
        return message
