import socket
import time
import subprocess
import sys
import threading
import os

def wait_for_signal(port=12345, timeout=30):
    """Esperar señal de sincronización con timeout"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(('', port))
        sock.listen(5)
        sock.settimeout(timeout)
        print(f"Esperando señal en puerto {port} (timeout: {timeout}s)...")
        
        conn, addr = sock.accept()
        print(f"Señal recibida de {addr}")
        conn.close()
        sock.close()
        return True
    except socket.timeout:
        print(f"Timeout: No se recibió señal en {timeout} segundos")
        sock.close()
        return False
    except Exception as e:
        print(f"Error esperando señal: {e}")
        sock.close()
        return False

def send_signal(host, port=12345, timeout=5):
    """Enviar señal de sincronización con timeout"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        print(f"Enviando señal a {host}:{port}...")
        sock.connect((host, port))
        sock.close()
        return True
    except Exception as e:
        print(f"No se pudo conectar a {host}: {e}")
        return False

def run_mpi_simulation():
    """Ejecutar la simulación MPI"""
    if os.name == 'nt':  # Windows
        cmd = ['mpiexec', '-np', '2', 'python', 'fire_simulation_fixed.py']
    else:  # macOS/Linux
        cmd = ['mpirun', '-np', '2', 'python', 'fire_simulation_fixed.py']
    
    print(f"Ejecutando: {' '.join(cmd)}")
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                 universal_newlines=True, bufsize=1)
        
        # Mostrar salida en tiempo real
        for line in iter(process.stdout.readline, ''):
            print(line.rstrip())
        
        process.wait()
        return process.returncode == 0
    except Exception as e:
        print(f"Error ejecutando simulación: {e}")
        return False

def master_mode():
    """Modo coordinador (MASTER)"""
    print("INICIANDO COORDINACIÓN DISTRIBUIDA")
    print("   Modo: COORDINADOR (MASTER)")
    
    # Lista de computadoras worker
    worker_hosts = [
        # '172.20.10.3',  # Windows PC 1
        '172.20.10.4',  # Windows PC 2
        # Agregar más IPs según sea necesario
    ]
    
    # Dar tiempo a que los workers estén listos
    print("Esperando 5 segundos para que los workers estén listos...")
    time.sleep(5)
    
    # Enviar señales a todas las computadoras worker
    connected_workers = 0
    for host in worker_hosts:
        if send_signal(host):
            print(f"Conectado exitosamente a {host}")
            connected_workers += 1
        else:
            print(f"No se pudo conectar a {host} (puede estar offline)")
    
    print(f"Resumen: {connected_workers}/{len(worker_hosts)} workers conectados")
    
    if connected_workers > 0:
        print("Iniciando simulación distribuida...")
        #