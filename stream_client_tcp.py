import socket
import pyaudio
import time
import threading
import sys

TCP_PORT = 5005
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 1

# Configuração dos buffers
BUFFER_DURATION = 0.5
NUM_BUFFERS = 6
MIN_READY_BUFFERS = 2
BUFFER_SIZE = int(RATE * BUFFER_DURATION * CHANNELS * 2)

print(f"Tamanho de cada buffer: {BUFFER_SIZE} bytes ({BUFFER_DURATION*1000:.0f}ms)")
print(f"Pool de {NUM_BUFFERS} buffers | inicia com {MIN_READY_BUFFERS} prontos")

buffers = [bytearray() for _ in range(NUM_BUFFERS)]
buffer_ready = [False] * NUM_BUFFERS
current_fill = 0
next_play = 0

fill_lock = threading.Lock()
play_semaphore = threading.Semaphore(0)
stop_flag = False
receiving_done = False


def mask_ip(ip_str):
    """Mascara um endereço IPv4 mostrando apenas os dois primeiros octetos."""
    partes = ip_str.split('.')
    if len(partes) == 4:
        return f"{partes[0]}.{partes[1]}.***.***"
    return "***.***.***.***"


def input_masked(prompt):
    """
    Lê uma string do terminal, exibindo '*' para cada caractere digitado.
    Funciona em Windows (msvcrt) e Linux/Unix (termios).
    """
    print(prompt, end='', flush=True)
    chars = []

    if sys.platform == 'win32':
        import msvcrt
        while True:
            ch = msvcrt.getch()
            if ch in (b'\r', b'\n'):          # Enter
                print()
                break
            elif ch == b'\x08':                # Backspace
                if chars:
                    chars.pop()
                    print('\b \b', end='', flush=True)
            else:
                try:
                    char = ch.decode('utf-8')
                    chars.append(char)
                    print('*', end='', flush=True)
                except UnicodeDecodeError:
                    continue
        return ''.join(chars)

    else:  # Unix-like
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            while True:
                ch = sys.stdin.read(1)
                if ch in ('\r', '\n'):         # Enter
                    print()
                    break
                elif ch in ('\x7f', '\x08'):   # Backspace/Delete
                    if chars:
                        chars.pop()
                        print('\b \b', end='', flush=True)
                else:
                    chars.append(ch)
                    print('*', end='', flush=True)
            return ''.join(chars)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def receive_data(server_ip):
    global current_fill, stop_flag, receiving_done

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_ip, TCP_PORT))

    peer_ip, peer_port = sock.getpeername()
    ip_mascarado = mask_ip(peer_ip)
    print(f"Conectado ao servidor: {ip_mascarado}:{peer_port}")
    print("Aguardando START...")

    start = sock.recv(1024)
    if start != b'START':
        print("Handshake falhou.")
        sock.close()
        stop_flag = True
        return

    sock.sendall(b'READY')
    print("Handshake OK. Recebendo áudio...")

    while not stop_flag:
        try:
            data = sock.recv(65536)
            if not data:
                break
        except Exception as e:
            print(f"Erro ao receber: {e}")
            break

        with fill_lock:
            buffers[current_fill].extend(data)
            if len(buffers[current_fill]) >= BUFFER_SIZE:
                buffer_ready[current_fill] = True
                play_semaphore.release()
                current_fill = (current_fill + 1) % NUM_BUFFERS
                buffers[current_fill] = bytearray()
                buffer_ready[current_fill] = False

    with fill_lock:
        if len(buffers[current_fill]) > 0:
            buffer_ready[current_fill] = True
            play_semaphore.release()

    receiving_done = True
    sock.close()
    print("Recepção concluída.")


def play_audio():
    global next_play, stop_flag

    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        output=True,
        frames_per_buffer=CHUNK
    )

    try:
        print(f"Aguardando {MIN_READY_BUFFERS} buffers antes de iniciar...")
        for _ in range(MIN_READY_BUFFERS):
            play_semaphore.acquire()

        with fill_lock:
            ready_count = sum(buffer_ready)
        print(f"Iniciando reprodução com {ready_count} buffers prontos.")

        for _ in range(MIN_READY_BUFFERS):
            play_semaphore.release()

        while not stop_flag:
            if not play_semaphore.acquire(timeout=1.0):
                if receiving_done:
                    with fill_lock:
                        if not any(buffer_ready):
                            break
                continue

            with fill_lock:
                if buffer_ready[next_play]:
                    buf = bytes(buffers[next_play])
                    buffer_ready[next_play] = False
                    buffers[next_play] = bytearray()
                    next_play = (next_play + 1) % NUM_BUFFERS
                else:
                    if receiving_done and not any(buffer_ready):
                        break
                    play_semaphore.release()
                    time.sleep(0.01)
                    continue

            for i in range(0, len(buf), CHUNK):
                if stop_flag:
                    break
                stream.write(buf[i:i + CHUNK])

            with fill_lock:
                full = sum(buffer_ready)
            print(f"Buffers prontos restantes: {full}")

    except Exception as e:
        print(f"Erro na reprodução: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        stop_flag = True
        print("Reprodução encerrada.")


if __name__ == "__main__":
    server_ip = input_masked("IP do servidor: ")
    # Se necessário, pode-se validar o IP aqui (ex: split('.') e tentar converter para int)

    receiver = threading.Thread(target=receive_data, args=(server_ip,), daemon=True)
    player = threading.Thread(target=play_audio, daemon=True)

    receiver.start()
    player.start()

    try:
        while not stop_flag:
            time.sleep(0.1)
    except KeyboardInterrupt:
        stop_flag = True
        print("\nInterrompido pelo usuário.")

    print("Encerrado.")