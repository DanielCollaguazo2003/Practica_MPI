# terrain.py

import numpy as np
import random
import datetime
import platform
import socket

from config import TREE_YOUNG, TREE_MATURE, TREE_OLD, EMPTY, WATER
from mpi4py import MPI

def get_detailed_host_info():
    rank = MPI.COMM_WORLD.Get_rank()
    size = MPI.COMM_WORLD.Get_size()
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

def generate_complex_terrain(rows, cols, size, logger):
    rows_per_proc = rows // size

    logger.info(f"Generando terreno: {rows_per_proc}x{cols} celdas")

    terrain = np.random.choice([TREE_YOUNG, TREE_MATURE, TREE_OLD, EMPTY, WATER],
                               size=(rows_per_proc, cols),
                               p=[0.3, 0.4, 0.2, 0.08, 0.02])

    elevation = np.random.random((rows_per_proc, cols)) * 100
    humidity = np.random.uniform(0.3, 0.9, (rows_per_proc, cols))
    temperature = np.random.uniform(20, 35, (rows_per_proc, cols))

    logger.info("Terreno generado exitosamente")
    return terrain, elevation, humidity, temperature

def initialize_fires(forest, logger):
    num_fires = random.randint(2, 5)
    fires_created = 0

    for _ in range(num_fires):
        i = random.randint(0, forest.shape[0] - 1)
        j = random.randint(0, forest.shape[1] - 1)
        if forest[i, j] in [1, 2, 3]:
            forest[i, j] = random.choice([4, 5, 6])
            fires_created += 1

    logger.info(f"Inicializados {fires_created} focos de incendio")
    return forest
