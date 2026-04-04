import socket
import time
from pydub import AudioSegment

TCP_PORT = 5005
CHUNK = 1024
RATE = 44100
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16bit

# Taxa real de áudio em bytes/segundo
BYTES_PER_SEC = RATE * CHANNELS * SAMPLE_WIDTH  # 88200 bytes/s

# Carrega e converte MP3 para PCM
audio = AudioSegment.from_mp3("/media/frank/URUBUTURBO/PESQUISA/applicationSoftware/stream_server/1.mp3")
audio = audio.set_channels(CHANNELS).set_frame_rate(RATE).set_sample_width(SAMPLE_WIDTH)
raw_data = audio.raw_data

print(f"Áudio carregado: {len(raw_data)} bytes / {len(raw_data)/BYTES_PER_SEC:.1f} segundos")

# Cria socket TCP
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind(('', TCP_PORT))
server_socket.listen(1)
print("Aguardando conexão...")

conn, addr = server_socket.accept()

# --- Ajuste: oculta o IP do cliente ---
ip, port = addr
partes = ip.split('.')
if len(partes) == 4:  # IPv4
    ip_mascarado = f"{partes[0]}.{partes[1]}.***.***"
else:
    ip_mascarado = "***.***.***.***"  # fallback para IPv6 ou formato inesperado
print(f"Cliente conectado: {ip_mascarado}:{port}")

# Handshake: envia START, aguarda READY
conn.sendall(b'START')
response = conn.recv(1024)
if response != b'READY':
    print("Handshake falhou.")
    conn.close()
    server_socket.close()
    exit()

print("Handshake OK. Transmitindo áudio...")

total_sent = 0
start_time = time.time()

for i in range(0, len(raw_data), CHUNK):
    chunk = raw_data[i:i + CHUNK]
    conn.sendall(chunk)
    total_sent += len(chunk)

    # Throttling: calcula o tempo esperado para este ponto do stream
    # e dorme se estiver adiantado em relação ao tempo real
    expected_time = total_sent / BYTES_PER_SEC
    elapsed = time.time() - start_time
    sleep_time = expected_time - elapsed
    if sleep_time > 0:
        time.sleep(sleep_time)

    if (i // CHUNK) % 500 == 0:
        print(f"Enviado {i // CHUNK} blocos | {total_sent / 1024:.0f} KB | "
              f"tempo real: {elapsed:.1f}s / esperado: {expected_time:.1f}s")

conn.close()
server_socket.close()
print(f"Transmissão concluída. Total enviado: {total_sent} bytes.")