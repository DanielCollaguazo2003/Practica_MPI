# colors.py

from config import *

def get_color_advanced(state):
    colors = {
        EMPTY: "#8B4513",
        TREE_YOUNG: "#90EE90",
        TREE_MATURE: "#228B22",
        TREE_OLD: "#006400",
        FIRE_LOW: "#FF4500",
        FIRE_MEDIUM: "#FF0000",
        FIRE_HIGH: "#8B0000",
        BURNED: "#2F2F2F",
        ASH: "#696969",
        WATER: "#4169E1"
    }
    return colors.get(state, "#000000")
