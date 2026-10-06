"""
Модул за изчисляване на аксесоари и окомплектовка (TEKO Formwork System)
Напълно съобразен с документа "Алгоритъм за редене на кофража".
"""

import math
from typing import Dict, List, Any, Tuple


# ==========================================
# 1. ИЗЧИСЛЯВАНЕ НА РИГЕЛИ (WALERS)
# ==========================================
def calculate_walers(
    wall_type: str, 
    dim_a_cm: float, 
    dim_b_cm: float, 
    height_cm: float,
    first_row_panel_type: str = "150x60_standing"
) -> Dict[str, Any]:
    """
    Изчислява точния брой, тип и височинни позиции на ригелите (AW).
    
    Правила от документация:
    1. На колони и стени до 35 cm ширина НЕ се поставят ригели.
    2. Първи ред от изправени 120x60: h1 = 18 cm, h2 = 60 cm, след това през 60 cm.
    3. Първи ред от изправени 150x60 или полегнали (120x60/150x60): h1 = 30 cm, след това през 60 cm.
    4. В горните 0-60 cm от стената НЕ се монтира ригел (top margin >= 60 cm).
    """
    a = float(dim_a_cm or 0)
    b = float(dim_b_cm or a)
    h = float(height_cm or 0)
    
    is_column = "Колона" in wall_type or "колона" in wall_type.lower()
    
    # Правило: Ширина <= 35 cm -> Без ригели
    requires_walers_a = a > 35.0
    requires_walers_b = b > 35.0
    
    # Генериране на височинните нива за ригелите
    waler_heights = []
    
    if "120x60_standing" in first_row_panel_type:
        # Вариант А: 120x60 изправен панел на първи ред
        candidate_heights = [18.0, 60.0]
        curr_h = 120.0
        while curr_h < h:
            candidate_heights.append(curr_h)
            curr_h += 60.0
    else:
        # Вариант Б: 150x60 изправен или полегнал панел
        candidate_heights = []
        curr_h = 30.0
        while curr_h < h:
            candidate_heights.append(curr_h)
            curr_h += 60.0
            
    # Прилагане на правилото за горните 60 cm без ригел
    for wh in candidate_heights:
        if (h - wh) >= 60.0:
            waler_heights.append(wh)

    num_levels = len(waler_heights)
    bom = {}
    positions = []

    if is_column:
        if requires_walers_a or requires_walers_b:
            waler_code = "Ригел AW 100" if max(a, b) <= 100 else "Ригел AW 150"
            count = num_levels * 4  # 4 ригела на ниво за затягане
            bom[waler_code] = count
            
            for level_h in waler_heights:
                positions.append({"height_cm": level_h, "sides": ["A1", "A2", "B1", "B2"], "type": waler_code})
    else:
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
    Изчислява броя и позиционирането на вертикализаторите.
    
    Правила:
    - За колони до 60x60 cm -> по 2 вертикализатора (на 2 съседни страни).
    - За стени с H > 120 cm: отстояние от ръб <= 90 cm, стъпка между тях <= 180 cm.
    """
    h = float(height_cm or 0)
    a = float(dim_a_cm or 0)
    b = float(dim_b_cm or 0)
    
    if h <= 120.0:
        return {"bom": {}, "total_count": 0, "prop_type": "Няма (H <= 120 cm)", "spacing_details": []}

    prop_code = "Вертикализатор PP 300 (2.0 - 3.2 m)" if h <= 300 else "Вертикализатор PP 450 (3.2 - 4.8 m)"

    def get_props_count_for_length(length_cm: float) -> Tuple[int, List[float]]:
        if length_cm <= 0:
            return 0, []
        if length_cm <= 180.0:
            return 1, [round(length_cm / 2.0, 1)]
        
        num_props = 1 + math.ceil((length_cm - 180.0) / 180.0)
        edge_offset = min(90.0, length_cm / (num_props * 2))
        step = (length_cm - 2 * edge_offset) / (num_props - 1) if num_props > 1 else 0
        positions = [round(edge_offset + i * step, 1) for i in range(num_props)]
        return num_props, positions

    is_column = "Колона" in wall_type or "колона" in wall_type.lower()
    total_props = 0
    details = []

    if is_column:
        if a <= 60 and b <= 60:
            total_props = 2  # По 2 вертикализатора на колона до 60x60
            details.append({"side": "Страна A", "count": 1, "positions_cm": [round(a / 2, 1)]})
            details.append({"side": "Страна B (съседна)", "count": 1, "positions_cm": [round(b / 2, 1)]})
        else:
            count_a, pos_a = get_props_count_for_length(a)
            count_b, pos_b = get_props_count_for_length(b)
            total_props = (count_a + count_b) * 2
            details.append({"side": "Страни A1, A2", "count": count_a * 2, "positions_cm": pos_a})
            details.append({"side": "Страни B1, B2", "count": count_b * 2, "positions_cm": pos_b})
    else:
        # При стени - монтаж от двете страни (двустранно)
        count_a, pos_a = get_props_count_for_length(a)
        total_props += count_a * 2
        details.append({"side": "Страна A (двустранно)", "count": count_a * 2, "positions_cm": pos_a})
        
        if wall_type == "L-образна стена" and b > 0:
            count_b, pos_b = get_props_count_for_length(b)
            total_props += count_b * 2
            details.append({"side": "Страна B (двустранно)", "count": count_b * 2, "positions_cm": pos_b})

    bom = {prop_code: total_props} if total_props > 0 else {}

    return {
        "bom": bom,
        "total_count": total_props,
        "prop_type": prop_code,
        "spacing_details": details
    }


# ==========================================
# 3. ИЗЧИСЛЯВАНЕ НА СТЕГИ И РЪКОХВАТКИ
# ==========================================
def calculate_panel_clamps(width_breakdown: List[float], height_breakdown: List[float], sides_count: int = 2) -> Dict[str, Any]:
    """
    Алгоритъм за броене само на допирателните вертикални и хоризонтални фуги между панелите.
    """
    cols = len(width_breakdown)
    rows = len(height_breakdown)
    
    if cols == 0 or rows == 0:
        return {"bom": {}, "vert_joints": 0, "horiz_joints": 0, "total_clamps": 0}

    # 1. Вертикални фуги (между панелите)
    vert_joints_per_row = max(0, cols - 1)
    total_vert_joints = vert_joints_per_row * rows * sides_count
    
    vert_clamps = 0
    for h_val in height_breakdown:
        clamps_per_joint = max(2, int(math.ceil(h_val / 60.0)))
        vert_clamps += vert_joints_per_row * clamps_per_joint * sides_count

    # 2. Хоризонтални фуги (между редовете панели)
    horiz_joints_count = max(0, rows - 1)
    total_horiz_joints = horiz_joints_count * cols * sides_count
    
    horiz_clamps = 0
    if horiz_joints_count > 0:
        for w_val in width_breakdown:
            clamps_per_w = max(1, int(math.ceil(w_val / 40.0)))
            horiz_clamps += horiz_joints_count * clamps_per_w * sides_count

    total_clamps = vert_clamps + horiz_clamps
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
                          height_breakdown: List[float] = None,
                          first_row_panel_type: str = "150x60_standing") -> Dict[str, Any]:
    """
    Обединяваща функция за аксесоарите.
    """
    a = float(dim_a_cm or 0)
    b = float(dim_b_cm or a)
    h = float(height_cm or 0)
    
    is_column = "Колона" in wall_type or "колона" in wall_type.lower()
    sides_count = 4 if is_column else (4 if wall_type == "L-образна стена" else 2)

    if not width_breakdown_a:
        width_breakdown_a = [a]
    if not height_breakdown:
        height_breakdown = [h]

    walers_res = calculate_walers(wall_type, a, b, h, first_row_panel_type=first_row_panel_type)
    props_res = calculate_push_pull_props(wall_type, a, b, h)
    clamps_res = calculate_panel_clamps(width_breakdown_a, height_breakdown, sides_count=sides_count)

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
