from mpi4py import MPI
import numpy as np
import tkinter as tk
from tkinter import ttk
import threading
import time
import random
import socket
import json
import math
import platform
import datetime
import logging

# Configurar logging para cada proceso
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

# Configurar logging individual por proceso
hostname = socket.gethostname()
logging.basicConfig(
    filename=f'mpi_log_rank_{rank}_{hostname}.log',
    level=logging.INFO,
    format='%(asctime)s - Rank %(rank)d - %(hostname)s - %(message)s',
    filemode='w'
)

# Agregar información de rank y hostname al logger
logger = logging.getLogger()
logger = logging.LoggerAdapter(logger, {'rank': rank, 'hostname': hostname})

# --- Configuración Avanzada ---
ROWS, COLS = 60, 80
STEPS = 500
CELL_SIZE = 8

# Probabilidades más realistas
PROB_BASE = 0.15
HUMIDITY_BASE = 0.7  # Humedad base del ambiente
TEMP_BASE = 25       # Temperatura base en °C
WIND_DIRECTION = 'SE'  # Dirección fija del viento
WIND_SPEED = 2.5       # Velocidad fija del viento
ELEVATION_FACTOR = 0.1  # Factor de elevación

# --- Estados Mejorados ---
EMPTY = 0
TREE_YOUNG = 1
TREE_MATURE = 2
TREE_OLD = 3
FIRE_LOW = 4
FIRE_MEDIUM = 5
FIRE_HIGH = 6
BURNED = 7
ASH = 8
WATER = 9

# Configuración de red para múltiples computadoras
def get_detailed_host_info():
    """Obtener información detallada del sistema"""
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except:
        ip = "Unknown"
    
    os_info = f"{platform.system()} {platform.release()}"
    
    try:
        import psutil
        cpu_count = psutil.cpu_count()
        memory = psutil.virtual_memory()
        memory_gb = round(memory.total / (1024**3), 2)
        cpu_percent = psutil.cpu_percent(interval=1)
    except ImportError:
        cpu_count = "N/A"
        memory_gb = "N/A" 
        cpu_percent = "N/A"
    
    return {
        'hostname': hostname,
        'ip': ip,
        'os': os_info,
        'cpu_cores': cpu_count,
        'memory_gb': memory_gb,
        'cpu_usage': cpu_percent,
        'rank': rank,
        'total_processes': size,
        'timestamp': datetime.datetime.now().strftime("%H:%M:%S")
    }

# --- Generación de Terreno Complejo ---
def generate_complex_terrain():
    rows_per_proc = ROWS // size
    
    logger.info(f"Generando terreno: {rows_per_proc}x{COLS} celdas")
    
    # Generar diferentes tipos de vegetación
    terrain = np.random.choice([TREE_YOUNG, TREE_MATURE, TREE_OLD, EMPTY, WATER], 
                              size=(rows_per_proc, COLS),
                              p=[0.3, 0.4, 0.2, 0.08, 0.02])
    
    # Agregar elevación (afecta la propagación del fuego)
    elevation = np.random.random((rows_per_proc, COLS)) * 100
    
    # Humedad variable del terreno
    humidity = np.random.uniform(0.3, 0.9, (rows_per_proc, COLS))
    
    # Temperatura variable
    temperature = np.random.uniform(20, 35, (rows_per_proc, COLS))
    
    logger.info("Terreno generado exitosamente")
    return terrain, elevation, humidity, temperature

# --- Inicialización con múltiples focos ---
def initialize_fires(forest):
    num_fires = random.randint(2, 5)
    fires_created = 0
    
    for _ in range(num_fires):
        i = random.randint(0, forest.shape[0] - 1)
        j = random.randint(0, forest.shape[1] - 1)
        if forest[i, j] in [TREE_YOUNG, TREE_MATURE, TREE_OLD]:
            forest[i, j] = random.choice([FIRE_LOW, FIRE_MEDIUM, FIRE_HIGH])
            fires_created += 1
    
    logger.info(f"Inicializados {fires_created} focos de incendio")
    return forest

# --- Propagación Avanzada del Fuego ---
def spread_fire_complex(forest, elevation, humidity, temperature, step):
    new_forest = forest.copy()
    rows, cols = forest.shape
    
    # Direcciones con diagonal
    directions = [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]
    wind_vectors = {
        'N': (-1, 0), 'NE': (-1, 1), 'E': (0, 1), 'SE': (1, 1),
        'S': (1, 0), 'SW': (1, -1), 'W': (0, -1), 'NW': (-1, -1)
    }
    wind_vector = wind_vectors.get(WIND_DIRECTION, (0, 0))
    
    fires_extinguished = 0
    fires_spread = 0
    
    for i in range(rows):
        for j in range(cols):
            cell = forest[i, j]
            
            # Evolución del fuego
            if cell in [FIRE_LOW, FIRE_MEDIUM, FIRE_HIGH]:
                # El fuego se consume gradualmente
                burn_time = random.random()
                if burn_time < 0.1:  # 10% chance de quemarse completamente
                    new_forest[i, j] = BURNED
                    fires_extinguished += 1
                elif burn_time < 0.05:  # 5% chance de intensificarse
                    new_forest[i, j] = min(cell + 1, FIRE_HIGH)
            
            elif cell == BURNED:
                # Cenizas después de quemar
                if random.random() < 0.05:
                    new_forest[i, j] = ASH
            
            elif cell in [TREE_YOUNG, TREE_MATURE, TREE_OLD]:
                # Calcular probabilidad de ignición
                fire_prob = 0
                
                for dx, dy in directions:
                    ni, nj = i + dx, j + dy
                    if 0 <= ni < rows and 0 <= nj < cols:
                        neighbor = forest[ni, nj]
                        
                        if neighbor in [FIRE_LOW, FIRE_MEDIUM, FIRE_HIGH]:
                            # Probabilidad base según tipo de fuego
                            base_prob = {
                                FIRE_LOW: 0.1,
                                FIRE_MEDIUM: 0.2,
                                FIRE_HIGH: 0.35
                            }[neighbor]
                            
                            # Factor de viento
                            wind_factor = 1.0
                            if (dx, dy) == wind_vector:
                                wind_factor = 1 + (WIND_SPEED * 0.3)
                            elif (-dx, -dy) == wind_vector:
                                wind_factor = 1 - (WIND_SPEED * 0.1)
                            
                            # Factor de elevación (fuego sube más fácil)
                            elev_factor = 1.0
                            if ni < rows and nj < cols:
                                if elevation[i, j] > elevation[ni, nj]:
                                    elev_factor = 1 + ELEVATION_FACTOR
                                else:
                                    elev_factor = 1 - ELEVATION_FACTOR * 0.5
                            
                            # Factor de humedad
                            humid_factor = 1 - humidity[i, j]
                            
                            # Factor de temperatura
                            temp_factor = 1 + (temperature[i, j] - TEMP_BASE) * 0.02
                            
                            # Factor de tipo de árbol
                            tree_factor = {
                                TREE_YOUNG: 0.8,   # Más resistente
                                TREE_MATURE: 1.0,
                                TREE_OLD: 1.3      # Más inflamable
                            }[cell]
                            
                            fire_prob += base_prob * wind_factor * elev_factor * humid_factor * temp_factor * tree_factor
                
                # Ignición
                if random.random() < min(fire_prob, 0.8):
                    # Tipo de fuego según condiciones
                    if temperature[i, j] > 30 and humidity[i, j] < 0.4:
                        new_forest[i, j] = FIRE_HIGH
                    elif temperature[i, j] > 25 and humidity[i, j] < 0.6:
                        new_forest[i, j] = FIRE_MEDIUM
                    else:
                        new_forest[i, j] = FIRE_LOW
                    fires_spread += 1
    
    if fires_extinguished > 0 or fires_spread > 0:
        logger.info(f"Paso {step}: {fires_spread} nuevos fuegos, {fires_extinguished} extinguidos")
    
    return new_forest

# --- Colores Mejorados ---
def get_color_advanced(state):
    colors = {
        EMPTY: "#8B4513",        # Tierra
        TREE_YOUNG: "#90EE90",   # Verde claro
        TREE_MATURE: "#228B22",  # Verde
        TREE_OLD: "#006400",     # Verde oscuro
        FIRE_LOW: "#FF4500",     # Naranja
        FIRE_MEDIUM: "#FF0000",  # Rojo
        FIRE_HIGH: "#8B0000",    # Rojo oscuro
        BURNED: "#2F2F2F",       # Gris oscuro
        ASH: "#696969",          # Gris
        WATER: "#4169E1"         # Azul
    }
    return colors.get(state, "#000000")

# --- GUI Mejorada (Solo Rank 0) ---
if rank == 0:
    print(f"INICIANDO SIMULACIÓN DE INCENDIOS FORESTALES")
    print(f"Coordinador ejecutándose en: {hostname}")
    print(f"Total de procesos: {size}")
    print(f"Esperando información de todos los nodos...")
    
    class AdvancedFireApp:
        def __init__(self, root):
            self.root = root
            self.root.title(f"Simulación de Incendios Forestales - MPI ({size} procesos) - {hostname}")
            self.root.configure(bg="#1a1a1a")
            
            # Recopilar información de todos los procesos
            logger.info("Recopilando información de todos los procesos")
            self.process_info = comm.gather(get_detailed_host_info(), root=0)
            
            # Mostrar información en consola
            print("\n📊 INFORMACIÓN DE PROCESOS DISTRIBUIDOS:")
            print("=" * 60)
            for info in self.process_info:
                print(f"  Proceso {info['rank']}: {info['hostname']} ({info['ip']})")
                print(f"    OS: {info['os']}")
                print(f"    CPU: {info['cpu_cores']} cores | RAM: {info['memory_gb']} GB")
                print(f"    Uso CPU: {info['cpu_usage']}%")
                print("-" * 40)
            
            # Frame principal horizontal
            main_frame = tk.Frame(root, bg="#1a1a1a")
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Panel izquierdo - Leyenda y estadísticas
            left_panel = tk.Frame(main_frame, bg="#2d2d2d", relief=tk.RAISED, bd=2, width=250)
            left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
            left_panel.pack_propagate(False)
            
            # Título principal
            title_label = tk.Label(left_panel, text="SIMULACIÓN MPI", bg="#2d2d2d", fg="#ff6600", 
                                 font=("Arial", 14, "bold"))
            title_label.pack(pady=(10, 5))
            
            # Información del cluster
            cluster_info = tk.Label(left_panel, text=f"Cluster: {size} procesos", 
                                  bg="#2d2d2d", fg="#00ff00", font=("Arial", 11, "bold"))
            cluster_info.pack(pady=2)
            
            # Crear panel de información de procesos
            self.create_process_info_panel(left_panel)
            
            # Separador
            separator = tk.Frame(left_panel, height=2, bg="#555555")
            separator.pack(fill=tk.X, padx=10, pady=10)
            
            # Título de la leyenda
            legend_title = tk.Label(left_panel, text="LEYENDA", bg="#2d2d2d", fg="#ffffff", 
                                  font=("Arial", 12, "bold"))
            legend_title.pack(pady=(5, 10))
            
            # Crear leyenda
            self.create_legend(left_panel)
            
            # Separador
            separator2 = tk.Frame(left_panel, height=2, bg="#555555")
            separator2.pack(fill=tk.X, padx=10, pady=10)
            
            # Estadísticas
            stats_title = tk.Label(left_panel, text="ESTADÍSTICAS", bg="#2d2d2d", fg="#ffffff", 
                                 font=("Arial", 11, "bold"))
            stats_title.pack(pady=(5, 10))
            
            self.stats_frame = tk.Frame(left_panel, bg="#2d2d2d")
            self.stats_frame.pack(fill=tk.X, padx=10)
            
            # Panel derecho - Simulación
            right_panel = tk.Frame(main_frame, bg="#1a1a1a")
            right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
            
            # Canvas principal
            canvas_frame = tk.Frame(right_panel, bg="#1a1a1a", relief=tk.SUNKEN, bd=2)
            canvas_frame.pack(fill=tk.BOTH, expand=True)
            
            self.canvas = tk.Canvas(canvas_frame, width=COLS*CELL_SIZE, height=ROWS*CELL_SIZE, 
                                  bg="#000000", highlightthickness=0)
            self.canvas.pack()
            
            # Crear rectángulos
            self.rects = [[
                self.canvas.create_rectangle(
                    j*CELL_SIZE, i*CELL_SIZE,
                    (j+1)*CELL_SIZE, (i+1)*CELL_SIZE,
                    fill=get_color_advanced(TREE_MATURE), outline="", width=0
                ) for j in range(COLS)] for i in range(ROWS)]
            
            self.running = True
            self.step = 0
            self.stats = {'trees': 0, 'fires': 0, 'burned': 0}
            
            logger.info("GUI inicializada, comenzando simulación")
            threading.Thread(target=self.simulation_loop, daemon=True).start()
        
        def create_process_info_panel(self, parent):
            # Título
            info_title = tk.Label(parent, text="PROCESOS ACTIVOS", bg="#2d2d2d", fg="#ffffff", 
                                 font=("Arial", 11, "bold"))
            info_title.pack(pady=(10, 10))
            
            # Frame scrollable para información de procesos
            canvas = tk.Canvas(parent, bg="#2d2d2d", height=150, highlightthickness=0)
            scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg="#2d2d2d")
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            if self.process_info:
                for i, info in enumerate(self.process_info):
                    # Frame para cada proceso
                    process_frame = tk.Frame(scrollable_frame, bg="#404040", relief=tk.RAISED, bd=1)
                    process_frame.pack(fill=tk.X, pady=1, padx=5)
                    
                    # Información del proceso
                    tk.Label(process_frame, text=f"📍 Proceso {info['rank']}", 
                            bg="#404040", fg="#00ff00", font=("Arial", 9, "bold")).pack(anchor="w", padx=5, pady=1)
                    
                    tk.Label(process_frame, text=f"🖥️  {info['hostname'][:15]}", 
                            bg="#404040", fg="#ffffff", font=("Arial", 8)).pack(anchor="w", padx=10)
                    
                    tk