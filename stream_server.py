import socket
import time
from pydub import AudioSegment

UDP_PORT = 5005
CHUNK = 1024
RATE = 44100
sleep_time = CHUNK / RATE * 0.99

# Carrega MP3 (ajuste o caminho)
audio = AudioSegment.from_mp3("/media/frank/URUBUTURBO/PESQUISA/applicationSoftware/stream_server/1.mp3")
audio = audio.set_channels(1).set_frame_rate(RATE).set_sample_width(2)
raw_data = audio.raw_data

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('', UDP_PORT))
print("Aguardando HELLO do cliente...")

try:
    data, client_addr = sock.recvfrom(1024)
    if data != b'HELLO':
        print("Mensagem inválida.")
        sock.close()
        exit()
    print(f"Cliente {client_addr} conectado. Enviando START...")
    sock.sendto(b'START', client_addr)

    response, _ = sock.recvfrom(1024)
    if response != b'READY':
        print("Resposta inválida.")
        sock.close()
        exit()
    print("Handshake OK. Iniciando transmissão...")
except socket.timeout:
    print("Timeout aguardando cliente.")
    sock.close()
    exit()

seq = 0
start_time = time.perf_counter()
print("Transmitindo...")
for i in range(0, len(raw_data), CHUNK):
    chunk = raw_data[i:i+CHUNK]
    header = seq.to_bytes(4, 'little')
    sock.sendto(header + chunk, client_addr)

    expected = start_time + (seq + 1) * sleep_time
    now = time.perf_counter()
    if now < expected:
        time.sleep(expected - now)

    if seq % 100 == 0:
        print(f"Enviado pacote {seq}")
    seq += 1

sock.sendto((0xFFFFFFFF).to_bytes(4, 'little') + b'', client_addr)
print(f"Transmissão concluída. {seq} pacotes enviados.")
sock.close()