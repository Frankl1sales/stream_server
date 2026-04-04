# mic_stream_server_tcp.py
import socket
import pyaudio
import time
import threading

TCP_PORT = 5005
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16 bits

# Taxa de bytes por segundo
BYTES_PER_SEC = RATE * CHANNELS * SAMPLE_WIDTH  # 88200 bytes/s

# Configuração do buffer de envio (para suavizar)
SEND_BUFFER_SECONDS = 0.5
SEND_CHUNK_SIZE = int(RATE * SEND_BUFFER_SECONDS * CHANNELS * SAMPLE_WIDTH)  # 44100 bytes

def list_microphones():
    """Lista dispositivos de entrada disponíveis."""
    p = pyaudio.PyAudio()
    print("Dispositivos de entrada disponíveis:")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            print(f"  Índice {i}: {info['name']} (canais: {info['maxInputChannels']})")
    p.terminate()

def get_microphone_index():
    """Permite o usuário escolher o microfone (opcional)."""
    list_microphones()
    try:
        idx = int(input("Digite o índice do microfone desejado (ou Enter para padrão): ") or -1)
        return idx if idx >= 0 else None
    except ValueError:
        return None

def mic_stream_server():
    # Escolher microfone
    mic_index = get_microphone_index()
    
    # Inicializa PyAudio para captura
    p = pyaudio.PyAudio()
    stream_in = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=mic_index,
        frames_per_buffer=CHUNK
    )
    
    # Cria socket TCP
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('', TCP_PORT))
    server_socket.listen(1)
    print(f"Aguardando conexão TCP na porta {TCP_PORT}...")
    
    conn, addr = server_socket.accept()
    ip, port = addr
    # Oculta IP parcialmente
    partes = ip.split('.')
    if len(partes) == 4:
        ip_mascarado = f"{partes[0]}.{partes[1]}.***.***"
    else:
        ip_mascarado = "***.***.***.***"
    print(f"Cliente conectado: {ip_mascarado}:{port}")
    
    # Handshake
    conn.sendall(b'START')
    response = conn.recv(1024)
    if response != b'READY':
        print("Handshake falhou.")
        conn.close()
        server_socket.close()
        return
    
    print("Handshake OK. Iniciando captura e transmissão do microfone...")
    print("Pressione Ctrl+C para parar.")
    
    total_sent = 0
    start_time = time.time()
    
    try:
        while True:
            # Lê um buffer de áudio do microfone
            data = stream_in.read(SEND_CHUNK_SIZE, exception_on_overflow=False)
            if not data:
                break
            
            # Envia via TCP
            conn.sendall(data)
            total_sent += len(data)
            
            # Controle de tempo real (throttling)
            expected_time = total_sent / BYTES_PER_SEC
            elapsed = time.time() - start_time
            sleep_time = expected_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            # Status a cada ~5 segundos
            if int(elapsed) % 5 == 0 and elapsed > 0:
                print(f"Enviado: {total_sent / 1024:.0f} KB | tempo real: {elapsed:.1f}s / esperado: {expected_time:.1f}s")
    
    except KeyboardInterrupt:
        print("\nTransmissão interrompida pelo usuário.")
    except Exception as e:
        print(f"Erro: {e}")
    finally:
        stream_in.stop_stream()
        stream_in.close()
        p.terminate()
        conn.close()
        server_socket.close()
        print("Servidor encerrado.")

if __name__ == "__main__":
    mic_stream_server()