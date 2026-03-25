import socket
import pyaudio
import struct
import time

# Configurações de áudio
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024                # Tamanho de cada bloco

# Configurações de rede
UDP_IP = "0.0.0.0"          # Escuta em todas as interfaces (usado para bind)
TARGET_IP = input("Digite o IP do celular: ")
UDP_PORT = 5005

# Inicializa PyAudio
p = pyaudio.PyAudio()

# Abre stream de captura
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK)

# Cria socket UDP
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

print("Streaming em tempo real iniciado. Pressione Ctrl+C para parar.")

try:
    while True:
        # Captura um bloco de áudio
        data = stream.read(CHUNK, exception_on_overflow=False)
        # Envia o bloco via UDP
        sock.sendto(data, (TARGET_IP, UDP_PORT))
        # Pequena pausa para não sobrecarregar a rede (ajuste conforme necessário)
        time.sleep(0.001)
except KeyboardInterrupt:
    print("\nEncerrando...")
finally:
    stream.stop_stream()
    stream.close()
    p.terminate()
    sock.close()