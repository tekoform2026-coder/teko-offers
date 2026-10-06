"""
Модул за изчисляване на аксесоари и окомплектовка (TEKO Formwork System)
Стъпка 2: Ригели, Вертикализатори и Ръкохватки/Стеги.
"""

import math
from typing import Dict, List, Any, Tuple


# ==========================================
# 1. ИЗЧИСЛЯВАНЕ НА РИГЕЛИ (WALERS)
# ==========================================
def calculate_walers(wall_type: str, dim_a_cm: float, dim_b_cm: float, height_cm: float) -> Dict[str, Any]:
    """
    Изчислява точния брой, тип и височинни позиции на ригелите (AW).
    
    Правила:
    - За стени/колони с ширина > 35 cm се поставят ригели.
    - Позиции по височина: през ~120 cm (стандартно на h=50 cm, 120 cm, 180 cm, 240 cm, 300 cm...).
    - Първият ред панели определя началната височина на първия ригел.
    """
    a = float(dim_a_cm or 0)
    b = float(dim_b_cm or a)
    h = float(height_cm or 0)
    
    is_column = "Колона" in wall_type or "колона" in wall_type.lower()
    
    # Ригели се изискват при широчина/размер > 35 cm
    requires_walers_a = a > 35
    requires_walers_b = b > 35
    
    # Определяне на височинните нива за ригели
    waler_heights = []
    current_h = 50.0  # Първи ригел на 50 cm от кота 0
    while current_h < h:
        waler_heights.append(current_h)
        current_h += 120.0  # Стъпка 120 cm
        
    num_levels = len(waler_heights)
    
    bom = {}
    positions = []

    if is_column:
        if requires_walers_a or requires_walers_b:
            # При колони с размер > 35 cm се ползват ригели AW 100/150 за затягане на 4-те страни
            waler_code = "Ригел AW 100" if max(a, b) <= 100 else "Ригел AW 150"
            count = num_levels * 4  # По 4 ригела на ниво
            bom[waler_code] = count
            
            for level_h in waler_heights:
                positions.append({"height_cm": level_h, "sides": ["A1", "A2", "B1", "B2"], "type": waler_code})
    else:
        # При прави и L-образни стени
        if requires_walers_a:
            code_a = f"Ригел AW {200 if a >= 200 else 150 if a >= 150 else 100}"
            count_a = num_levels * 2  # Двустранно
            bom[code_a] = bom.get(code_a, 0) + count_a
            
            for level_h in waler_heights:
                positions.append({"height_cm": level_h, "side": "A (двустранно)", "type": code_a})

        if wall_type == "L-образна стена" and requires_walers_b:
            code_b = f"Ригел AW {200 if b >= 200 else 150 if b >= 150 else 100}"
            count_b = num_levels * 2
            bom[code_b] = bom.get(code_b, 0) + count_b
            
            for level_h in waler_heights:
                positions.append({"height_cm": level_h, "side": "B (двустранно)", "type": code_b})

    return {
        "bom": bom,
        "levels_count": num_levels,
        "height_positions_cm": waler_heights,
        "detailed_positions": positions
    }


# ==========================================
# 2. ИЗЧИСЛЯВАНЕ НА ВЕРТИКАЛИЗАТОРИ (PUSH-PULL PROPS)
# ==========================================
def calculate_push_pull_props(wall_type: str, dim_a_cm: float, dim_b_cm: float, height_cm: float) -> Dict[str, Any]:
    """
    Изчислява броя и позиционирането на вертикализаторите (PP).
    
    Правила:
    - Изискват се САМО за елементи с височина > 120 cm.
    - Максимално разстояние от ръб/ъгъл: 90 cm.
    - Максимална стъпка между вертикализаторите: 180 cm.
    """
    h = float(height_cm or 0)
    a = float(dim_a_cm or 0)
    b = float(dim_b_cm or 0)
    
    # Под 120 cm не се изискват вертикализатори
    if h <= 120.0:
        return {
            "bom": {},
            "total_count": 0,
            "prop_type": "Няма (H <= 120 cm)",
            "spacing_details": []
        }

    # Определяне на типа вертикализатор според височината
    if h <= 300:
        prop_code = "Вертикализатор PP 300 (2.0 - 3.2 m)"
    else:
        prop_code = "Вертикализатор PP 450 (3.2 - 4.8 m)"

    def get_props_count_for_length(length_cm: float) -> Tuple[int, List[float]]:
        """Изчислява брой и точно разпределение (в cm от началото) по дължина."""
        if length_cm <= 0:
            return 0, []
        
        # Ако дължината е до 180 cm - 1 вертикализатор в средата (на L/2 <= 90 cm от всеки ръб)
        if length_cm <= 180.0:
            return 1, [round(length_cm / 2.0, 1)]
        
        # За дължини > 180 cm:
        # N = 1 + ceil((L - 180) / 180)
        num_props = 1 + math.ceil((length_cm - 180.0) / 180.0)
        
        # Равномерно разпределение с крайни точки <= 90 cm
        edge_offset = min(90.0, length_cm / (num_props * 2))
        step = (length_cm - 2 * edge_offset) / (num_props - 1) if num_props > 1 else 0
        
        positions = [round(edge_offset + i * step, 1) for i in range(num_props)]
        return num_props, positions

    is_column = "Колона" in wall_type or "колона" in wall_type.lower()
    
    total_props = 0
    details = []

    if is_column:
        # Колоните се укрепват с поне 2 вертикализатора под 90 градуса
        total_props = 2
        details.append({"side": "Страна A", "count": 1, "positions_cm": [round(a / 2, 1)]})
        details.append({"side": "Страна B", "count": 1, "positions_cm": [round(b / 2, 1)]})
    else:
        # За прави и L-образни стени
        count_a, pos_a = get_props_count_for_length(a)
        total_props += count_a
        details.append({"side": "Страна A", "count": count_a, "positions_cm": pos_a})
        
        if wall_type == "L-образна стена" and b > 0:
            count_b, pos_b = get_props_count_for_length(b)
            total_props += count_b
            details.append({"side": "Страна B", "count": count_b, "positions_cm": pos_b})

    bom = {prop_code: total_props} if total_props > 0 else {}

    return {
        "bom": bom,
        "total_count": total_props,
        "prop_type": prop_code,
        "spacing_details": details
    }


# ==========================================
# 3. ИЗЧИСЛЯВАНЕ НА СТЕГИ И РЪКОХВАТКИ (CLAMPS & HANDLES)
# ==========================================
def calculate_panel_clamps(width_breakdown: List[float], height_breakdown: List[float], sides_count: int = 2) -> Dict[str, Any]:
    """
    Алгоритъм за преброяване на допирателните вертикални и хоризонтални фуги между панелите.
    
    Правила:
    - Вертикална фуга: между 2 съседни панела. Стеги се поставят през ~60 cm височина (мин. 2 бр./фуга).
    - Хоризонтална фуга: между 2 реда панели по височина. Стеги се поставят по дължината на панела.
    """
    cols = len(width_breakdown)
    rows = len(height_breakdown)
    
    if cols == 0 or rows == 0:
        return {"bom": {}, "vert_joints": 0, "horiz_joints": 0, "total_clamps": 0}

    # 1. Вертикални фуги (между колоните от панели)
    # Брой вертикални фуги на един ред = cols - 1
    vert_joints_per_row = max(0, cols - 1)
    total_vert_joints = vert_joints_per_row * rows * sides_count
    
    vert_clamps = 0
    for h_val in height_breakdown:
        # Поне 2 стеги на вертикална фуга, или през 60 cm
        clamps_per_joint = max(2, int(math.ceil(h_val / 60.0)))
        vert_clamps += vert_joints_per_row * clamps_per_joint * sides_count

    # 2. Хоризонтални фуги (между редовете панели)
    # Брой хоризонтални фуги по височина = rows - 1
    horiz_joints_count = max(0, rows - 1)
    total_horiz_joints = horiz_joints_count * cols * sides_count
    
    horiz_clamps = 0
    if horiz_joints_count > 0:
        for w_val in width_breakdown:
            # По 1 стега на всеки 30-60 cm ширина
            clamps_per_w = max(1, int(math.ceil(w_val / 40.0)))
            horiz_clamps += horiz_joints_count * clamps_per_w * sides_count

    total_clamps = vert_clamps + horiz_clamps
    
    # Добавяме ръкохватки за пренасяне (по 2 на панел)
    total_panels = cols * rows * sides_count
    total_handles = total_panels * 2

    bom = {
        "Бърза стега TEKO": total_clamps,
        "Монтажна ръкохватка": total_handles
    }

    return {
        "bom": bom,
        "vert_joints_count": total_vert_joints,
        "horiz_joints_count": total_horiz_joints,
        "total_clamps": total_clamps,
        "total_handles": total_handles
    }


# ==========================================
# 4. ГЛАВНА ФУНКЦИЯ: CALCULATE_ACCESSORIES
# ==========================================
def calculate_accessories(wall_type: str, dim_a_cm: float, dim_b_cm: float, height_cm: float,
                          width_breakdown_a: List[float] = None, 
                          height_breakdown: List[float] = None) -> Dict[str, Any]:
    """
    Обединяваща функция за пълен изчислетелен анализ на аксесоарите.
    """
    a = float(dim_a_cm or 0)
    b = float(dim_b_cm or a)
    h = float(height_cm or 0)
    
    is_column = "Колона" in wall_type or "колона" in wall_type.lower()
    sides_count = 4 if is_column else (4 if wall_type == "L-образна стена" else 2)

    # Резервни стойности за разбивката, ако не са подадени
    if not width_breakdown_a:
        width_breakdown_a = [a]
    if not height_breakdown:
        height_breakdown = [h]

    # Изчисления
    walers_res = calculate_walers(wall_type, a, b, h)
    props_res = calculate_push_pull_props(wall_type, a, b, h)
    clamps_res = calculate_panel_clamps(width_breakdown_a, height_breakdown, sides_count=sides_count)

    # Обединяване на КС (BOM)
    combined_bom = {}
    for sub_res in [walers_res["bom"], props_res["bom"], clamps_res["bom"]]:
        for code, qty in sub_res.items():
            combined_bom[code] = combined_bom.get(code, 0) + qty

    return {
        "bom_summary": combined_bom,
        "walers": walers_res,
        "push_pull_props": props_res,
        "clamps_and_handles": clamps_res
    }
