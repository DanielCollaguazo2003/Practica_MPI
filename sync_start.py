import socket
import time
import subprocess
import sys

def wait_for_signal(port=12345):
    """Esperar señal de sincronización"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('', port))
    sock.listen(5)
    print(f"Esperando señal en puerto {port}...")
    conn, addr = sock.accept()
    print(f"Señal recibida de {addr}")
    sock.close()
    return True

def send_signal(host, port=12345):
    """Enviar señal de sincronización"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((host, port))
        sock.close()
        return True
    except:
        return False

# Para computadora MASTER (macOS)
if len(sys.argv) > 1 and sys.argv[1] == "master":
    print("🔥 INICIANDO COORDINACIÓN DISTRIBUIDA")
    time.sleep(3)  # Dar tiempo a que otros estén listos
    
    # Enviar señal a todas las computadoras
    hosts = ['172.20.10.3', '172.20.10.4']  # IPs de Windows
    for host in hosts:
        if send_signal(host):
            print(f"✅ Señal enviada a {host}")
        else:
            print(f"❌ No se pudo conectar a {host}")
    
    # Ejecutar simulación
    subprocess.run(['mpirun', '-np', '2', 'python3', 'fire_simulation.py'])

# Para computadoras WORKER (Windows)
else:
    wait_for_signal()
    subprocess.run(['mpirun', '-np', '2', 'python', 'fire_simulation.py'])