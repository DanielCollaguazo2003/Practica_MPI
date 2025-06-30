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

print(f"[Rank {rank}] Proceso iniciado en {hostname}")

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

# === SINCRONIZACIÓN INICIAL ===
print(f"[Rank {rank}] Sincronizando con otros procesos...")

# Todos los procesos envían su información
my_info = get_detailed_host_info()
print(f"[Rank {rank}] Enviando información: {my_info['hostname']}")

# Recopilar información de todos los procesos
all_process_info = comm.allgather(my_info)

# Sincronización: todos los procesos esperan aquí
comm.Barrier()
print(f"[Rank {rank}] Sincronización completada")

# === INICIALIZACIÓN DE DATOS ===
print(f"[Rank {rank}] Generando datos iniciales...")

# Generar terreno local
local_forest, local_elevation, local_humidity, local_temperature = generate_complex_terrain()
local_forest = initialize_fires(local_forest)

print(f"[Rank {rank}] Datos generados. Tamaño local: {local_forest.shape}")

# === GUI SOLO EN RANK 0 ===
if rank == 0:
    print(f"🔥 SIMULACIÓN DE INCENDIOS FORESTALES - COORDINADOR 🔥")
    print(f"   Ejecutándose en: {hostname}")
    print(f"   Total de procesos: {size}")
    
    # Mostrar información de todos los procesos
    print("\n📊 INFORMACIÓN DE PROCESOS DISTRIBUIDOS:")
    print("=" * 60)
    for info in all_process_info:
        print(f"  Proceso {info['rank']}: {info['hostname']} ({info['ip']})")
        print(f"    OS: {info['os']}")
        print(f"    CPU: {info['cpu_cores']} cores | RAM: {info['memory_gb']} GB")
        print("-" * 40)
    
    class AdvancedFireApp:
        def __init__(self, root):
            self.root = root
            self.root.title(f"Simulación de Incendios Forestales - MPI ({size} procesos) - {hostname}")
            self.root.configure(bg="#1a1a1a")
            
            # Información de procesos
            self.process_info = all_process_info
            
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
            
            # Controles
            control_frame = tk.Frame(right_panel, bg="#1a1a1a")
            control_frame.pack(fill=tk.X, pady=5)
            
            self.step_label = tk.Label(control_frame, text="Paso: 0", bg="#1a1a1a", fg="#ffffff", 
                                     font=("Arial", 12, "bold"))
            self.step_label.pack(side=tk.LEFT, padx=10)
            
            pause_btn = tk.Button(control_frame, text="Pausar", command=self.toggle_pause,
                                bg="#ff6600", fg="white", font=("Arial", 10, "bold"))
            pause_btn.pack(side=tk.RIGHT, padx=5)
            
            reset_btn = tk.Button(control_frame, text="Reiniciar", command=self.reset_simulation,
                                bg="#00aa00", fg="white", font=("Arial", 10, "bold"))
            reset_btn.pack(side=tk.RIGHT, padx=5)
            
            logger.info("GUI inicializada, comenzando simulación")
            threading.Thread(target=self.simulation_loop, daemon=True).start()
        
        def create_process_info_panel(self, parent):
            # Título
            info_title = tk.Label(parent, text="PROCESOS ACTIVOS", bg="#2d2d2d", fg="#ffffff", 
                                 font=("Arial", 11, "bold"))
            info_title.pack(pady=(10, 10))
            
            # Frame para información de procesos
            info_frame = tk.Frame(parent, bg="#2d2d2d")
            info_frame.pack(fill=tk.X, padx=5)
            
            for i, info in enumerate(self.process_info):
                # Frame para cada proceso
                process_frame = tk.Frame(info_frame, bg="#404040", relief=tk.RAISED, bd=1)
                process_frame.pack(fill=tk.X, pady=1)
                
                # Información del proceso
                tk.Label(process_frame, text=f"Proceso {info['rank']}", 
                        bg="#404040", fg="#00ff00", font=("Arial", 9, "bold")).pack(anchor="w", padx=5, pady=1)
                
                tk.Label(process_frame, text=f"{info['hostname'][:15]}", 
                        bg="#404040", fg="#ffffff", font=("Arial", 8)).pack(anchor="w", padx=10)
        
        def create_legend(self, parent):
            legend_items = [
                (TREE_YOUNG, "Árbol Joven"),
                (TREE_MATURE, "Árbol Maduro"),
                (TREE_OLD, "Árbol Viejo"),
                (FIRE_LOW, "Fuego Bajo"),
                (FIRE_MEDIUM, "Fuego Medio"),
                (FIRE_HIGH, "Fuego Alto"),
                (BURNED, "Quemado"),
                (EMPTY, "Tierra"),
                (WATER, "Agua")
            ]
            
            for state, label in legend_items:
                item_frame = tk.Frame(parent, bg="#2d2d2d")
                item_frame.pack(fill=tk.X, padx=10, pady=1)
                
                color_box = tk.Label(item_frame, text="  ", bg=get_color_advanced(state), 
                                   width=3, relief=tk.RAISED, bd=1)
                color_box.pack(side=tk.LEFT, padx=(0, 5))
                
                label_text = tk.Label(item_frame, text=label, bg="#2d2d2d", fg="#ffffff", 
                                    font=("Arial", 9), anchor="w")
                label_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def update_stats(self, forest_data):
            """Actualizar estadísticas"""
            # Limpiar frame de estadísticas
            for widget in self.stats_frame.winfo_children():
                widget.destroy()
            
            # Contar estados
            unique, counts = np.unique(forest_data, return_counts=True)
            state_counts = dict(zip(unique, counts))
            
            trees = sum(state_counts.get(state, 0) for state in [TREE_YOUNG, TREE_MATURE, TREE_OLD])
            fires = sum(state_counts.get(state, 0) for state in [FIRE_LOW, FIRE_MEDIUM, FIRE_HIGH])
            burned = state_counts.get(BURNED, 0)
            total_cells = forest_data.size
            
            stats = [
                ("Árboles", trees, "#00ff00"),
                ("Fuegos", fires, "#ff0000"),
                ("Quemados", burned, "#666666"),
                ("Total", total_cells, "#ffffff")
            ]
            
            for label, value, color in stats:
                stat_frame = tk.Frame(self.stats_frame, bg="#2d2d2d")
                stat_frame.pack(fill=tk.X, pady=2)
                
                tk.Label(stat_frame, text=label, bg="#2d2d2d", fg=color, 
                        font=("Arial", 9, "bold")).pack(side=tk.LEFT)
                
                tk.Label(stat_frame, text=str(value), bg="#2d2d2d", fg="#ffffff", 
                        font=("Arial", 9)).pack(side=tk.RIGHT)
        
        def toggle_pause(self):
            self.running = not self.running
        
        def reset_simulation(self):
            self.step = 0
            # Aquí podrías reinicializar los datos si fuera necesario
        
        def simulation_loop(self):
            """Bucle principal de simulación"""
            global local_forest, local_elevation, local_humidity, local_temperature
            
            while self.step < STEPS:
                if not self.running:
                    time.sleep(0.1)
                    continue
                
                try:
                    # Notificar a todos los procesos que continúen
                    comm.bcast(True, root=0)
                    
                    # Recopilar datos de todos los procesos
                    all_forests = comm.gather(local_forest, root=0)
                    
                    if all_forests:
                        # Combinar datos de todos los procesos
                        full_forest = np.vstack(all_forests)
                        
                        # Actualizar visualización
                        self.update_visualization(full_forest)
                        self.update_stats(full_forest)
                        
                        # Actualizar contador de pasos
                        self.step_label.config(text=f"Paso: {self.step}")
                        
                        self.step += 1
                    
                    time.sleep(0.1)  # Controlar velocidad de simulación
                    
                except Exception as e:
                    logger.error(f"Error en simulación: {e}")
                    break
            
            # Notificar fin de simulación
            comm.bcast(False, root=0)
            print("Simulación completada")
        
        def update_visualization(self, forest_data):
            """Actualizar la visualización del canvas"""
            for i in range(min(ROWS, forest_data.shape[0])):
                for j in range(min(COLS, forest_data.shape[1])):
                    color = get_color_advanced(forest_data[i, j])
                    self.canvas.itemconfig(self.rects[i][j], fill=color)
            
            # Actualizar canvas
            self.root.update_idletasks()
    
    # Crear y ejecutar GUI
    root = tk.Tk()
    app = AdvancedFireApp(root)
    
    print(f"[Rank {rank}] Iniciando GUI...")
    root.mainloop()

else:
    # === PROCESOS WORKER ===
    print(f"[Rank {rank}] Iniciando como proceso worker...")
    
    while True:
        # Esperar señal del coordinador
        try:
            continue_sim = comm.bcast(None, root=0)
            
            if not continue_sim:
                print(f"[Rank {rank}] Recibida señal de fin de simulación")
                break
            
            # Evolucionar el bosque local
            local_forest = spread_fire_complex(local_forest, local_elevation, 
                                             local_humidity, local_temperature, 0)
            
            # Enviar datos al coordinador
            comm.gather(local_forest, root=0)
            
        except Exception as e:
            logger.error(f"Error en worker: {e}")
            break

print(f"[Rank {rank}] Proceso terminado")