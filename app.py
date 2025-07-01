# main.py

from mpi4py import MPI
from config import *
from terrain import generate_complex_terrain, initialize_fires, get_detailed_host_info
from logging_config import configure_logger
from fire_spread import spread_fire_complex
from gui import AdvancedFireApp
import tkinter as tk
import numpy as np
import socket
import time
import os

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

logger = configure_logger()
hostname = socket.gethostname()
print(f"[Rank {rank}] Proceso iniciado en {hostname}")

print(f"[Rank {rank}] Sincronizando con otros procesos...")
my_info = get_detailed_host_info()
all_process_info = comm.allgather(my_info)
comm.Barrier()

local_forest, local_elevation, local_humidity, local_temperature = generate_complex_terrain(ROWS, COLS, size, logger)
local_forest = initialize_fires(local_forest, logger)
owner_local = np.full_like(local_forest, rank)

if rank == 0:
    def coordinator_loop():
        step = 0
        while step < STEPS:
            comm.bcast(True, root=0)
            local_forest[:] = spread_fire_complex(local_forest, local_elevation, local_humidity, local_temperature, step, logger)
            owner_local[:] = np.where(
                (local_forest >= FIRE_LOW) & (local_forest <= FIRE_HIGH),
                rank,
                owner_local
            )
            all_forests = comm.gather(local_forest, root=0)
            all_owners = comm.gather(owner_local, root=0)
            full_forest = np.vstack(all_forests)
            full_owners = np.vstack(all_owners)
            app.update_visualization(full_forest, full_owners)
            app.update_stats(full_forest)
            app.update_step(step)
            step += 1
            time.sleep(0.1)
        comm.bcast(False, root=0)

    root = tk.Tk()
    app = AdvancedFireApp(
        root,
        all_process_info,
        logger,
        local_forest,
        local_elevation,
        local_humidity,
        local_temperature,
        owner_local,
        coordinator_loop
    )
    root.mainloop()
else:
    while True:
        try:
            continue_sim = comm.bcast(None, root=0)
            if not continue_sim:
                break
            local_forest = spread_fire_complex(local_forest, local_elevation, local_humidity, local_temperature, 0, logger)
            owner_local = np.where(
                (local_forest >= FIRE_LOW) & (local_forest <= FIRE_HIGH),
                rank,
                owner_local
            )
            comm.gather(local_forest, root=0)
            comm.gather(owner_local, root=0)
        except Exception as e:
            logger.error(f"Error en worker: {e}")
            break

print(f"[Rank {rank}] Proceso terminado")
