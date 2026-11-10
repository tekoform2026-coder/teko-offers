"""
Модул за изчисляване на аксесоари и окомплектовка (TEKO Formwork System)
Напълно съобразен с документа "Алгоритъм за редене на кофража".
"""

import math
from typing import Dict, List, Any, Tuple

from teko_calculator import format_panel_code, is_compensator_row


# ==========================================
# 1. ИЗЧИСЛЯВАНЕ НА РИГЕЛИ (WALERS)
# ==========================================
WALER_LENGTHS_CM = [300, 200, 100]   # Alignment waling AW300 / AW200 / AW100 (спецификацията)
NARROW_LIMIT_CM = 35.0               # колони и стени до 35 cm широки - без ригели
TOP_FREE_CM = 60.0                   # в горните 0-60 cm няма ригел
WALER_OVERHANG_CM = 10.0             # ригелът може да излиза до 10 см извън края (Алгоритъм, т. 9)


def waler_heights_cm(height_cm: float, first_row_height_cm: float) -> List[float]:
    """
    Височини на ригелите (и анкерните нива) според Алгоритъма:
      - долен ред изправени 120x60: 18 см, после +42 (=60), после през 60 см
      - иначе (изправени 150x60 или полегнали): 30 см, после през 60 см
      - нов ригел само ако над него остават поне 60 см (0-60 см отгоре - празно)
    """
    h = float(height_cm or 0)
    if first_row_height_cm == 120:
        candidates = [18.0, 60.0]
        curr = 120.0
    else:
        candidates = [30.0]
        curr = 90.0
    while curr < h:
        candidates.append(curr)
        curr += 60.0
    return [wh for wh in candidates if (h - wh) >= TOP_FREE_CM]


def _waler_pieces(length_cm: float, max_cm: float = None) -> List[int]:
    """
    Ригели за страна с дадена дължина. Ригелът може да излиза до 10 см извън края или да спре
    до 10 см преди края; когато няма точен размер, се избира най-близката обща дължина
    (при равенство - по-дългата), съставена от AW300 + остатък AW200/AW100.
    max_cm: най-голямата обща дължина, която се побира (вътрешна страна).
    """
    total = max(100, int(math.floor(length_cm / 100.0 + 0.5)) * 100)
    if max_cm is not None:
        total = min(total, int(math.floor(max_cm / 100.0 + 1e-9)) * 100)
        if total <= 0:
            return []
    count_300, rem = divmod(total, 300)
    return [300] * count_300 + ([rem] if rem else [])


def waler_levels_cm(height_cm: float, first_row_height_cm: float) -> List[float]:
    """
    Нива на ригелите: waler_heights_cm, а при нисък елемент без нито едно ниво - един ред
    ригели в средата на височината (Solar farm Tipperary: H=35 см - по един ригел на страна).
    Шпилките остават по waler_heights_cm.
    """
    return waler_heights_cm(height_cm, first_row_height_cm) or [float(height_cm or 0) / 2.0]


def face_waler_pieces(face: Dict[str, Any]) -> List[int]:
    """
    Ригели на една страна (стандартни AW 100 / 200 / 300).
    Вътрешна страна (с ъгъл IN): ригелите не трябва да удрят в стената - при ъгъла IN ригелът
    спира на края на страната (отвъд е панелът на перпендикулярната стена), а в другия край
    може да излиза до 10 см (Алгоритъм, т. 9). Избира се най-дългата комбинация, която се побира.
    """
    length = face["length_cm"]
    if length <= NARROW_LIMIT_CM:
        return []
    ends = [face["start"], face["end"]]
    if "IN" not in ends:
        return _waler_pieces(length)
    free_ends = sum(1 for e in ends if e != "IN")
    return _waler_pieces(length, length + WALER_OVERHANG_CM * free_ends)


def _first_row_height(layout: Dict[str, Any]) -> float:
    levels = layout.get("height_levels") or [150]
    return levels[0]


def calculate_walers(layout: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ригели по страни от teko_calculator.layout_element:
    на всяко ниво по един комплект ригели на всяка страна, по-широка от 35 cm.
    """
    h = layout["height_cm"]
    heights = waler_levels_cm(h, _first_row_height(layout))
    bom: Dict[str, int] = {}
    positions = []

    for face in layout["faces"]:
        length = face["length_cm"]
        pieces = face_waler_pieces(face)
        if not pieces:
            continue
        for p in pieces:
            code = f"Ригел AW {p}"
            bom[code] = bom.get(code, 0) + len(heights)
        positions.append({"side": face["name"], "length_cm": length,
                          "walers": [f"AW {p}" for p in pieces], "heights_cm": heights})

    return {
        "bom": bom,
        "levels_count": len(heights),
        "height_positions_cm": heights,
        "detailed_positions": positions
    }


# ==========================================
# 2. ИЗЧИСЛЯВАНЕ НА ШПИЛКИ И ГАЙКИ (TIE RODS & NUTS)
# ==========================================
TIE_FACES_PREFIXES = ("A1", "B1", "C1")  # вътрешните страни на L-, П- и Т-стена
TIE_RODS_PER_M2 = 1.35                   # шпилки на m² кофраж (потребителят, 10.11.2026)


def _tie_faces(layout: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Страните, чиито панели се броят за шпилки: шпилката минава през стената там, където два панела
    стоят един срещу друг - по една на панел от вътрешната страна (10.11.2026).
    Права стена - A (= A1); колона - A и B; L / П / Т - A1, B1, C1 (без панелите до EX и челата).
    """
    faces = [f for f in layout["faces"] if f["length_cm"] > NARROW_LIMIT_CM]
    if layout["type"] == "column":
        return [f for f in faces if f["name"] in ("A", "B")]
    if layout["type"] == "wall":
        return [f for f in faces if f["name"] == "A"]
    return [f for f in faces if f["name"].startswith(TIE_FACES_PREFIXES)]


def _row_at_height(levels: List[float], height_cm: float) -> int:
    """Индекс на реда панели (отдолу нагоре), в който е височината."""
    top = 0.0
    for i, level in enumerate(levels):
        top += level
        if height_cm < top:
            return i
    return len(levels) - 1


def calculate_tie_rods(
    wall_type: str,
    dim_a_cm: float,
    dim_b_cm: float,
    height_cm: float,
    width_breakdown_a: List[float] = None,
    first_row_panel_type: str = "150x60_standing",
    layout: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Шпилки и гайки (10.11.2026): по-голямото от 1,35 на m² кофраж (всички страни на layout, вкл.
    челата, закръглено нагоре) и реденето по панели - на всяко ниво на анкериране (както ригелите -
    30, 90, 150 cm и т.н.) по една шпилка на всеки панел от страните на _tie_faces. Елемент без шпилки
    по панели (без нива, страни до 35 cm) - без шпилки. Гайките са 2 на шпилка.
    Без layout - права стена с панелите width_breakdown_a.
    """
    a = float(dim_a_cm or 0)
    b = float(dim_b_cm or a)
    h = float(height_cm or 0)
    empty = {"bom": {}, "rods_count": 0, "nuts_count": 0, "levels_count": 0}

    # Височинните нива за анкериране съвпадат с ригелите
    first_row_h = 120 if "120x60_standing" in first_row_panel_type else 150
    tie_heights = waler_heights_cm(h, first_row_h)
    num_levels = len(tie_heights)
    if num_levels == 0:
        return empty

    if layout:
        levels = layout["height_levels"]
        faces = _tie_faces(layout)
        by_panels = sum(len(face["rows"][_row_at_height(levels, y)]) for y in tie_heights for face in faces)
        area_m2 = sum(face["length_cm"] for face in layout["faces"]) * h / 10000.0
        by_area = int(math.ceil(round(TIE_RODS_PER_M2 * area_m2, 6))) if by_panels else 0
        total_rods = max(by_area, by_panels)
    else:
        if a <= NARROW_LIMIT_CM:
            return empty
        total_rods = num_levels * len(width_breakdown_a or [a])

    # За всяка шпилка са необходими 2 броя гайки
    total_nuts = total_rods * 2

    bom = {}
    if total_rods > 0:
        bom["Шпилка TR 12"] = total_rods
        bom["Гайка N12"] = total_nuts

    return {
        "bom": bom,
        "rods_count": total_rods,
        "nuts_count": total_nuts,
        "levels_count": num_levels,
        "height_positions_cm": tie_heights
    }


# ==========================================
# 3. ИЗЧИСЛЯВАНЕ НА ЪГЛИ (EX И IN CORNERS)
# ==========================================
EX_CORNER_CODE = "Външен ъгъл EX240"
IN_CORNER_CODES = {150: "Вътрешен ъгъл IN150", 120: "Вътрешен ъгъл IN120"}
EX_ONE_PIECE_MAX_CM = 270  # до 270 cm височина - 1 външен ъгъл EX240


def ex_corner_pieces(height_cm: float) -> int:
    """Брой парчета EX240 на една позиция без рязане: 1 до 270 cm, после по едно на всеки следващи 240 cm."""
    over = max(0.0, float(height_cm) - EX_ONE_PIECE_MAX_CM)
    return 1 + math.ceil(over / EX_PIECE_HEIGHT_CM)


def ex_corner_cover(height_cm: float) -> Tuple[int, float]:
    """
    Една позиция EX: (цели EX240, дължина на отрязаното допълнение в cm).
    Допускът 30 cm остава (1 EX240 до 270 cm); над него допълнението е височината - 270
    (вариант А, 31.10.2026), отрязано от EX240.
    """
    over = max(0.0, float(height_cm) - EX_ONE_PIECE_MAX_CM)
    full, cut = divmod(over, EX_PIECE_HEIGHT_CM)
    return 1 + int(full), cut


def ex_corner_total(height_cm: float, positions: int) -> int:
    """
    Брой EX240 за всички позиции на елемента: целите парчета + EX240, от които се режат
    допълненията (от едно EX240 - толкова допълнения, колкото се побират; остатъците не се ползват).
    Напр. 4 позиции, 310 cm: 4 цели + 1 EX240 нарязан на 4 x 40 cm = 5.
    """
    if positions <= 0:
        return 0
    full, cut = ex_corner_cover(height_cm)
    total = positions * full
    if cut > 0:
        per_bar = int(EX_PIECE_HEIGHT_CM // cut)
        total += math.ceil(positions / per_bar)
    return total


def in_corner_pieces(height_cm: float) -> List[int]:
    """
    Парчета IN (височини в cm, отдолу нагоре) на една позиция: комбинацията от IN150 и IN120, която
    покрива височината с най-малко излишък, при равенство - с по-малко парчета (10.11.2026, вместо
    редуване 150 / 120): 240 - 120 + 120, 270 - 150 + 120, 300 - 150 + 150, 360 - 3 x 120.
    """
    h = float(height_cm)
    best = None
    n = 1
    while best is None or 120 * n <= best[0]:
        for k in range(n + 1):   # k парчета IN150, останалите IN120
            total = 150 * k + 120 * (n - k)
            if total >= h and (best is None or (total, n) < best[:2]):
                best = (total, n, [150] * k + [120] * (n - k))
        n += 1
    return best[2]


def calculate_corners(layout: Dict[str, Any]) -> Dict[str, int]:
    """
    Брой външни (EX240) и вътрешни (IN150 / IN120) ъгли: позициите от разположението на панелите
    (layout["corners"] - отчита типа елемент и затворените краища) по парчетата по височина.
    """
    if not layout:
        return {}
    h = float(layout["height_cm"] or 0)
    if h <= 0:
        return {}

    bom = {}
    ex_positions = layout["corners"]["EX"]
    if ex_positions:
        bom[EX_CORNER_CODE] = ex_corner_total(h, ex_positions)
    in_positions = layout["corners"]["IN"]
    if in_positions:
        for size in in_corner_pieces(h):
            code = IN_CORNER_CODES[size]
            bom[code] = bom.get(code, 0) + in_positions
    return bom

# ==========================================
# 4. ИЗЧИСЛЯВАНЕ НА ВЕРТИКАЛИЗАТОРИ (PUSH-PULL PROPS)
# ==========================================
PROP_EDGE_MAX_CM = 90.0      # до ъгъла/ръба на стената - не повече от 90 cm
PROP_SPACING_MAX_CM = 180.0  # между два съседни вертикализатора - не повече от 180 cm
PROP_CODE = "Вертикализатор PP"  # един вид за всички височини
LOW_ELEMENT_CM = 60.0        # под 60 cm - вертикализатори като в Solar farm Tipperary (H=35)
STRAIGHT_WALL_2_1_CM = (60.0, 175.0)  # права стена 60-175 cm - 2 + 1 (потребителят, 10.11.2026)
STRAIGHT_WALL_2_1_MAX_H_CM = 300.0    # над 300 cm височина - 2 + 2


def _props_on_sides(length_cm: float, height_cm: float, straight_wall: bool = False) -> Tuple[int, int]:
    """
    Стена (всяко рамо на L/U): (брой на външната страна, брой срещу тях).
    До 120 cm - по един от двете дълги страни, един срещу друг; над 120 cm - по два на дългата
    страна, повече при нужда, така че до ръба да са <= 90 cm и между съседни <= 180 cm.
    Права стена 60-175 cm (straight_wall): 2 на външната страна и 1 в средата срещу тях, а при височина
    над 300 cm - 2 + 2; рамената на L-, П- и Т-стена - без промяна.
    Нисък елемент (под 60 cm, Solar farm Tipperary): срещу - само колкото трябват по 90 / 180 cm,
    на външната страна - поне 2 (110-170 cm - 2 + 1, 190-220 cm - 2 + 2).
    """
    if length_cm <= 0:
        return 0, 0
    if straight_wall and STRAIGHT_WALL_2_1_CM[0] <= length_cm <= STRAIGHT_WALL_2_1_CM[1]:
        return (2, 2) if height_cm > STRAIGHT_WALL_2_1_MAX_H_CM else (2, 1)
    needed = max(1, 1 + int(math.ceil((length_cm - 2 * PROP_EDGE_MAX_CM) / PROP_SPACING_MAX_CM)))
    if height_cm < LOW_ELEMENT_CM:
        return max(2, needed), needed
    if length_cm <= 120.0:
        return 1, 1
    return max(2, needed), max(2, needed)


def _prop_positions(length_cm: float, count: int) -> List[float]:
    if count <= 0:
        return []
    if count == 1:
        return [round(length_cm / 2.0, 1)]
    edge = min(PROP_EDGE_MAX_CM, length_cm / (2.0 * count))
    step = (length_cm - 2 * edge) / (count - 1)
    return [round(edge + i * step, 1) for i in range(count)]


def calculate_push_pull_props(layout: Dict[str, Any]) -> Dict[str, Any]:
    """
    Вертикализатори по Алгоритъма:
      - колона: по два на колона, на две съседни страни
      - стена / рамо на L и U: по _props_on_sides на външната страна и срещу тях
    """
    h = layout["height_cm"]
    prop_code = PROP_CODE
    faces = {f["name"]: f for f in layout["faces"]}
    details = []

    if layout["type"] == "column":
        total = 2
        details.append({"side": "Страни A и B (съседни)", "count": 2,
                        "positions_cm": [round(faces["A"]["length_cm"] / 2, 1), round(faces["B"]["length_cm"] / 2, 1)]})
    else:
        total = 0
        for name in ("A", "B", "C"):
            if name not in faces:
                continue
            length = faces[name]["length_cm"]
            outer, opposite = _props_on_sides(length, h, layout["type"] == "wall")
            total += outer + opposite
            details.append({"side": f"Страна {name} (двустранно)", "count": outer + opposite,
                            "positions_cm": _prop_positions(length, outer),
                            "opposite_positions_cm": _prop_positions(length, opposite)})

    return {
        "bom": {prop_code: total} if total > 0 else {},
        "total_count": total,
        "prop_type": prop_code,
        "spacing_details": details
    }


# ==========================================
# 5. ИЗЧИСЛЯВАНЕ НА РЪКОХВАТКИ (HANDLES)
# ==========================================
# Отвори за ръкохватки по ръб с дадена дължина (Спесификация размери, тегло и аксесоари.xlsx):
# TK 150/60 -> 10 по височина, 4 по ширина; TK 120/x -> 8; ширина 35/30 -> 2; 25/20/15 -> 1; 10 -> 0.
EDGE_HOLES = {150: 10, 120: 8, 60: 4, 40: 2, 35: 2, 30: 2, 25: 1, 20: 1, 15: 1, 10: 0, 5: 0}
EX_HOLES_PER_SIDE = 16  # EXTERNAL CORNER EX240: 16 отвора по височина на всяко рамо
EX_PIECE_HEIGHT_CM = 240

SMALL_PANEL_CODES = {"TK 40/25", "TK 30/25", "TK 20/20", "TK 20/15", "TK 15/15"}

HANDLE_BY_KINDS = {
    frozenset(["MAIN"]): "Ръкохватка H8",           # основен - основен
    frozenset(["MAIN", "SMALL"]): "Ръкохватка H6",  # основен - малък
    frozenset(["SMALL"]): "Ръкохватка H5",          # малък - малък
}


def _holes_for_length(length_cm: float) -> int:
    """Отвори по ръб: точна стойност от таблицата или най-близката по-малка дължина."""
    keys = [k for k in EDGE_HOLES if k <= length_cm]
    return EDGE_HOLES[max(keys)] if keys else 0


def _overlap_holes(overlap_cm: float) -> int:
    """
    Отвори по общия ръб на два разминати панела (хоризонтална фуга): по таблицата, но
    застъпване 10 см има 1 отвор (Solar farm Tipperary: ред 20 под ред 15, 20 срещу 15 и 150 срещу 20).
    """
    if 10 <= overlap_cm < 15:
        return 1
    return _holes_for_length(overlap_cm)


def _panel_kind(width_cm: float, height_cm: float) -> str:
    code = format_panel_code(int(width_cm), height_cm)  # без int(): редът панели 15 не е TC
    if code.startswith("TC"):
        return "METAL"
    if code in SMALL_PANEL_CODES:
        return "SMALL"
    return "MAIN"


def _vertical_edge_holes(width_cm: float, height_cm: float) -> int:
    """Отвори по вертикалния ръб на панел в ред с височина height_cm (и при компенсаторите TC)."""
    return _holes_for_length(height_cm)


def _horizontal_edge_holes(width_cm: float, height_cm: float) -> int:
    """Отвори по хоризонталния ръб; металните компенсатори TC нямат отвори по ширина."""
    if _panel_kind(width_cm, height_cm) == "METAL":
        return 0
    return _holes_for_length(width_cm)


def _handle_code(kind_a: str, kind_b: str):
    """Тип ръкохватка за допира; метал с метал не се свързва (None)."""
    if kind_a == "METAL" and kind_b == "METAL":
        return None
    if "METAL" in (kind_a, kind_b):
        return "Ръкохватка H4"
    return HANDLE_BY_KINDS[frozenset([kind_a, kind_b])]


def calculate_handles(layout: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ръкохватки само там, където елемент опира в елемент (не към земята, въздуха или отворен край):
      - вертикални фуги между съседни панели в ред: отворите по височината на реда
      - хоризонтални фуги между редовете: отворите по общия ръб
      - компенсатор TC отгоре (H4): отворите по горния ръб на всеки панел под него
      - панел до ъгъл EX (H4): до 16 отвора на рамо на цял EX240, на отрязаното парче - пропорционално
      - панел до ъгъл IN (H4): IN150/IN120 по редове, отворите по височината на реда
    layout е резултатът от teko_calculator.layout_element.
    """
    levels = layout["height_levels"]
    ex_full, ex_cut = ex_corner_cover(layout["height_cm"])
    # отвори на рамо по височината на ъгъла: 16 на цял EX240, на отрязаното - пропорционално
    ex_holes = EX_HOLES_PER_SIDE * ex_full + int(EX_HOLES_PER_SIDE * ex_cut // EX_PIECE_HEIGHT_CM)
    bom: Dict[str, int] = {}

    def add(code, qty):
        if code and qty > 0:
            bom[code] = bom.get(code, 0) + qty

    vert_joints = 0
    horiz_joints = 0

    for face in layout["faces"]:
        rows = face["rows"]

        # 1. Вертикални фуги в реда
        for h, row in zip(levels, rows):
            for w_left, w_right in zip(row, row[1:]):
                qty = min(_vertical_edge_holes(w_left, h), _vertical_edge_holes(w_right, h))
                add(_handle_code(_panel_kind(w_left, h), _panel_kind(w_right, h)), qty)
                vert_joints += 1

        # 2. Хоризонтални фуги между редовете (по припокриването на панелите)
        for r in range(len(rows) - 1):
            h_low, h_up = levels[r], levels[r + 1]
            low_x = 0
            for w_low in rows[r]:
                up_x = 0
                for w_up in rows[r + 1]:
                    overlap = min(low_x + w_low, up_x + w_up) - max(low_x, up_x)
                    if overlap > 0 and is_compensator_row(h_up):
                        # компенсатор отгоре (H4): отворите по горния ръб на панела под него
                        if _panel_kind(w_low, h_low) != "METAL":
                            add("Ръкохватка H4", min(_horizontal_edge_holes(w_low, h_low), _holes_for_length(overlap)))
                    elif overlap > 0:
                        qty = min(_horizontal_edge_holes(w_low, h_low), _horizontal_edge_holes(w_up, h_up))
                        if not (low_x == up_x and w_low == w_up):
                            qty = min(qty, _overlap_holes(overlap))
                        add(_handle_code(_panel_kind(w_low, h_low), _panel_kind(w_up, h_up)), qty)
                        horiz_joints += 1
                    up_x += w_up
                low_x += w_low

        # 3. Ъгли в краищата на страната
        for edge, idx in (("start", 0), ("end", -1)):
            corner = face[edge]
            if not corner:
                continue
            row_holes = [_vertical_edge_holes(row[idx], h) for h, row in zip(levels, rows)
                         if row and _panel_kind(row[idx], h) != "METAL"]
            if corner == "EX":
                # по всички отвори на рамото на EX240, и при нисък елемент (Solar farm Tipperary:
                # H=35 см, 4 EX - 128 H4)
                add("Ръкохватка H4", ex_holes)
            else:
                add("Ръкохватка H4", sum(row_holes))

    return {
        "bom": bom,
        "vert_joints_count": vert_joints,
        "horiz_joints_count": horiz_joints,
        "total_handles": sum(bom.values())
    }


# ==========================================
# 6. ГЛАВНА ФУНКЦИЯ: CALCULATE_ACCESSORIES
# ==========================================
def calculate_accessories(wall_type: str, dim_a_cm: float, dim_b_cm: float, height_cm: float,
                          width_breakdown_a: List[float] = None, 
                          height_breakdown: List[float] = None,
                          first_row_panel_type: str = "150x60_standing",
                          layout: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Обединяваща функция за аксесоарите, шпилките, гайките и ъглите.
    layout (teko_calculator.layout_element) е нужен за ригелите, вертикализаторите и ръкохватките.
    """
    a = float(dim_a_cm or 0)
    b = float(dim_b_cm or a)
    h = float(height_cm or 0)

    if not width_breakdown_a:
        width_breakdown_a = [a]
    if not height_breakdown:
        height_breakdown = [h]

    empty = {"bom": {}}
    if layout:
        first_row_panel_type = "120x60_standing" if _first_row_height(layout) == 120 else "150x60_standing"
    walers_res = calculate_walers(layout) if layout else empty
    ties_res = calculate_tie_rods(wall_type, a, b, h, width_breakdown_a=width_breakdown_a,
                                  first_row_panel_type=first_row_panel_type, layout=layout)
    props_res = calculate_push_pull_props(layout) if layout else empty
    clamps_res = calculate_handles(layout) if layout else empty
    corners_res = calculate_corners(layout)

    combined_bom = {}
    for sub_res in [walers_res["bom"], ties_res["bom"], props_res["bom"], clamps_res["bom"], corners_res]:
        for code, qty in sub_res.items():
            combined_bom[code] = combined_bom.get(code, 0) + qty

    return {
        "bom_summary": combined_bom,
        "walers": walers_res,
        "tie_rods": ties_res,
        "push_pull_props": props_res,
        "clamps_and_handles": clamps_res,
        "corners": corners_res
    }
