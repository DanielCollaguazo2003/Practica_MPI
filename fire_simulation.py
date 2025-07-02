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

# Nuevos estados para fuegos de diferentes procesos (10-99 reservados para fuegos por rank)
FIRE_BASE = 10  # Base para fuegos por proceso

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

# --- Funciones para regiones ---
def get_region_bounds(rank, size, total_rows, total_cols):
    """Calcular los límites de la región para cada proceso"""
    if size == 1:
        return 0, total_rows, 0, total_cols
    
    # Dividir el bosque en regiones rectangulares
    if size <= 4:
        # Para pocos procesos, dividir en franjas horizontales
        rows_per_proc = total_rows // size
        row_start = rank * rows_per_proc
        row_end = (rank + 1) * rows_per_proc if rank < size - 1 else total_rows
        return row_start, row_end, 0, total_cols
    else:
        # Para más procesos, dividir en cuadrícula
        grid_rows = int(np.sqrt(size))
        grid_cols = size // grid_rows
        if grid_rows * grid_cols < size:
            grid_cols += 1
        
        proc_row = rank // grid_cols
        proc_col = rank % grid_cols
        
        rows_per_grid = total_rows // grid_rows
        cols_per_grid = total_cols // grid_cols
        
        row_start = proc_row * rows_per_grid
        row_end = min((proc_row + 1) * rows_per_grid, total_rows)
        col_start = proc_col * cols_per_grid
        col_end = min((proc_col + 1) * cols_per_grid, total_cols)
        
        return row_start, row_end, col_start, col_end

# --- Generación de Terreno Complejo ---
def generate_region_terrain(row_start, row_end, col_start, col_end):
    """Generar terreno para una región específica"""
    rows = row_end - row_start
    cols = col_end - col_start
    
    logger.info(f"Generando terreno región: {rows}x{cols} celdas")
    
    # Generar diferentes tipos de vegetación
    terrain = np.random.choice([TREE_YOUNG, TREE_MATURE, TREE_OLD, EMPTY, WATER], 
                              size=(rows, cols),
                              p=[0.3, 0.4, 0.2, 0.08, 0.02])
    
    # Agregar elevación (afecta la propagación del fuego)
    elevation = np.random.random((rows, cols)) * 100
    
    # Humedad variable del terreno
    humidity = np.random.uniform(0.3, 0.9, (rows, cols))
    
    # Temperatura variable
    temperature = np.random.uniform(20, 35, (rows, cols))
    
    logger.info("Terreno de región generado exitosamente")
    return terrain, elevation, humidity, temperature

# --- Inicialización con fuegos por proceso ---
def initialize_process_fires(forest, process_rank):
    """Inicializar fuegos específicos para cada proceso"""
    num_fires = random.randint(2, 5)  # Aumentar número de fuegos iniciales
    fires_created = 0
    fire_state = FIRE_BASE + process_rank  # Fuego único por proceso
    
    for _ in range(num_fires):
        i = random.randint(0, forest.shape[0] - 1)
        j = random.randint(0, forest.shape[1] - 1)
        if forest[i, j] in [TREE_YOUNG, TREE_MATURE, TREE_OLD]:
            forest[i, j] = fire_state
            fires_created += 1
    
    logger.info(f"Inicializados {fires_created} focos de incendio para proceso {process_rank}")
    return forest

# --- Propagación del Fuego por Proceso ---
def spread_process_fire(forest, elevation, humidity, temperature, process_rank, step):
    """Propagación de fuego específica por proceso"""
    new_forest = forest.copy()
    rows, cols = forest.shape
    
    # Direcciones con diagonal
    directions = [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]
    wind_vectors = {
        'N': (-1, 0), 'NE': (-1, 1), 'E': (0, 1), 'SE': (1, 1),
        'S': (1, 0), 'SW': (1, -1), 'W': (0, -1), 'NW': (-1, -1)
    }
    wind_vector = wind_vectors.get(WIND_DIRECTION, (0, 0))
    
    my_fire_state = FIRE_BASE + process_rank
    fires_extinguished = 0
    fires_spread = 0
    
    for i in range(rows):
        for j in range(cols):
            cell = forest[i, j]
            
            # Solo procesar el fuego de este proceso
            if cell == my_fire_state:
                # El fuego se consume gradualmente
                burn_time = random.random()
                if burn_time < 0.05:  # Reducir probabilidad de extinción para ver más fuego
                    new_forest[i, j] = BURNED
                    fires_extinguished += 1
            
            elif cell == BURNED:
                # Cenizas después de quemar
                if random.random() < 0.02:
                    new_forest[i, j] = ASH
            
            elif cell in [TREE_YOUNG, TREE_MATURE, TREE_OLD]:
                # Solo puede ser prendido por el fuego de este proceso
                fire_prob = 0
                
                for dx, dy in directions:
                    ni, nj = i + dx, j + dy
                    if 0 <= ni < rows and 0 <= nj < cols:
                        neighbor = forest[ni, nj]
                        
                        # Solo responder al fuego de este proceso
                        if neighbor == my_fire_state:
                            base_prob = 0.35  # Aumentar probabilidad base
                            
                            # Factor de viento
                            wind_factor = 1.0
                            if (dx, dy) == wind_vector:
                                wind_factor = 1 + (WIND_SPEED * 0.3)
                            elif (-dx, -dy) == wind_vector:
                                wind_factor = 1 - (WIND_SPEED * 0.1)
                            
                            # Factor de elevación
                            elev_factor = 1.0
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
                                TREE_YOUNG: 0.8,
                                TREE_MATURE: 1.0,
                                TREE_OLD: 1.3
                            }[cell]
                            
                            fire_prob += base_prob * wind_factor * elev_factor * humid_factor * temp_factor * tree_factor
                
                # Ignición con el fuego específico de este proceso
                if random.random() < min(fire_prob, 0.7):  # Aumentar probabilidad máxima
                    new_forest[i, j] = my_fire_state
                    fires_spread += 1
    
    if fires_extinguished > 0 or fires_spread > 0:
        logger.info(f"Proceso {process_rank}, Paso {step}: {fires_spread} nuevos fuegos, {fires_extinguished} extinguidos")
    
    return new_forest

# --- Colores por Proceso ---
def get_color_for_process(process_rank):
    """Obtener color único para cada proceso"""
    colors = [
        "#FF0000",  # Rojo - Proceso 0
        "#00FF00",  # Verde - Proceso 1
        "#0000FF",  # Azul - Proceso 2
        "#FFFF00",  # Amarillo - Proceso 3
        "#FF00FF",  # Magenta - Proceso 4
        "#00FFFF",  # Cian - Proceso 5
        "#FFA500",  # Naranja - Proceso 6
        "#800080",  # Púrpura - Proceso 7
        "#FFC0CB",  # Rosa - Proceso 8
        "#A52A2A",  # Marrón - Proceso 9
    ]
    return colors[process_rank % len(colors)]

def get_color_advanced(state, process_info=None):
    """Colores mejorados con soporte para fuegos por proceso"""
    if state >= FIRE_BASE:
        process_rank = state - FIRE_BASE
        return get_color_for_process(process_rank)
    
    colors = {
        EMPTY: "#8B4513",        # Tierra
        TREE_YOUNG: "#90EE90",   # Verde claro
        TREE_MATURE: "#228B22",  # Verde
        TREE_OLD: "#006400",     # Verde oscuro
        FIRE_LOW: "#FF4500",     # Naranja (fuego genérico)
        FIRE_MEDIUM: "#FF0000",  # Rojo (fuego genérico)
        FIRE_HIGH: "#8B0000",    # Rojo oscuro (fuego genérico)
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

# Calcular región para este proceso
row_start, row_end, col_start, col_end = get_region_bounds(rank, size, ROWS, COLS)
print(f"[Rank {rank}] Región asignada: filas {row_start}-{row_end}, columnas {col_start}-{col_end}")

# Sincronización: todos los procesos esperan aquí
comm.Barrier()  # Esperar a todos los procesos
print(f"[Rank {rank}] Todos los procesos están sincronizados.")

# === INICIALIZACIÓN DE DATOS ===
print(f"[Rank {rank}] Generando datos iniciales...")

# Generar terreno de la región
local_forest, local_elevation, local_humidity, local_temperature = generate_region_terrain(
    row_start, row_end, col_start, col_end)
local_forest = initialize_process_fires(local_forest, rank)

print(f"[Rank {rank}] Datos generados. Tamaño local: {local_forest.shape}")

# === GUI SOLO EN RANK 0 ===
if rank == 0:
    print(f"SIMULACIÓN DE INCENDIOS FORESTALES - COORDINADOR")
    print(f"   Ejecutándose en: {hostname}")
    print(f"   Total de procesos: {size}")
    
    # Mostrar información de los workers conectados (rank != 0)
    print("\nINFORMACIÓN DE PROCESOS REMOTOS CONECTADOS:")
    print("=" * 60)
    for info in all_process_info:
        if info['rank'] != 0:  # Mostrar solo los workers (rank != 0)
            print(f"  Worker {info['rank']}: {info['hostname']} ({info['ip']})")
            print(f"    OS: {info['os']}")
            print(f"    CPU: {info['cpu_cores']} cores | RAM: {info['memory_gb']} GB")
            print("-" * 40)
    
    class MasterFireApp:
        def __init__(self, root):
            self.root = root
            self.root.title(f"Simulación de Incendios Forestales - MASTER ({size} procesos) - {hostname}")
            self.root.configure(bg="#1a1a1a")
            
            # Información de procesos
            self.process_info = all_process_info
            
            # Frame principal horizontal
            main_frame = tk.Frame(root, bg="#1a1a1a")
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Panel izquierdo - Información de procesos y leyenda
            left_panel = tk.Frame(main_frame, bg="#2d2d2d", relief=tk.RAISED, bd=2, width=280)
            left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
            left_panel.pack_propagate(False)
            
            # Título principal
            title_label = tk.Label(left_panel, text="SIMULACIÓN MPI MASTER", bg="#2d2d2d", fg="#ff6600", 
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
            
            # Panel derecho - Simulación completa
            right_panel = tk.Frame(main_frame, bg="#1a1a1a")
            right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
            
            # Canvas principal - Vista completa del bosque
            canvas_frame = tk.Frame(right_panel, bg="#1a1a1a", relief=tk.SUNKEN, bd=2)
            canvas_frame.pack(fill=tk.BOTH, expand=True)
            
            canvas_title = tk.Label(canvas_frame, text="VISTA COMPLETA DEL BOSQUE", 
                                  bg="#1a1a1a", fg="#ffffff", font=("Arial", 12, "bold"))
            canvas_title.pack(pady=5)
            
            self.canvas = tk.Canvas(canvas_frame, width=COLS*CELL_SIZE, height=ROWS*CELL_SIZE, 
                                  bg="#000000", highlightthickness=0)
            self.canvas.pack()
            
            # Inicializar bosque completo con árboles
            self.full_forest = np.full((ROWS, COLS), TREE_MATURE, dtype=int)
            
            # Crear rectángulos para todo el bosque
            self.rects = [[
                self.canvas.create_rectangle(
                    j*CELL_SIZE, i*CELL_SIZE,
                    (j+1)*CELL_SIZE, (i+1)*CELL_SIZE,
                    fill=get_color_advanced(TREE_MATURE), outline="", width=0
                ) for j in range(COLS)] for i in range(ROWS)]
            
            self.running = True
            self.step = 0
            
            # Controles
            control_frame = tk.Frame(right_panel, bg="#1a1a1a")
            control_frame.pack(fill=tk.X, pady=5)
            
            self.step_label = tk.Label(control_frame, text="Paso: 0", bg="#1a1a1a", fg="#ffffff", 
                                     font=("Arial", 12, "bold"))
            self.step_label.pack(side=tk.LEFT, padx=10)
            
            # Estadísticas de fuego
            self.stats_label = tk.Label(control_frame, text="Fuegos: 0 | Quemados: 0", 
                                      bg="#1a1a1a", fg="#ffff00", font=("Arial", 10))
            self.stats_label.pack(side=tk.LEFT, padx=20)
            
            pause_btn = tk.Button(control_frame, text="⏸Pausar", command=self.toggle_pause,
                                bg="#ff6600", fg="white", font=("Arial", 10, "bold"))
            pause_btn.pack(side=tk.RIGHT, padx=5)
            
            logger.info("GUI Master inicializada, comenzando simulación")
            threading.Thread(target=self.simulation_loop, daemon=True).start()
        
        def create_process_info_panel(self, parent):
            # Título
            info_title = tk.Label(parent, text="PROCESOS Y COLORES", bg="#2d2d2d", fg="#ffffff", 
                                 font=("Arial", 11, "bold"))
            info_title.pack(pady=(10, 10))
            
            # Frame para información de procesos
            info_frame = tk.Frame(parent, bg="#2d2d2d")
            info_frame.pack(fill=tk.X, padx=5)
            
            for i, info in enumerate(self.process_info):
                process_color = get_color_for_process(info['rank'])
                
                # Frame para cada proceso
                process_frame = tk.Frame(info_frame, bg="#404040", relief=tk.RAISED, bd=1)
                process_frame.pack(fill=tk.X, pady=2)
                
                # Color del proceso
                color_frame = tk.Frame(process_frame, bg="#404040")
                color_frame.pack(fill=tk.X, padx=5, pady=2)
                
                color_box = tk.Label(color_frame, text="  ", bg=process_color, 
                                   width=3, relief=tk.RAISED, bd=1)
                color_box.pack(side=tk.LEFT, padx=(0, 5))
                
                tk.Label(color_frame, text=f"Proceso {info['rank']}", 
                        bg="#404040", fg="#ffffff", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
                
                tk.Label(process_frame, text=f" {info['hostname'][:12]}", 
                        bg="#404040", fg="#cccccc", font=("Arial", 8)).pack(anchor="w", padx=10)
        
        def create_legend(self, parent):
            legend_items = [
                (TREE_YOUNG, "Árbol Joven"),
                (TREE_MATURE, "Árbol Maduro"),
                (TREE_OLD, "Árbol Viejo"),
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
        
        def toggle_pause(self):
            self.running = not self.running
        
        def simulation_loop(self):
            """Bucle principal de simulación del master"""
            global local_forest
            
            while self.step < STEPS:
                if not self.running:
                    time.sleep(0.1)
                    continue
                
                try:
                    # Notificar a todos los procesos que continúen
                    comm.bcast(True, root=0)
                    
                    # EL MASTER TAMBIÉN DEBE PROCESAR SU PROPIA REGIÓN
                    local_forest = spread_process_fire(local_forest, local_elevation, 
                                                    local_humidity, local_temperature, rank, self.step)
                    
                    # Recopilar datos de todas las regiones
                    all_regions = comm.gather({
                        'forest': local_forest,
                        'bounds': (row_start, row_end, col_start, col_end)
                    }, root=0)
                    
                    if all_regions:
                        # Actualizar bosque completo con datos de todas las regiones
                        for region_data in all_regions:
                            region_forest = region_data['forest']
                            r_start, r_end, c_start, c_end = region_data['bounds']
                            
                            self.full_forest[r_start:r_end, c_start:c_end] = region_forest
                        
                        # Actualizar visualización
                        self.update_visualization(self.full_forest)
                        
                        # Actualizar contador de pasos
                        self.step_label.config(text=f"Paso: {self.step}")
                        
                        self.step += 1
                    
                    time.sleep(0.1)  # Controlar velocidad de simulación
                    
                except Exception as e:
                    logger.error(f"Error en simulación master: {e}")
                    print(f"[Rank {rank}] Error en simulación: {e}")
                    break
            
            # Notificar fin de simulación
            try:
                comm.bcast(False, root=0)
            except:
                pass
            print("Simulación Master completada")
        
        def update_visualization(self, forest_data):
            """Actualizar la visualización del canvas completo"""
            fire_count = 0
            burned_count = 0
            
            for i in range(min(ROWS, forest_data.shape[0])):
                for j in range(min(COLS, forest_data.shape[1])):
                    cell_state = forest_data[i, j]
                    color = get_color_advanced(cell_state)
                    self.canvas.itemconfig(self.rects[i][j], fill=color)
                    
                    # Contar estadísticas
                    if cell_state >= FIRE_BASE:
                        fire_count += 1
                    elif cell_state == BURNED:
                        burned_count += 1
            
            # Actualizar estadísticas
            self.stats_label.config(text=f"Fuegos: {fire_count} | Quemados: {burned_count}")
            
            # Actualizar canvas
            self.root.update_idletasks()
    
    # Crear y ejecutar GUI Master
    root = tk.Tk()
    app = MasterFireApp(root)
    
    print(f"[Rank {rank}] Iniciando GUI Master...")
    root.mainloop()

else:
    # === PROCESOS WORKER ===
    print(f"[Rank {rank}] Iniciando como proceso worker...")
    
    def simulation_worker_loop():
        """Bucle de simulación para worker - SIN GUI"""
        global local_forest, local_elevation, local_humidity, local_temperature
        step = 0
        
        print(f"[Rank {rank}] Worker iniciando bucle de simulación...")
        
        while True:
            try:
                # Esperar señal del coordinador
                continue_simulation = comm.bcast(None, root=0)
                if not continue_simulation:
                    print(f"[Rank {rank}] Recibida señal de fin de simulación")
                    break
                
                # Evolucionar el bosque local
                local_forest = spread_process_fire(local_forest, local_elevation,
                                                   local_humidity, local_temperature, rank, step)
                
                # Contar fuegos activos para debug
                my_fire_state = FIRE_BASE + rank
                fire_count = np.sum(local_forest == my_fire_state)
                if step % 10 == 0:  # Log cada 10 pasos
                    print(f"[Rank {rank}] Paso {step}: {fire_count} fuegos activos")
                
                # Enviar datos al coordinador
                comm.gather({
                    'forest': local_forest,
                    'bounds': (row_start, row_end, col_start, col_end)
                }, root=0)
                
                step += 1
                
            except Exception as e:
                logger.error(f"Error en worker {rank}: {e}")
                print(f"[Rank {rank}] Error en worker: {e}")
                break
        
        print(f"[Rank {rank}] Worker terminado")
    
    # Verificar fuegos iniciales
    print(f"[Rank {rank}] Verificando fuegos iniciales...")
    my_fire_state = FIRE_BASE + rank
    initial_fires = np.sum(local_forest == my_fire_state)
    print(f"[Rank {rank}] Fuegos iniciales: {initial_fires}")

    # Si no hay fuegos iniciales, crear algunos
    if initial_fires == 0:
        print(f"[Rank {rank}] Creando fuegos iniciales...")
        local_forest = initialize_process_fires(local_forest, rank)
        new_fires = np.sum(local_forest == my_fire_state)
        print(f"[Rank {rank}] Fuegos creados: {new_fires}")
    
    # Ejecutar simulación worker
    simulation_worker_loop()

print(f"[Rank {rank}] Proceso terminado")