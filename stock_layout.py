"""
Редене според складовата наличност (отметката над таблица 1, потребителят 18.11.2026).

Алгоритъмът за редене (teko_calculator.layout_element) не се пипа: тук се взима готовото му разположение
и само когато някой панел не стига в склада, елементът се променя:
  1. Замяна в същия ред: липсващият панел -> най-малко по-малки налични панели, от най-големите
     (60 -> 30 + 30). Сменя се на всички еднакви сегменти на елемента (A и A1 остават огледални);
     в сегмента панелите остават от по-големи към по-малки (големите откъм началото на сегмента).
  2. Пренареждане на целия елемент по височина: другите разпределения от редове 150 / 120 / 60 с
     остатъка отгоре (300 = 150 + 150 -> 120 + 120 + 60), по ширина - пак алгоритъмът, после стъпка 1.
  3. Ако и така не стига - остава разположението на алгоритъма (предупреждението за недостиг остава).
Елементите вземат от склада по ред - по площ на 1 бр. (най-големите първи), при равенство - по таблицата.
Еднаквите редове в таблицата са един елемент (броят се събира) - получават еднакво разположение.
Проверява се само наличността, въведена в склада; панел без наличност в склада не се проверява
и не се ползва за замяна или пренареждане. Аксесоарите не се заменят - те следват панелите.
"""
from collections import Counter
from itertools import combinations_with_replacement

from teko_calculator import (_face_rows, _remainder_options, _round_up_to_5, _strip_misses,
                             count_panels, format_panel_code, is_compensator_row, mirror_t_stem, solve_width_cm)

MAX_REPLACEMENT_PIECES = 6   # най-много панели на мястото на един
WIDTHS = range(5, 155, 5)    # възможните ширини на панелите (кои ги има - по склада)


def panel_area_cm2(layout):
    """Площта на панелите на 1 бр. (ширина x височина), както „Площ“ в app.py."""
    return sum(sum(row) * h for face in layout["faces"]
               for h, row in zip(layout["height_levels"], face["rows"]))


def height_alternatives(height_cm):
    """
    Разпределенията по височина за пренареждане (отдолу нагоре): всички комбинации от редове
    150 / 120 / 60 с остатък под 60 см, от по-високата основа към по-ниската, при равна - с по-малко
    редове и повече 150; остатъкът отгоре - както в алгоритъма (_remainder_options).
    """
    h = _round_up_to_5(height_cm)
    bases = []
    for n150 in range(h // 150 + 1):
        for n120 in range((h - 150 * n150) // 120 + 1):
            for n60 in range((h - 150 * n150 - 120 * n120) // 60 + 1):
                total = 150 * n150 + 120 * n120 + 60 * n60
                if h - total < 60:
                    bases.append((-total, n150 + n120 + n60, -n150, -n120, [150] * n150 + [120] * n120 + [60] * n60))
    bases.sort(key=lambda b: b[:4])
    return [base + rest for *_, base in bases for rest in _remainder_options(h - sum(base), low=not base)]


def _with_levels(layout, levels):
    """Копие на разположението с друго разпределение по височина (ширините - по алгоритъма)."""
    faces = [dict(face, rows=_face_rows(face["segments"], levels, face["flip"])) for face in layout["faces"]]
    for face in faces:
        face.pop("seg_rows", None)
    if layout["type"] == "t_wall":
        mirror_t_stem(faces, levels)   # реброто - огледално, както в layout_element
    return dict(layout, height_levels=list(levels), faces=faces)


def _segment_rows(face, levels):
    """Ширините по редове и сегменти (в реда на сегмента, без обръщане): [ред][сегмент] -> [ширини]."""
    if face.get("seg_rows"):
        return [[list(w) for w in row] for row in face["seg_rows"]]
    return [[[] if is_compensator_row(h) else solve_width_cm(seg, h) for seg in face["segments"]]
            for h in levels]


def _apply_segment_rows(layout, classes):
    """Новите ширини на сегментите -> seg_rows и rows на страните (компенсаторите - без промяна)."""
    levels = layout["height_levels"]
    faces = []
    for face in layout["faces"]:
        seg_rows = _segment_rows(face, levels)
        rows = []
        for r, h in enumerate(levels):
            if is_compensator_row(h):
                rows.append(face["rows"][r])
                continue
            row = []
            for i, seg in enumerate(face["segments"]):
                key = (round(seg, 6), r)
                if key in classes:
                    seg_rows[r][i] = list(classes[key]["widths"])
                widths = seg_rows[r][i]
                row += widths[::-1] if i in face["flip"] else widths
            rows.append(row)
        faces.append(dict(face, rows=rows, seg_rows=seg_rows))
    return dict(layout, faces=faces)


def _replacement(width, h, spare, times, key):
    """
    Най-малко по-малки налични панели с обща ширина width в ред h, от най-големите (60 -> 30 + 30),
    за times места; None - няма. Компенсатори TC в изправен ред не се слагат (никога два един до друг).
    """
    options = []
    for w in WIDTHS:
        if w >= width or (h >= 120 and w <= 15) or (h == 60 and w < 15):   # TK 60/10 няма
            continue
        k = key(format_panel_code(w, h))
        if k is not None and spare.get(k, 0) >= times:
            options.append(w)
    options.sort(reverse=True)
    for n in range(2, MAX_REPLACEMENT_PIECES + 1):
        for combo in combinations_with_replacement(options, n):
            if sum(combo) != width:
                continue
            use = Counter(key(format_panel_code(w, h)) for w in combo)
            if all(spare.get(k, 0) >= q * times for k, q in use.items()):
                return list(combo)
    return None


def _needs(layout, count, key):
    need = Counter()
    for code, qty in count_panels(layout, count).items():
        k = key(code)
        if k is not None:
            need[k] += qty
    return need


def _shortages(need, available):
    return {k: q - available[k] for k, q in need.items() if k in available and q > available[k]}


def replace_in_rows(layout, count, available, key):
    """
    Стъпка 1: замяна на липсващите панели в същия ред. Връща (разположение, замени, недостиг) -
    замени: [(стар код, [нови кодове], брой места)], недостиг: {ключ: колко не стигат}.
    """
    levels = layout["height_levels"]
    classes = {}   # (дължина на сегмента, ред) -> ширини и брой еднакви сегменти (x брой елементи)
    for face in layout["faces"]:
        for r, row in enumerate(_segment_rows(face, levels)):
            if is_compensator_row(levels[r]):
                continue
            for i, seg in enumerate(face["segments"]):
                if seg <= 0 or not row[i]:
                    continue
                cls = classes.setdefault((round(seg, 6), r), {"widths": row[i], "h": levels[r], "m": 0})
                cls["m"] += count
    need = _needs(layout, count, key)
    replaced = []
    changed = set()
    blocked = set()
    while True:
        short = _shortages(need, available)
        if not short:
            break
        progress = False
        for cls_key, cls in sorted(classes.items()):
            h, m = cls["h"], cls["m"]
            # последният (най-малкият) липсващ панел в сегмента - големите остават в началото
            for idx in range(len(cls["widths"]) - 1, -1, -1):
                w = cls["widths"][idx]
                old = key(format_panel_code(w, h))
                if old not in short or (cls_key, idx, w) in blocked:
                    continue
                spare = {k: q - need.get(k, 0) for k, q in available.items() if k != old}
                combo = _replacement(w, h, spare, m, key)
                if combo is None:
                    blocked.add((cls_key, idx, w))
                    continue
                cls["widths"] = sorted(cls["widths"][:idx] + cls["widths"][idx + 1:] + combo, reverse=True)
                need[old] -= m
                for c in combo:
                    need[key(format_panel_code(c, h))] += m
                replaced.append((format_panel_code(w, h), [format_panel_code(c, h) for c in combo], m))
                changed.add(cls_key)
                progress = True
                break
            if progress:
                break
        if not progress:
            break
    if changed:
        layout = _apply_segment_rows(layout, {k: classes[k] for k in changed})
    return layout, replaced, _shortages(need, available)


def fit_to_stock(layout, count, available, key):
    """
    Разположение за един елемент (count бр.) според наличното: стъпки 1, 2, 3 (виж горе).
    Връща речник: layout, replaced (замените), levels_changed, short (недостигът след всичко).
    """
    need = _needs(layout, count, key)
    if not _shortages(need, available):
        return {"layout": layout, "replaced": [], "levels_changed": False, "short": {}}
    fitted, replaced, short = replace_in_rows(layout, count, available, key)
    if not short:
        return {"layout": fitted, "replaced": replaced, "levels_changed": False, "short": {}}
    misses = _strip_misses(layout["faces"], layout["height_levels"])
    for levels in height_alternatives(layout["height_cm"]):
        if levels == layout["height_levels"] or _strip_misses(layout["faces"], levels) > misses:
            continue
        other = _with_levels(layout, levels)
        fitted, replaced, short = replace_in_rows(other, count, available, key)
        # нови панели (които алгоритъмът не ползва) - само с въведена наличност
        unknown = [k for k in _needs(fitted, count, key) if k not in available and k not in need]
        if not short and not unknown:
            return {"layout": fitted, "replaced": replaced, "levels_changed": True, "short": {}}
    return {"layout": layout, "replaced": [], "levels_changed": False,
            "short": _shortages(need, available)}


def plan_project(elements, available, key):
    """
    Разположенията на всички елементи на проекта според склада.
    elements: [(ключ на елемента, разположение по алгоритъма, брой)] в реда на таблицата (еднаквите -
    вече събрани); available: {ключ в склада: наличност} - само въведените; key: кодът -> ключ в склада.
    Връща {ключ на елемента: резултата от fit_to_stock}; без въведена наличност - празен речник.
    """
    if not available:
        return {}
    left = dict(available)
    order = sorted(range(len(elements)), key=lambda i: -panel_area_cm2(elements[i][1]))
    plan = {}
    for i in order:
        elem_key, layout, count = elements[i]
        result = fit_to_stock(layout, count, left, key)
        for k, q in _needs(result["layout"], count, key).items():
            if k in left:
                left[k] = max(0, left[k] - q)
        plan[elem_key] = result
    return plan
