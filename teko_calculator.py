# teko_calculator.py
"""
Единствената логика за редене на панели TEKO (височина, ширина, разположение по страни).
Ползва се от app.py и drawing_generator.py.
Правилата следват "Алгоритъм за редене на кофража":
  - първо панели 60, после по-малки; страните A и A1 са огледални (60 срещу 60 и т.н.)
  - при L/U стени до външния ъгъл EX идва панел "дебелина + 10" (10 = ширина на IN),
    след което страната се реди като права стена
"""
import math
from collections import Counter

IN_CORNER_CM = 10

STANDARD_HEIGHT_MAP = {
    240: [120, 120],
    270: [150, 120],
    300: [150, 150],
    330: [150, 120, 60],
    360: [150, 150, 60]
}

# Остатък след панелите 60 -> малки панели. 65/70/75 се получават, когато
# остатъкът е 5/10/15 и една 60-ка се разменя (напр. 190 = 60+60+35+35 вместо 60+60+60+TC10).
STANDING_REMAINDERS = {
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
    55: [30, 25],
    65: [35, 30],
    70: [35, 35],
    75: [35, 20, 20]
}

LYING_REMAINDERS = {
    60: [30, 30],
    65: [35, 30],
    70: [35, 35],
    75: [35, 20, 20],
    80: [35, 25, 20],
    85: [35, 30, 20],
    90: [30, 30, 30],
    95: [35, 35, 25],
    100: [35, 35, 30],
    105: [35, 35, 35],
    110: [35, 35, 20, 20],
    115: [35, 30, 30, 20]
}

def format_panel_code(width_cm, height_cm):
    """
    Генерира каталожното наименование според официалната спецификация ТЕКО.
    Полегнал ред (височина 60): ширини 150/120 са полегнали големи панели,
    останалите са TK 60/x (TC 60/x за компенсаторите до 15 см).
    Ред 20-35 см (полегнали панели): TK по-голям/по-малък размер, напр. 150/20, 20/15.
    Ред 5/10/15 см - компенсатор отгоре: TC 150/x.
    """
    if is_compensator_row(height_cm):
        return f"TC 150/{int(height_cm)}"
    if height_cm < 60:
        return f"TK {max(width_cm, height_cm)}/{min(width_cm, height_cm)}"
    if height_cm == 60:
        if width_cm == 150:
            return "TK 150/60 (полегнал)"
        if width_cm == 120:
            return "TK 120/60 (полегнал)"
        if width_cm <= 15:
            return f"TC 60/{width_cm}"
        return f"TK 60/{width_cm}"

    if width_cm <= 15 and height_cm in [120, 150]:
        return f"TC {height_cm}/{width_cm}"

    return f"TK {height_cm}/{width_cm}"

COMPENSATOR_PIECE_CM = 150  # компенсаторът отгоре се смята на парчета по 150 см

# Остатък над редовете 150/120/60 (под 60 см), отдолу нагоре:
# 5/10/15 - компенсатор TC отгоре; 20-35 - ред легнали панели; 40-55 - два реда.
TOP_REMAINDERS = {
    0: [], 5: [5], 10: [10], 15: [15],
    20: [20], 25: [25], 30: [30], 35: [35],
    40: [20, 20], 45: [25, 20], 50: [30, 20], 55: [30, 25],
}

# Дължини на панелите в ред с височина 20-35 см (легнали големи и малки панели от спецификацията)
STRIP_PIECES = {
    20: [150, 120, 60, 20, 15],   # TK 150/20, 120/20, 60/20, 20/20, 20/15
    25: [150, 120, 60, 40, 30],   # TK 150/25, 120/25, 60/25, 40/25, 30/25
    30: [150, 120, 60, 25],       # TK 150/30, 120/30, 60/30, 30/25
    35: [150, 120, 60],           # TK 150/35, 120/35, 60/35
}

def is_compensator_row(height_cm):
    """Ред с височина 5/10/15 см - компенсатор TC отгоре (винаги най-горният ред)."""
    return 0 < height_cm <= 15

def compensator_pieces(length_cm):
    """Брой компенсатори по 150 см за дължина (закръглено нагоре: 1000 см -> 7 бр.)."""
    return int(math.ceil(round(length_cm, 6) / COMPENSATOR_PIECE_CM))

def _height_bases(height_cm):
    """
    Точните комбинации от редове 150 / 120 / 60 до височината, с остатък под 60 см -
    от най-високата към по-ниските. За всяка сума - с по-малко редове, после повече 150.
    Подредени отдолу нагоре: 150, 120, 60.
    """
    best = {}
    for n150 in range(height_cm // 150 + 1):
        for n120 in range((height_cm - 150 * n150) // 120 + 1):
            for n60 in range((height_cm - 150 * n150 - 120 * n120) // 60 + 1):
                levels = [150] * n150 + [120] * n120 + [60] * n60
                total = sum(levels)
                key = (-len(levels), n150)
                if height_cm - total < 60 and (total not in best or key > best[total][0]):
                    best[total] = (key, levels)
    return [best[total][1] for total in sorted(best, reverse=True)]

def _remainder_options(rem):
    """
    Начини за остатъка отгоре, по ред на предпочитане. Първо TOP_REMAINDERS; при 40-55 см -
    и другите два реда легнали, после два реда + компенсатор (по-големият TC първи),
    напр. 55 = 30 + 25, 35 + 20, после 20 + 20 + TC 15 (55.pdf).
    """
    options = [TOP_REMAINDERS[rem]]
    if rem >= 40:
        strips = sorted(STRIP_PIECES, reverse=True)
        pairs = lambda r: [[a, b] for a in strips for b in strips if a >= b and a + b == r]
        options += [p for p in pairs(rem) if p not in options]
        for tc in (15, 10, 5):
            options += [p + [tc] for p in pairs(rem - tc)]
    return options

def height_candidates(height_cm):
    """
    Възможните разпределения по височина (отдолу нагоре), по ред на предпочитане:
    най-високата основа от 150 / 120 / 60 с остатъка отгоре, после по-ниските основи.
    layout_element взима първото, при което редовете легнали панели покриват страните точно.
    """
    height_cm = _round_up_to_5(height_cm)
    if height_cm in STANDARD_HEIGHT_MAP:
        return [list(STANDARD_HEIGHT_MAP[height_cm])]
    return [base + rest for base in _height_bases(height_cm)
            for rest in _remainder_options(height_cm - sum(base))]

def solve_height_cm(height_cm):
    """
    Пресмята височинното разпределение на панелите (отдолу нагоре), без да гледа дължините.
    За стандартни височини връща фиксираната комбинация. Иначе - най-високата точна
    комбинация от 150 / 120 / 60, а остатъкът (под 60 см) отгоре: 20-55 см - един или два реда
    легнали панели, 5/10/15 см - компенсатор TC (най-отгоре, никога два един до друг).
    Височината се закръгля нагоре до 5 см. Окончателното е в layout_element (сменя основата,
    когато ред легнали не покрива страна точно).
    """
    return height_candidates(height_cm)[0]

def _round_up_to_5(width_cm):
    """Размер, некратен на 5 см, се закръгля нагоре (допълва се с компенсатор TC 5)."""
    return int(math.ceil(round(width_cm, 6) / 5.0) * 5)

def _solve_width_standing(width_cm):
    """Изправен ред (H=150/120): максимум панели 60, остатъкът с малки панели."""
    count_60, rem = divmod(width_cm, 60)
    if rem in (5, 10, 15) and count_60 > 0:
        count_60 -= 1
        rem += 60
    return [60] * count_60 + STANDING_REMAINDERS[rem]

def _solve_width_lying(width_cm):
    """Полегнал ред (H=60): първо полегнали 150 и 120, после малки модули."""
    count_150, rem = divmod(width_cm, 150)
    count_120, rem = divmod(rem, 120)
    small = LYING_REMAINDERS.get(rem) or STANDING_REMAINDERS[rem]
    return [150] * count_150 + [120] * count_120 + small

def _solve_width_strip(width_cm, pieces):
    """
    Ред легнали панели с височина 20-35 см: точно покритие с възможно най-малко панели,
    големите отляво, малките допълват отдясно (200 = 120 + 60 + 20, 205 = 150 + 20 + 20 + 15).
    Когато не може точно - най-малкото надхвърляне (последният панел излиза).
    """
    limit = width_cm + max(pieces)
    best = {0: []}   # дължина -> най-малко панели, по-големите първи
    for total in range(5, limit + 1, 5):
        options = [sorted(best[total - p] + [p], reverse=True)
                   for p in pieces if total - p in best]
        if options:
            best[total] = min(options, key=lambda r: (len(r), [-x for x in r]))
    reach = min(t for t in best if t >= width_cm)
    return best[reach]

def solve_width_cm(width_cm, height_level_cm=150):
    """
    Подреден списък с ширините на панелите за един ред с дадена височина.
    Сумата е равна на ширината (закръглена нагоре до 5 см); надхвърля я само ред легнали
    панели 20-35 см, когато няма точно покритие.
    """
    if width_cm <= 0:
        return []
    w = _round_up_to_5(width_cm)
    if is_compensator_row(height_level_cm):
        return [w]
    if height_level_cm in STRIP_PIECES:
        return _solve_width_strip(w, STRIP_PIECES[height_level_cm])
    if height_level_cm == 60:
        return _solve_width_lying(w)
    return _solve_width_standing(w)

def _face(name, segments, levels, start=None, end=None, flip=()):
    """
    Страна от кофража. segments са дължини, всяка се реди самостоятелно с solve_width_cm,
    така че еднаквите сегменти на срещуположните страни излизат огледални.
    flip: индекси на сегментите, редени в обратен ред (панелите 60 откъм края на сегмента).
    """
    return {
        "name": name,
        "length_cm": sum(max(0, s) for s in segments),
        "start": start,
        "end": end,
        "rows": _face_rows(segments, levels, flip),
        "segments": list(segments),
        "flip": tuple(flip),
    }

def _face_rows(segments, levels, flip=()):
    rows = []
    for h in levels:
        if is_compensator_row(h):
            # компенсаторът е една лента по цялата страна
            rows.append([sum(_round_up_to_5(seg) for seg in segments if seg > 0)])
            continue
        row = []
        for i, seg in enumerate(segments):
            widths = solve_width_cm(seg, h)
            row += widths[::-1] if i in flip else widths
        rows.append(row)
    return rows

def _strip_misses(faces, levels):
    """Брой сегменти, които някой ред легнали 20-35 см не покрива точно (последният панел излиза)."""
    strips = [h for h in levels if h in STRIP_PIECES]
    return sum(1 for face in faces for seg in face["segments"] if seg > 0
               and any(sum(solve_width_cm(seg, h)) != _round_up_to_5(seg) for h in strips))

def layout_element(elem_type, height_cm, length_cm=0, width_cm=0, thickness_cm=25,
                   l1_cm=0, l2_cm=0, l3_cm=0, closed_ends=0,
                   closed_end_1=None, closed_end_2=None, closed_end_3=False):
    """
    Разположение на панелите по страни и редове за един елемент.

    elem_type: "column" (width x length), "wall" (length, thickness),
               "l_wall" (l1 = рамо A, l2 = рамо B, thickness),
               "u_wall" (l1 = рамо A, l2 = гръб B, l3 = рамо C, thickness),
               "t_wall" (l1 = страна A (полката), l2 = страна B / B1 (реброто, от предното лице
                         на полката до края му), thickness; реброто е в средата на полката).
    closed_end_1 / closed_end_2: затворени челни края (стени). Край 1 е краят на рамо A
                 (при права стена - десният), край 2 - краят на последното рамо B / C
                 (при права стена - левият). При T-стена: край 1 - десният край на полката,
                 край 2 - левият, closed_end_3 - краят на реброто.
    closed_ends: 0/1/2 - кратък запис, когато не е зададено кой край: 1 = край 1, 2 = двата.

    Връща речник с height_levels, faces (всяка с rows = ширини по редове отдолу нагоре)
    и corners (брой позиции EX / IN).
    """
    levels = solve_height_cm(height_cm)
    t = float(thickness_cm or 0)
    k = t + IN_CORNER_CM
    if closed_end_1 is None and closed_end_2 is None:
        n = max(0, min(2, int(closed_ends or 0)))
        closed_end_1, closed_end_2 = n >= 1, n >= 2
    closed = [bool(closed_end_1), bool(closed_end_2)]
    faces = []
    ex, inn = 0, 0

    if elem_type == "column":
        a, b = float(width_cm), float(length_cm)
        faces = [
            _face("A", [a], levels, "EX", "EX"),
            _face("A1", [a], levels, "EX", "EX"),
            _face("B", [b], levels, "EX", "EX"),
            _face("B1", [b], levels, "EX", "EX"),
        ]
        ex = 4
        dims = {"a": a, "b": b}
        closed = [False, False]

    elif elem_type == "wall":
        length = float(length_cm)
        end_r = "EX" if closed[0] else None
        end_l = "EX" if closed[1] else None
        faces = [
            _face("A", [length], levels, end_l, end_r),
            _face("A1", [length], levels, end_l, end_r),
        ]
        if closed[0]:
            faces.append(_face("Край 1", [t], levels, "EX", "EX"))
        if closed[1]:
            faces.append(_face("Край 2", [t], levels, "EX", "EX"))
        ex = 2 * sum(closed)
        dims = {"length": length, "t": t}

    elif elem_type == "l_wall":
        l1, l2 = float(l1_cm), float(l2_cm)
        end_a = "EX" if closed[0] else None
        end_b = "EX" if closed[1] else None
        faces = [
            _face("A", [k, l1 - k], levels, "EX", end_a),
            _face("A1", [l1 - k], levels, "IN", end_a),
            _face("B", [k, l2 - k], levels, "EX", end_b),
            _face("B1", [l2 - k], levels, "IN", end_b),
        ]
        if closed[0]:
            faces.append(_face("Край A", [t], levels, "EX", "EX"))
        if closed[1]:
            faces.append(_face("Край B", [t], levels, "EX", "EX"))
        ex = 1 + 2 * sum(closed)
        inn = 1
        dims = {"l1": l1, "l2": l2, "t": t}

    elif elem_type == "u_wall":
        l1, l2, l3 = float(l1_cm), float(l2_cm), float(l3_cm)
        end_a = "EX" if closed[0] else None
        end_c = "EX" if closed[1] else None
        faces = [
            _face("A", [k, l1 - k], levels, "EX", end_a),
            _face("A1", [l1 - k], levels, "IN", end_a),
            _face("B", [k, l2 - 2 * k, k], levels, "EX", "EX"),
            _face("B1", [l2 - 2 * k], levels, "IN", "IN"),
            _face("C", [k, l3 - k], levels, "EX", end_c),
            _face("C1", [l3 - k], levels, "IN", end_c),
        ]
        if closed[0]:
            faces.append(_face("Край A", [t], levels, "EX", "EX"))
        if closed[1]:
            faces.append(_face("Край C", [t], levels, "EX", "EX"))
        ex = 2 + 2 * sum(closed)
        inn = 2
        dims = {"l1": l1, "l2": l2, "l3": l3, "t": t}

    elif elem_type == "t_wall":
        # Полка A (задно лице, цяло) и A1 (предно лице, разделено от реброто на ляво и дясно,
        # винаги с IN при реброто); ребро B / B1 от IN до края на реброто (край 3).
        # Срещу „IN + ребро + IN“ на A стои сегмент t + 20, така че A е огледална на A1.
        # EX - само на затворените краища, по 2 на край.
        # Реброто е винаги в средата на полката (l3 не се ползва).
        l1, l2 = float(l1_cm), float(l2_cm)
        p = math.floor((l1 - t) / 2 / 5.0) * 5
        left, right, stem = p - IN_CORNER_CM, l1 - p - t - IN_CORNER_CM, l2 - IN_CORNER_CM
        closed.append(bool(closed_end_3))
        end_1 = "EX" if closed[0] else None
        end_2 = "EX" if closed[1] else None
        end_3 = "EX" if closed[2] else None
        faces = [
            _face("A", [left, t + 2 * IN_CORNER_CM, right], levels, end_2, end_1, flip=(0,)),
            _face("A1 ляво", [left], levels, end_2, "IN", flip=(0,)),
            _face("A1 дясно", [right], levels, "IN", end_1),
            _face("B", [stem], levels, end_3, "IN", flip=(0,)),
            _face("B1", [stem], levels, end_3, "IN", flip=(0,)),
        ]
        if closed[0]:
            faces.append(_face("Край 1", [t], levels, "EX", "EX"))
        if closed[1]:
            faces.append(_face("Край 2", [t], levels, "EX", "EX"))
        if closed[2]:
            faces.append(_face("Край 3", [t], levels, "EX", "EX"))
        ex = 2 * sum(closed)
        inn = 2
        dims = {"l1": l1, "l2": l2, "l3": p, "t": t}

    else:
        raise ValueError(f"Непознат тип елемент: {elem_type}")

    # Ред легнали, който не покрива страна точно -> следващата по-ниска основа (55.pdf: 205 см).
    # Избира се разпределението с най-малко непокрити сегменти (челата 25 см често не се покриват).
    candidates = height_candidates(height_cm)
    best = min(candidates, key=lambda c: _strip_misses(faces, c))
    if best != levels:
        levels = best
        for face in faces:
            face["rows"] = _face_rows(face["segments"], levels, face["flip"])

    return {
        "type": elem_type,
        "height_cm": float(height_cm),
        "height_levels": levels,
        "thickness_cm": t,
        "closed_ends": sum(closed),
        "closed": closed,
        "dims": dims,
        "faces": faces,
        "corners": {"EX": ex, "IN": inn},
    }

def count_panels(layout, count=1):
    """Брой панели по каталожен код за разположението (умножено по броя елементи)."""
    totals = Counter()
    for face in layout["faces"]:
        for h, row in zip(layout["height_levels"], face["rows"]):
            if is_compensator_row(h):
                totals[format_panel_code(0, h)] += sum(compensator_pieces(w) for w in row) * count
                continue
            for w in row:
                totals[format_panel_code(w, h)] += count
    return dict(totals)

def calculate_column(width_m, length_m, height_m, count=1):
    width_cm = int(round(width_m * 100))
    length_cm = int(round(length_m * 100))
    height_cm = int(round(height_m * 100))

    perimeter_m = 2 * (width_m + length_m)
    area_per_col = perimeter_m * height_m
    total_area = round(area_per_col * count, 2)

    layout = layout_element("column", height_cm, width_cm=width_cm, length_cm=length_cm)
    detailed_panels = count_panels(layout, count)

    outer_corners = 4 * len(layout["height_levels"]) * count
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

    layout = layout_element("wall", height_cm, length_cm=length_cm, thickness_cm=thickness_cm)
    detailed_panels = count_panels(layout, count)

    total_panel_pieces = sum(detailed_panels.values())
    handles = total_panel_pieces * 4
    tie_rods = len(layout["height_levels"]) * 2 * count
    nuts = tie_rods * 2

    return {
        "type": "Права Стена / Шайба",
        "dimensions": f"L={length_m}м, B={thickness_cm}см, H={height_m}м",
        "count": count,
        "area_m2": total_area,
        "remainder_width_cm": 0,
        "panels_spec": detailed_panels,
        "accessories": {
            "Пластмасови ръкохватки": handles,
            "Шпилка TR 12": tie_rods,
            "Гайка N12": nuts
        }
    }
