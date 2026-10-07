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
    """
    a = float(dim_a_cm or 0)
    b = float(dim_b_cm or a)
    h = float(height_cm or 0)
    
    is_column = "Колона" in wall_type or "колона" in wall_type.lower()
    
    # Правило: Ширина <= 35 cm -> Без ригели
    requires_walers_a = a > 35.0
    requires_walers_b = b > 35.0
    
    waler_heights = []
    
    if "120x60_standing" in first_row_panel_type:
        candidate_heights = [18.0, 60.0]
        curr_h = 120.0
        while curr_h < h:
            candidate_heights.append(curr_h)
            curr_h += 60.0
    else:
        candidate_heights = []
        curr_h = 30.0
        while curr_h < h:
            candidate_heights.append(curr_h)
            curr_h += 60.0
            
    # В горните 0-60 cm от стената НЕ се монтира ригел
    for wh in candidate_heights:
        if (h - wh) >= 60.0:
            waler_heights.append(wh)

    num_levels = len(waler_heights)
    bom = {}
    positions = []

    if is_column:
        if requires_walers_a or requires_walers_b:
            waler_code = "Ригел AW 100" if max(a, b) <= 100 else "Ригел AW 150"
            count = num_levels * 4
            bom[waler_code] = count
            
            for level_h in waler_heights:
                positions.append({"height_cm": level_h, "sides": ["A1", "A2", "B1", "B2"], "type": waler_code})
    else:
        if requires_walers_a:
            code_a = f"Ригел AW {200 if a >= 200 else 150 if a >= 150 else 100}"
            count_a = num_levels * 2
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
            total_props = 2
            details.append({"side": "Страна A", "count": 1, "positions_cm": [round(a / 2, 1)]})
            details.append({"side": "Страна B (съседна)", "count": 1, "positions_cm": [round(b / 2, 1)]})
        else:
            count_a, pos_a = get_props_count_for_length(a)
            count_b, pos_b = get_props_count_for_length(b)
            total_props = (count_a + count_b) * 2
            details.append({"side": "Страни A1, A2", "count": count_a * 2, "positions_cm": pos_a})
            details.append({"side": "Страни B1, B2", "count": count_b * 2, "positions_cm": pos_b})
    else:
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
# 3. ИЗЧИСЛЯВАНЕ НА РЪКОХВАТКИ (HANDLES)
# ==========================================
def calculate_panel_clamps(width_breakdown: List[float], height_breakdown: List[float], sides_count: int = 2) -> Dict[str, Any]:
    """
    Алгоритъм за преброяване на пластмасовите ръкохватки (H8, H6, H5, H4)
    по допирателните фуги между панелите според Спесификация.xlsx.
    """
    cols = len(width_breakdown)
    rows = len(height_breakdown)
    
    if cols == 0 or rows == 0:
        return {"bom": {}, "vert_joints_count": 0, "horiz_joints_count": 0, "total_handles": 0}

    def classify_panel_type(w: float, h: float) -> str:
        """Определя категорията на елемента: 'MAIN', 'SMALL' или 'METAL'."""
        if w in [5.0, 10.0, 15.0]:
            return 'METAL'
        if w in [20.0, 25.0, 30.0, 35.0, 60.0] and h in [120.0, 150.0]:
            return 'MAIN'
        if h <= 40.0 or w <= 25.0:
            return 'SMALL'
        return 'MAIN'

    def get_handle_code(type1: str, type2: str) -> str:
        """Избира точния модел ръкохватка за фугата."""
        if type1 == 'METAL' or type2 == 'METAL':
            return "Ръкохватка H4"
        if type1 == 'MAIN' and type2 == 'MAIN':
            return "Ръкохватка H8"
        if (type1 == 'MAIN' and type2 == 'SMALL') or (type1 == 'SMALL' and type2 == 'MAIN'):
            return "Ръкохватка H6"
        if type1 == 'SMALL' and type2 == 'SMALL':
            return "Ръкохватка H5"
        return "Ръкохватка H8"

    bom = {}
    
    # 1. Вертикални фуги (между съседни панели по ширина)
    vert_joints_per_row = max(0, cols - 1)
    total_vert_joints = vert_joints_per_row * rows * sides_count
    
    vert_handles_count = 0
    for r_idx, h_val in enumerate(height_breakdown):
        handles_per_joint = max(2, int(math.ceil(h_val / 60.0)))
        for c_idx in range(vert_joints_per_row):
            w_left = width_breakdown[c_idx]
            w_right = width_breakdown[c_idx + 1]
            t_left = classify_panel_type(w_left, h_val)
            t_right = classify_panel_type(w_right, h_val)
            code = get_handle_code(t_left, t_right)
            qty = handles_per_joint * sides_count
            bom[code] = bom.get(code, 0) + qty
            vert_handles_count += qty

    # 2. Хоризонтални фуги (между редовете панели по височина)
    horiz_joints_count = max(0, rows - 1)
    total_horiz_joints = horiz_joints_count * cols * sides_count
    
    horiz_handles_count = 0
    if horiz_joints_count > 0:
        for r_idx in range(horiz_joints_count):
            h_bottom = height_breakdown[r_idx]
            h_top = height_breakdown[r_idx + 1]
            for c_idx, w_val in enumerate(width_breakdown):
                handles_per_w = max(1, int(math.ceil(w_val / 40.0)))
                t_bottom = classify_panel_type(w_val, h_bottom)
                t_top = classify_panel_type(w_val, h_top)
                code = get_handle_code(t_bottom, t_top)
                qty = handles_per_w * sides_count
                bom[code] = bom.get(code, 0) + qty
                horiz_handles_count += qty

    total_handles = vert_handles_count + horiz_handles_count

    return {
        "bom": bom,
        "vert_joints_count": total_vert_joints,
        "horiz_joints_count": total_horiz_joints,
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
