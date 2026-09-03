# teko_calculator.py
import math

MAIN_WIDTHS_CM = [60, 35, 30, 25, 20]
COMPENSATOR_WIDTHS_CM = [15, 10, 5]

STANDARD_HEIGHT_MAP = {
    240: [120, 120],
    270: [150, 120],
    300: [150, 150],
    330: [150, 120, 60],
    360: [150, 150, 60]
}

OPTIMAL_REMAINDERS = {
    0: [],
    5: [5],
    10: [10],
    15: [15],
    20: [20],
    25: [25],
    30: [30],
    35: [35],
    40: [20, 20],
    45: [25, 20],
    50: [30, 20],
    55: [30, 25]
}

def format_panel_code(width_cm, height_cm):
    """
    Генерира правилното каталожно наименование според системата ТЕКО.
    Ширини <= 15 см при височини 120/150 см са компенсатори (TC).
    Всички останали са стандартни платна (TK).
    """
    if width_cm <= 15 and height_cm in [120, 150]:
        return f"TC {height_cm}/{width_cm}"
    return f"TK {height_cm}/{width_cm}"

def solve_height_cm(height_cm):
    if height_cm in STANDARD_HEIGHT_MAP:
        return STANDARD_HEIGHT_MAP[height_cm]
    
    remaining = height_cm
    levels = []
    for h in [150, 120, 60]:
        while remaining >= h:
            levels.append(h)
            remaining -= h
    return levels

def solve_width_cm(width_cm):
    count_60 = width_cm // 60
    rem = width_cm % 60
    fit_rem = (rem // 5) * 5
    exact_rem = rem % 5
    
    panels = {}
    if count_60 > 0:
        panels[60] = count_60
        
    remainder_list = OPTIMAL_REMAINDERS.get(fit_rem, [])
    for w in remainder_list:
        panels[w] = panels.get(w, 0) + 1
        
    return panels, exact_rem

def calculate_column(width_m, length_m, height_m, count=1):
    width_cm = int(round(width_m * 100))
    length_cm = int(round(length_m * 100))
    height_cm = int(round(height_m * 100))
    
    perimeter_m = 2 * (width_m + length_m)
    area_per_col = perimeter_m * height_m
    total_area = round(area_per_col * count, 2)
    
    height_levels = solve_height_cm(height_cm)
    side_a_panels, _ = solve_width_cm(width_cm)
    side_b_panels, _ = solve_width_cm(length_cm)
    
    detailed_panels = {}
    for h in height_levels:
        for w, c in side_a_panels.items():
            key = format_panel_code(w, h)
            detailed_panels[key] = detailed_panels.get(key, 0) + (c * 2 * count)
        for w, c in side_b_panels.items():
            key = format_panel_code(w, h)
            detailed_panels[key] = detailed_panels.get(key, 0) + (c * 2 * count)
            
    outer_corners = 4 * len(height_levels) * count
    total_panel_pieces = sum(detailed_panels.values())
    handles = (total_panel_pieces + outer_corners) * 3
    
    return {
        "type": "Колона",
        "dimensions": f"{width_cm}x{length_cm} см, H={height_m}м",
        "count": count,
        "area_m2": total_area,
        "panels_spec": detailed_panels,
        "accessories": {
            "Външни ъглови елементи": outer_corners,
            "Пластмасови ръкохватки": handles
        }
    }

def calculate_wall(length_m, thickness_m, height_m, count=1):
    length_cm = int(round(length_m * 100))
    thickness_cm = int(round(thickness_m * 100))
    height_cm = int(round(height_m * 100))
    
    side_area = 2 * (length_m * height_m)
    ends_area = 2 * (thickness_m * height_m)
    area_per_wall = side_area + ends_area
    total_area = round(area_per_wall * count, 2)
    
    height_levels = solve_height_cm(height_cm)
    side_panels, remainder = solve_width_cm(length_cm)
    
    detailed_panels = {}
    for h in height_levels:
        for w, c in side_panels.items():
            key = format_panel_code(w, h)
            detailed_panels[key] = detailed_panels.get(key, 0) + (c * 2 * count)
            
    total_panel_pieces = sum(detailed_panels.values())
    columns_per_side = sum(side_panels.values())
    
    handles = total_panel_pieces * 4
    tie_rods = columns_per_side * len(height_levels) * 2 * count
    nuts = tie_rods * 2
    
    return {
        "type": "Права Стена / Шайба",
        "dimensions": f"L={length_m}м, B={thickness_cm}см, H={height_m}м",
        "count": count,
        "area_m2": total_area,
        "remainder_width_cm": remainder,
        "panels_spec": detailed_panels,
        "accessories": {
            "Пластмасови ръкохватки": handles,
            "Анкерни шпилки": tie_rods,
            "Затягащи гайки": nuts
        }
    }

def calculate_l_wall(l1_m, l2_m, thickness_m, height_m, count=1):
    l1_cm = int(round(l1_m * 100))
    l2_cm = int(round(l2_m * 100))
    thickness_cm = int(round(thickness_m * 100))
    height_cm = int(round(height_m * 100))
    
    total_area = round(2 * (l1_m + l2_m) * height_m * count, 2)
    height_levels = solve_height_cm(height_cm)
    
    out1_panels, _ = solve_width_cm(l1_cm)
    out2_panels, _ = solve_width_cm(l2_cm)
    in1_panels, _ = solve_width_cm(max(0, l1_cm - thickness_cm))
    in2_panels, _ = solve_width_cm(max(0, l2_cm - thickness_cm))
    
    detailed_panels = {}
    for h in height_levels:
        for side in [out1_panels, out2_panels, in1_panels, in2_panels]:
            for w, c in side.items():
                key = format_panel_code(w, h)
                detailed_panels[key] = detailed_panels.get(key, 0) + (c * count)
                
    total_panel_pieces = sum(detailed_panels.values())
    inner_corners = 1 * len(height_levels) * count
    outer_corners = 1 * len(height_levels) * count
    
    handles = (total_panel_pieces + inner_corners + outer_corners) * 4
    tie_rods = (sum(out1_panels.values()) + sum(out2_panels.values())) * len(height_levels) * 2 * count
    nuts = tie_rods * 2
    
    return {
        "type": "L-образна Стена / Шайба",
        "dimensions": f"L1={l1_m}м, L2={l2_m}м, B={thickness_cm}см, H={height_m}м",
        "count": count,
        "area_m2": total_area,
        "panels_spec": detailed_panels,
        "accessories": {
            "Вътрешни ъглови елементи": inner_corners,
            "Външни ъглови елементи": outer_corners,
            "Пластмасови ръкохватки": handles,
            "Анкерни шпилки": tie_rods,
            "Затягащи гайки": nuts
        }
    }

def calculate_u_wall(l1_m, l2_m, l3_m, thickness_m, height_m, count=1):
    l1_cm = int(round(l1_m * 100))
    l2_cm = int(round(l2_m * 100))
    l3_cm = int(round(l3_m * 100))
    thickness_cm = int(round(thickness_m * 100))
    height_cm = int(round(height_m * 100))
    
    total_area = round(2 * (l1_m + l2_m + l3_m - thickness_m) * height_m * count, 2)
    height_levels = solve_height_cm(height_cm)
    
    out1_panels, _ = solve_width_cm(l1_cm)
    out2_panels, _ = solve_width_cm(l2_cm)
    out3_panels, _ = solve_width_cm(l3_cm)
    
    in1_panels, _ = solve_width_cm(max(0, l1_cm - thickness_cm))
    in2_panels, _ = solve_width_cm(max(0, l2_cm - 2 * thickness_cm))
    in3_panels, _ = solve_width_cm(max(0, l3_cm - thickness_cm))
    
    detailed_panels = {}
    for h in height_levels:
        for side in [out1_panels, out2_panels, out3_panels, in1_panels, in2_panels, in3_panels]:
            for w, c in side.items():
                key = format_panel_code(w, h)
                detailed_panels[key] = detailed_panels.get(key, 0) + (c * count)
                
    total_panel_pieces = sum(detailed_panels.values())
    inner_corners = 2 * len(height_levels) * count
    outer_corners = 2 * len(height_levels) * count
    
    handles = (total_panel_pieces + inner_corners + outer_corners) * 4
    tie_rods = (sum(out1_panels.values()) + sum(out2_panels.values()) + sum(out3_panels.values())) * len(height_levels) * 2 * count
    nuts = tie_rods * 2
    
    return {
        "type": "П-образна Стена / Шайба",
        "dimensions": f"L1={l1_m}м, L2={l2_m}м, L3={l3_m}м, B={thickness_cm}см, H={height_m}м",
        "count": count,
        "area_m2": total_area,
        "panels_spec": detailed_panels,
        "accessories": {
            "Вътрешни ъглови елементи": inner_corners,
            "Външни ъглови елементи": outer_corners,
            "Пластмасови ръкохватки": handles,
            "Анкерни шпилки": tie_rods,
            "Затягащи гайки": nuts
        }
    }
