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
    
    print(f"🚀 Ejecutando: {' '.join(cmd)}")
    
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
        
        # Esperar un poco más para asegurar sincronización
        time.sleep(2)
        
        # Ejecutar simulación MPI
        success = run_mpi_simulation()
        
        if success:
            print("Simulación completada exitosamente")
        else:
            print("Error durante la simulación")
    else:
        print("No hay workers disponibles. Ejecutando en modo local...")
        run_mpi_simulation()

def worker_mode():
    """Modo trabajador (WORKER)"""
    print("INICIANDO MODO WORKER")
    print("   Esperando señal del coordinador...")
    
    # Esperar señal del coordinador
    if wait_for_signal():
        print("Señal recibida. Iniciando simulación...")
        
        # Pequeña pausa para sincronización
        time.sleep(1)
        
        # Ejecutar simulación MPI
        success = run_mpi_simulation()
        
        if success:
            print("Simulación worker completada")
        else:
            print("Error en simulación worker")
    else:
        print("No se recibió señal del coordinador")

def interactive_mode():
    """Modo interactivo para seleccionar rol"""
    print("SIMULACIÓN DE INCENDIOS FORESTALES - MPI")
    print("=" * 50)
    print("Seleccione el modo de operación:")
    print("1. MASTER (Coordinador) - Envía señales y ejecuta GUI")
    print("2. WORKER (Trabajador) - Espera señales y procesa datos")
    print("3. LOCAL (Solo local) - Ejecuta simulación en esta máquina")
    print("4. AUTO (Automático) - Detecta configuración automáticamente")
    
    while True:
        try:
            choice = input("\nIngrese su opción (1-4): ").strip()
            
            if choice == '1':
                return 'master'
            elif choice == '2':
                return 'worker'
            elif choice == '3':
                return 'local'
            elif choice == '4':
                return 'auto'
            else:
                print("❌ Opción inválida. Por favor ingrese 1, 2, 3 o 4.")
        except KeyboardInterrupt:
            print("\n👋 Operación cancelada por el usuario")
            sys.exit(0)

def auto_detect_mode():
    """Detectar automáticamente el modo basado en la red"""
    import socket
    
    # Intentar determinar si somos coordinador o worker
    hostname = socket.gethostname().lower()
    
    # Lista de hostnames que típicamente actúan como coordinadores
    master_indicators = ['master', 'coord', 'main', 'server', 'mac']
    
    # Si el hostname contiene indicadores de master o es macOS
    if any(indicator in hostname for indicator in master_indicators):
        print(f"Auto-detectado como MASTER (hostname: {hostname})")
        return 'master'
    else:
        print(f"Auto-detectado como WORKER (hostname: {hostname})")
        return 'worker'

def local_mode():
    """Modo local - solo ejecutar en esta máquina"""
    print("MODO LOCAL - Ejecutando simulación en esta máquina únicamente")
    
    success = run_mpi_simulation()
    
    if success:
        print("Simulación local completada")
    else:
        print("Error en simulación local")

def main():
    """Función principal"""
    print("SINCRONIZADOR DE SIMULACIÓN MPI")
    print(f"   Sistema: {os.name}")
    print(f"   Hostname: {socket.gethostname()}")
    print()
    
    # Determinar modo de operación
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    else:
        mode = interactive_mode()
    
    # Ejecutar según el modo seleccionado
    try:
        if mode == 'master':
            master_mode()
        elif mode == 'worker':
            worker_mode()
        elif mode == 'local':
            local_mode()
        elif mode == 'auto':
            auto_mode = auto_detect_mode()
            if auto_mode == 'master':
                master_mode()
            else:
                worker_mode()
        else:
            print(f"Modo desconocido: {mode}")
            print("Modos válidos: master, worker, local, auto")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹Simulación interrumpida por el usuario")
    except Exception as e:
        print(f"Error inesperado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()