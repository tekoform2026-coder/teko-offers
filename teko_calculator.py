import math

def calculate_column(width_m, length_m, height_m, count=1):
    """
    Изчислява кофражната площ (m²) за правоъгълна/квадратна колона.
    """
    perimeter = 2 * (width_m + length_m)
    area_per_column = perimeter * height_m
    
    return {
        "type": "Колона",
        "dimensions": f"{int(width_m*100)}x{int(length_m*100)} cm, H={height_m}m",
        "count": count,
        "area_m2": round(area_per_column * count, 2)
    }

def calculate_wall(length_m, thickness_m, height_m, count=1):
    """
    Изчислява кофражната площ (m²) за бетонова стена/шайба (две страни + чела).
    """
    side_area = 2 * (length_m * height_m)
    ends_area = 2 * (thickness_m * height_m)
    area_per_wall = side_area + ends_area
    
    return {
        "type": "Стена / Шайба",
        "dimensions": f"L={length_m}m, B={int(thickness_m*100)}cm, H={height_m}m",
        "count": count,
        "area_m2": round(area_per_wall * count, 2)
    }

def estimate_teko_panels(total_area_m2):
    """
    Изчислява необходимия брой основни TEKO панели (120х60 см = 0.72 m²) 
    и необходимите свързващи ръкохватки/стяги.
    """
    panel_area = 1.20 * 0.60  # 0.72 m² площ на един панел 120x60 cm
    needed_panels = math.ceil(total_area_m2 / panel_area)
    needed_handles = needed_panels * 4  # Средно по 4 ръкохватки на панел
    
    return {
        "main_panels_120x60": needed_panels,
        "handles": needed_handles
    }

# --- ТЕСТ НА МОДУЛА ---
if __name__ == "__main__":
    print("=== ТЕСТ НА ИЗЧИСЛИТЕЛНИЯ ДВИГАТЕЛ TEKO ===")
    
    # Примерен тест: 4 колони (40x40 см, H=3.00 м) и 1 стена (L=6.00 м, B=25 см, H=3.00 м)
    col_res = calculate_column(width_m=0.40, length_m=0.40, height_m=3.00, count=4)
    wall_res = calculate_wall(length_m=6.00, thickness_m=0.25, height_m=3.00, count=1)
    
    total_area = round(col_res["area_m2"] + wall_res["area_m2"], 2)
    teko_spec = estimate_teko_panels(total_area)
    
    print(f"1. {col_res['count']} бр. {col_res['type']} ({col_res['dimensions']}): {col_res['area_m2']} m² кофраж")
    print(f"2. {wall_res['count']} бр. {wall_res['type']} ({wall_res['dimensions']}): {wall_res['area_m2']} m² кофраж")
    print("-" * 55)
    print(f"ОБЩО Кофражна площ: {total_area} m²")
    print(f"Оценка TEKO панели (120x60 cm): ~{teko_spec['main_panels_120x60']} бр. (с {teko_spec['handles']} ръкохватки)")