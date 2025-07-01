# gui.py

import tkinter as tk
import numpy as np
import threading
import time
from config import *
from colors import get_color_advanced
from mpi4py import MPI

comm = MPI.COMM_WORLD

# Colores para distinguir los procesos
PROCESS_COLORS = ['#FFFFFF', '#00FF00', '#FF0000', '#0000FF', '#FFFF00', '#00FFFF', '#FF00FF']

def get_rank_color(rank):
    return PROCESS_COLORS[rank % len(PROCESS_COLORS)]

class AdvancedFireApp:
    def __init__(self, root, all_process_info, logger, local_forest, local_elevation, local_humidity, local_temperature, owner_local, simulation_callback):
        self.root = root
        self.logger = logger
        self.local_forest = local_forest
        self.local_elevation = local_elevation
        self.local_humidity = local_humidity
        self.local_temperature = local_temperature
        self.all_process_info = all_process_info
        self.owner_local = owner_local
        self.simulation_callback = simulation_callback
        self.size = comm.Get_size()
        self.hostname = all_process_info[0]['hostname']
        self.running = True
        self.step = 0

        self.root.title(f"Simulación de Incendios Forestales - MPI ({self.size} procesos) - {self.hostname}")
        self.root.configure(bg="#1a1a1a")

        main_frame = tk.Frame(root, bg="#1a1a1a")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left_panel = tk.Frame(main_frame, bg="#2d2d2d", relief=tk.RAISED, bd=2, width=250)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)

        title_label = tk.Label(left_panel, text="SIMULACIÓN MPI", bg="#2d2d2d", fg="#ff6600",
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(10, 5))

        cluster_info = tk.Label(left_panel, text=f"Cluster: {self.size} procesos",
                                bg="#2d2d2d", fg="#00ff00", font=("Arial", 11, "bold"))
        cluster_info.pack(pady=2)

        self.create_process_info_panel(left_panel)

        separator = tk.Frame(left_panel, height=2, bg="#555555")
        separator.pack(fill=tk.X, padx=10, pady=10)

        legend_title = tk.Label(left_panel, text="LEYENDA", bg="#2d2d2d", fg="#ffffff",
                                font=("Arial", 12, "bold"))
        legend_title.pack(pady=(5, 10))

        self.create_legend(left_panel)

        separator2 = tk.Frame(left_panel, height=2, bg="#555555")
        separator2.pack(fill=tk.X, padx=10, pady=10)

        stats_title = tk.Label(left_panel, text="ESTADÍSTICAS", bg="#2d2d2d", fg="#ffffff",
                               font=("Arial", 11, "bold"))
        stats_title.pack(pady=(5, 10))

        self.stats_frame = tk.Frame(left_panel, bg="#2d2d2d")
        self.stats_frame.pack(fill=tk.X, padx=10)

        right_panel = tk.Frame(main_frame, bg="#1a1a1a")
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        canvas_frame = tk.Frame(right_panel, bg="#1a1a1a", relief=tk.SUNKEN, bd=2)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, width=COLS * CELL_SIZE, height=ROWS * CELL_SIZE,
                                bg="#000000", highlightthickness=0)
        self.canvas.pack()

        self.rects = [[
            self.canvas.create_rectangle(
                j * CELL_SIZE, i * CELL_SIZE,
                (j + 1) * CELL_SIZE, (i + 1) * CELL_SIZE,
                fill=get_color_advanced(TREE_MATURE), outline="#000000", width=1
            ) for j in range(COLS)] for i in range(ROWS)]

        control_frame = tk.Frame(right_panel, bg="#1a1a1a")
        control_frame.pack(fill=tk.X, pady=5)

        self.step_label = tk.Label(control_frame, text="Paso: 0", bg="#1a1a1a", fg="#ffffff",
                                   font=("Arial", 12, "bold"))
        self.step_label.pack(side=tk.LEFT, padx=10)

        pause_btn = tk.Button(control_frame, text="⏸Pausar", command=self.toggle_pause,
                              bg="#ff6600", fg="white", font=("Arial", 10, "bold"))
        pause_btn.pack(side=tk.RIGHT, padx=5)

        reset_btn = tk.Button(control_frame, text="Reiniciar", command=self.reset_simulation,
                              bg="#00aa00", fg="white", font=("Arial", 10, "bold"))
        reset_btn.pack(side=tk.RIGHT, padx=5)

        logger.info("GUI inicializada, comenzando simulación")
        threading.Thread(target=self.simulation_callback, daemon=True).start()

    def create_process_info_panel(self, parent):
        info_title = tk.Label(parent, text="PROCESOS ACTIVOS", bg="#2d2d2d", fg="#ffffff",
                              font=("Arial", 11, "bold"))
        info_title.pack(pady=(10, 10))

        info_frame = tk.Frame(parent, bg="#2d2d2d")
        info_frame.pack(fill=tk.X, padx=5)

        for info in self.all_process_info:
            process_frame = tk.Frame(info_frame, bg="#404040", relief=tk.RAISED, bd=1)
            process_frame.pack(fill=tk.X, pady=1)

            tk.Label(process_frame, text=f"Proceso {info['rank']}",
                     bg="#404040", fg="#00ff00", font=("Arial", 9, "bold")).pack(anchor="w", padx=5, pady=1)

            tk.Label(process_frame, text=f" {info['hostname'][:15]}",
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
        for widget in self.stats_frame.winfo_children():
            widget.destroy()

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

    def update_step(self, step):
        self.step = step
        self.step_label.config(text=f"Paso: {step}")

    def update_visualization(self, forest_data, owners_data):
        for i in range(min(ROWS, forest_data.shape[0])):
            for j in range(min(COLS, forest_data.shape[1])):
                color = get_color_advanced(forest_data[i, j])
                outline = get_rank_color(owners_data[i, j])
                self.canvas.itemconfig(self.rects[i][j], fill=color, outline=outline)
        self.root.update_idletasks()

    def toggle_pause(self):
        self.running = not self.running

    def reset_simulation(self):
        self.step = 0
