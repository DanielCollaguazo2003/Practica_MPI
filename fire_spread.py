# fire_spread.py

import random
from config import *

def spread_fire_complex(forest, elevation, humidity, temperature, step, logger):
    new_forest = forest.copy()
    rows, cols = forest.shape
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
