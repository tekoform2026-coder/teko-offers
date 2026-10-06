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
    Генерира каталожното наименование според официалната спецификация ТЕКО.
    Строго разграничава изправени от полегнали панели и гарантира,
    че няма несъществуващ панел 60/60.
    """
    if height_cm == 60:
        if width_cm == 150:
            return "TK 150/60 (полегнал)"
        elif width_cm == 120:
            return "TK 120/60 (полегнал)"
        elif width_cm <= 15:
            return f"TC 60/{width_cm}"
        else:
            return f"TK 60/{width_cm}"
    
    if width_cm <= 15 and height_cm in [120, 150]:
        return f"TC {height_cm}/{width_cm}"
    
    return f"TK {height_cm}/{width_cm}"

def solve_height_cm(height_cm):
    """
    Пресмята височинното разпределение на панелите.
    За стандартни височини връща фиксираната комбинация.
    За нестандартни височини използва първо изправени панели (150/120 см),
    а остатъкът под 120 см се запълва с полегнали панели (с височина 60 см).
    """
    if height_cm in STANDARD_HEIGHT_MAP:
        return STANDARD_HEIGHT_MAP[height_cm]
    
    remaining = height_cm
    levels = []
    
    # 1. Изправени панели 150 см
    while remaining >= 150:
        levels.append(150)
        remaining -= 150
        
    # 2. Изправени панели 120 см
    while remaining >= 120:
        levels.append(120)
        remaining -= 120

    # 3. Остатък: Полегнали панели с височина 60 см
    while remaining > 0:
        levels.append(60)
        remaining -= 60 if remaining >= 60 else remaining
            
    return levels

def solve_width_cm_standing(width_cm):
    """
    Пресмята разпределението по ширина за изправен ред (H=150 или H=120 см)
    с приоритет на основните панели 60 см.
    """
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

def solve_width_cm_lying(width_cm):
    """
    Пресмята разпределението по ширина за полегнал ред (H=60 см).
    Приоритет имат големите полегнали панели с ширина 150 см и 120 см.
    Остатъкът се допълва с по-малки модули (без панел 60/60).
    """
    remaining = width_cm
    panels = {}

    # 1. Полегнали панели 150 см (височина 60 см, ширина 150 см)
    count_150 = remaining // 150
    if count_150 > 0:
        panels[150] = count_150
        remaining -= count_150 * 150

    # 2. Полегнали панели 120 см (височина 60 см, ширина 120 см)
    count_120 = remaining // 120
    if count_120 > 0:
        panels[120] = count_120
        remaining -= count_120 * 120

    # 3. Допълване на остатъка под 120 см с малки модули (35, 30, 25, 20...)
    if remaining > 0:
        fit_rem = (remaining // 5) * 5
        exact_rem = remaining % 5
        
        if fit_rem == 60:
            remainder_list = [30, 30]
        elif fit_rem > 60:
            if fit_rem == 65: remainder_list = [35, 30]
            elif fit_rem == 70: remainder_list = [35, 35]
            elif fit_rem == 75: remainder_list = [35, 20, 20]
            elif fit_rem == 80: remainder_list = [35, 25, 20]
            elif fit_rem == 85: remainder_list = [35, 30, 20]
            elif fit_rem == 90: remainder_list = [30, 30, 30]
            elif fit_rem == 95: remainder_list = [35, 35, 25]
            elif fit_rem == 100: remainder_list = [35, 35, 30]
            elif fit_rem == 105: remainder_list = [35, 35, 35]
            elif fit_rem == 110: remainder_list = [35, 35, 20, 20]
            elif fit_rem == 115: remainder_list = [35, 30, 30, 20]
            else: remainder_list = OPTIMAL_REMAINDERS.get(fit_rem, [])
        else:
            remainder_list = OPTIMAL_REMAINDERS.get(fit_rem, [])

        for w in remainder_list:
            panels[w] = panels.get(w, 0) + 1
    else:
        exact_rem = 0

    return panels, exact_rem

def solve_width_cm(width_cm, height_level_cm=150):
    """
    Избира съответния алгоритъм за ширина според това дали редът е полегнал (60 см) или изправен.
    """
    if height_level_cm == 60:
        return solve_width_cm_lying(width_cm)
    else:
        return solve_width_cm_standing(width_cm)

def calculate_column(width_m, length_m, height_m, count=1):
    width_cm = int(round(width_m * 100))
    length_cm = int(round(length_m * 100))
    height_cm = int(round(height_m * 100))
    
    perimeter_m = 2 * (width_m + length_m)
    area_per_col = perimeter_m * height_m
    total_area = round(area_per_col * count, 2)
    
    height_levels = solve_height_cm(height_cm)
    detailed_panels = {}

    for h in height_levels:
        side_a_panels, _ = solve_width_cm(width_cm, h)
        side_b_panels, _ = solve_width_cm(length_cm, h)

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
    detailed_panels = {}
    last_remainder = 0

    for h in height_levels:
        side_panels, remainder = solve_width_cm(length_cm, h)
        last_remainder = remainder
        for w, c in side_panels.items():
            key = format_panel_code(w, h)
            detailed_panels[key] = detailed_panels.get(key, 0) + (c * 2 * count)
            
    total_panel_pieces = sum(detailed_panels.values())
    handles = total_panel_pieces * 4
    tie_rods = len(height_levels) * 2 * count
    nuts = tie_rods * 2
    
    return {
        "type": "Права Стена / Шайба",
        "dimensions": f"L={length_m}м, B={thickness_cm}см, H={height_m}м",
        "count": count,
        "area_m2": total_area,
        "remainder_width_cm": last_remainder,
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
    detailed_panels = {}

    for h in height_levels:
        out1_panels, _ = solve_width_cm(l1_cm, h)
        out2_panels, _ = solve_width_cm(l2_cm, h)
        in1_panels, _ = solve_width_cm(max(0, l1_cm - thickness_cm), h)
        in2_panels, _ = solve_width_cm(max(0, l2_cm - thickness_cm), h)

        for side in [out1_panels, out2_panels, in1_panels, in2_panels]:
            for w, c in side.items():
                key = format_panel_code(w, h)
                detailed_panels[key] = detailed_panels.get(key, 0) + (c * count)
                
    total_panel_pieces = sum(detailed_panels.values())
    inner_corners = 1 * len(height_levels) * count
    outer_corners = 1 * len(height_levels) * count
    
    handles = (total_panel_pieces + inner_corners + outer_corners) * 4
    tie_rods = len(height_levels) * 4 * count
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
    detailed_panels = {}

    for h in height_levels:
        out1_panels, _ = solve_width_cm(l1_cm, h)
        out2_panels, _ = solve_width_cm(l2_cm, h)
        out3_panels, _ = solve_width_cm(l3_cm, h)
        
        in1_panels, _ = solve_width_cm(max(0, l1_cm - thickness_cm), h)
        in2_panels, _ = solve_width_cm(max(0, l2_cm - 2 * thickness_cm), h)
        in3_panels, _ = solve_width_cm(max(0, l3_cm - thickness_cm), h)

        for side in [out1_panels, out2_panels, out3_panels, in1_panels, in2_panels, in3_panels]:
            for w, c in side.items():
                key = format_panel_code(w, h)
                detailed_panels[key] = detailed_panels.get(key, 0) + (c * count)
                
    total_panel_pieces = sum(detailed_panels.values())
    inner_corners = 2 * len(height_levels) * count
    outer_corners = 2 * len(height_levels) * count
    
    handles = (total_panel_pieces + inner_corners + outer_corners) * 4
    tie_rods = len(height_levels) * 6 * count
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
