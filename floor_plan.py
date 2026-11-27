"""
3D план на етажа (потребителят, 22.11.2026): елементите от един чертеж се подреждат с мишката в изглед отгоре
(приблизително - без точност) и се чертаят заедно в 3D - отделен PDF файл (А3, хоризонтално).

Мястото на всеки брой елемент: {"x", "y", "rot", "mir"} - центърът в см (y нагоре), завъртане в градуси обратно
на часовника (всякакъв ъгъл - и по диагонал), огледално (по x, преди завъртането). Реденето на панелите и сметките не се пипат - чертае се
разположението от layout_element() (или плана според склада).
"""
import heapq
import io

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.path import Path
from matplotlib.transforms import Affine2D

from drawing_generator import (_plan_geometry, _face_strips, PANEL_T, COLOR_3D_PANEL, COLOR_3D_COMPENSATOR,
                               COLOR_3D_CORNER, COLOR_3D_CORNER_IN, COLOR_3D_CONCRETE, COLOR_3D_EDGE, COLOR_BOARD,
                               TOP_PANEL, TOP_PANEL_BORDER, TOP_EX, TOP_IN, TOP_CONCRETE_BORDER)
from teko_calculator import face_row_pieces, is_compensator_row
from doc_lang import dt

SNAP_CM = 5          # местата прилепват през 5 см
ROW_WIDTH_CM = 3000  # подреждане по подразбиране - редове до 30 м
GAP_CM = 150         # разстояние между елементите при подреждането по подразбиране
VIEW_MAIN = (30, -60)     # 3D изглед: височина и посока на гледане (отпред вляво)
COLOR_CONCRETE_EDGE = '#6E6E70'
PLAN_CONCRETE = '#C9CDD2'
BG_ALPHA = 0.35       # чертежът (фонът) в PDF-а - бледо
BG_MARGIN_CM = 300    # от фона се взима частта около елементите и още толкова


# ---------- Геометрия на един елемент (локално, см) ----------

def _concrete_rects(poly):
    """Бетонът като правоъгълници (ивици по y): [(x0, y0, x1, y1)]."""
    core = Path(poly)
    ys = sorted({p[1] for p in poly})
    xs = sorted({p[0] for p in poly})
    rects = []
    for y0, y1 in zip(ys, ys[1:]):
        run = None
        for x0, x1 in zip(xs, xs[1:]):
            if core.contains_point(((x0 + x1) / 2, (y0 + y1) / 2)):
                run = (run[0], x1) if run else (x0, x1)
            elif run:
                rects.append((run[0], y0, run[1], y1))
                run = None
        if run:
            rects.append((run[0], y0, run[1], y1))
    return rects


def _rings(poly):
    """Контурите на бетона: един многоъгълник или пръстен (шахта - външният, после вътрешният; точката, с която
    контурът започва, се повтаря в края му)."""
    rings, cur = [], []
    for q in poly:
        if len(cur) > 2 and list(q) == list(cur[0]):
            rings.append(cur)
            cur = []
        else:
            cur.append(list(q))
    if cur:
        rings.append(cur)
    return rings


def _outer(piece):
    """Външният контур на бетона (при шахта - без дупката): за напасването и мащаба по контурите на чертежа."""
    return piece.get("rings", [piece["poly"]])[0]


def piece_plan(layout):
    """
    Изгледът отгоре за подреждането: бетонът (многоъгълник), кофражът ([x0, y0, x1, y1, вид] - "P" панели,
    "EX" / "IN" ъгли), центърът и размерите на целия елемент с кофража.
    """
    T = PANEL_T
    poly, place, corners = _plan_geometry(layout)
    forms = []
    for axis, a0, a1, c_lo, c_hi, _normal in _face_strips(layout, place, poly).values():
        forms.append([a0, c_lo, a1, c_hi, "P"] if axis == 'x' else [c_lo, a0, c_hi, a1, "P"])
    for kind, x, y in corners:
        forms.append([x, y, x + T, y + T, kind])
    xs = [p[0] for p in poly] + [f[0] for f in forms] + [f[2] for f in forms]
    ys = [p[1] for p in poly] + [f[1] for f in forms] + [f[3] for f in forms]
    return {"poly": [[float(x), float(y)] for x, y in poly],
            "rings": [[[float(x), float(y)] for x, y in ring] for ring in _rings(poly)],
            "forms": [[float(v) for v in f[:4]] + [f[4]] for f in forms],
            "cx": (min(xs) + max(xs)) / 2, "cy": (min(ys) + max(ys)) / 2,
            "w": max(xs) - min(xs), "h": max(ys) - min(ys)}


def piece_boxes(layout):
    """
    Кутиите за 3D (локално, см): (x0, y0, z0, x1, y1, z1, цвят, ос на парчетата, [(начало, край, цвят)]).
    Всеки ред панели на страна е една кутия, панелите в нея - парчета по оста (рисуват се с фугите).
    """
    T = PANEL_T
    poly, place, corners = _plan_geometry(layout)
    top = sum(layout["height_levels"])  # горен край на панелите
    boxes = []
    for face in layout["faces"]:
        x0, y0, axis, *rev = place[face["name"]]
        a0 = x0 if axis == 'x' else y0
        z = 0
        for h_val, row in zip(layout["height_levels"], face["rows"]):
            col = COLOR_3D_COMPENSATOR if is_compensator_row(h_val) else COLOR_3D_PANEL
            pieces = face_row_pieces(face, h_val, row)
            if rev and rev[0]:
                pieces = pieces[::-1]
            s, parts = 0, []
            for w_val, is_board, _panel_w in pieces:
                parts.append((a0 + s, a0 + s + w_val, COLOR_BOARD if is_board else col))
                s += w_val
            if axis == 'x':
                boxes.append((x0, y0, z, x0 + s, y0 + T, z + h_val, col, 'x', parts))
            else:
                boxes.append((x0, y0, z, x0 + T, y0 + s, z + h_val, col, 'y', parts))
            z += h_val
    for kind, x, y in corners:
        boxes.append((x, y, 0, x + T, y + T, top, COLOR_3D_CORNER if kind == "EX" else COLOR_3D_CORNER_IN, None, []))
    for x0, y0, x1, y1 in _concrete_rects(poly):
        boxes.append((x0, y0, 0, x1, y1, layout["height_cm"], COLOR_3D_CONCRETE, None, []))
    return boxes


# ---------- Място на етажа ----------

def _transform(piece, pos):
    """Матрицата 2x2 и преместването: локално (x, y) -> на етажа (огледално, завъртане около центъра)."""
    a = np.radians(float(pos.get("rot", 0) or 0))
    c, s = np.cos(a), np.sin(a)
    m = -1.0 if pos.get("mir") else 1.0
    M = np.array([[c * m, -s], [s * m, c]])
    return M, np.array([pos["x"], pos["y"]], float) - M @ np.array([piece["cx"], piece["cy"]], float)


def to_world(x, y, piece, pos):
    """Точка от елемента (локално) -> на етажа."""
    M, t = _transform(piece, pos)
    wx, wy = M @ np.array([x, y], float) + t
    return float(wx), float(wy)


def world_size(piece, pos):
    """Размерите на обхващащия правоъгълник на елемента на етажа (при завъртане под ъгъл - по-голям)."""
    a = np.radians(float(pos.get("rot", 0) or 0))
    c, s = abs(np.cos(a)), abs(np.sin(a))
    return round(c * piece["w"] + s * piece["h"], 6), round(s * piece["w"] + c * piece["h"], 6)


def default_positions(pieces, positions=None, top_cm=0.0, row_width_cm=ROW_WIDTH_CM):
    """
    Местата по подразбиране за елементите без място: един до друг на редове надолу от top_cm
    (под вече подредените, за да не се застъпват).
    """
    positions = dict(positions or {})
    placed = [p for p in pieces if p["id"] in positions]
    if placed:
        top_cm = min(top_cm, min(positions[p["id"]]["y"] - world_size(p, positions[p["id"]])[1] / 2
                                 for p in placed) - GAP_CM)
    x, y, row_h = 0.0, top_cm, 0.0
    for p in pieces:
        if p["id"] in positions:
            continue
        if x > 0 and x + p["w"] > row_width_cm:
            x, y, row_h = 0.0, y - row_h - GAP_CM, 0.0
        positions[p["id"]] = {"x": _snap(x + p["w"] / 2), "y": _snap(y - p["h"] / 2), "rot": 0, "mir": False}
        x += p["w"] + GAP_CM
        row_h = max(row_h, p["h"])
    return positions


def _snap(v):
    return round(v / SNAP_CM) * SNAP_CM


# ---------- Промени от плана (потребителят, 24.11.2026) ----------
# Изтриване, копиране, добавяне и промяна на елементи в таб 2 - направо в таблицата (вариант А). Всеки брой е
# (ред, k) - редът по позиция в таблицата, k - поредният брой (както floor_pieces() в app.py). Копие със същото име
# и размери е още един брой на реда; променен брой - нов ред (или към ред, с който вече е еднакъв).
def apply_floor_edit(df, action, signature):
    """
    Една промяна от плана върху таблицата. action: {"a": "delete" | "copy" | "edit" | "add", ...}:
    delete / copy - "row", "k"; edit - "row", "k", "values", "all" (за всички бройки на реда); add - "values"
    (с "drawing"), "count". signature(ред като dict) - еднакви елементи: (чертеж, тип, име, размери ...),
    чертежът е първи.
    Връща (новата таблица, {(стар ред, k): (нов ред, k)}, [(нов ред, k) на новите бройки]).
    """
    import pandas as pd
    df = df.reset_index(drop=True)
    rows = []
    for r, row in enumerate(df.to_dict("records")):
        n = pd.to_numeric(row.get("count"), errors="coerce")
        rows.append({"data": row, "tokens": [(r, k) for k in range(int(n) if pd.notna(n) else 1)]})

    def same_as(data, skip):
        if group_of(data):   # частите на обединен елемент - всяка на свой ред (свое място в плана)
            return None
        key = signature(data)
        return next((x for x in rows if x is not skip and signature(x["data"]) == key), None)

    a = action["a"]
    if a in ("delete", "copy", "edit"):
        own = rows[action["row"]]
        token = (action["row"], action.get("k", 0))
    if a == "delete":
        own["tokens"].remove(token)
    elif a == "copy":
        own["tokens"].append("new")
    elif a == "edit":
        if action.get("all") or len(own["tokens"]) == 1:   # целият ред
            own["data"] = {**own["data"], **action["values"]}
            other = same_as(own["data"], own)
            if other is not None:
                other["tokens"] += own["tokens"]
                own["tokens"] = []
        else:   # само тази бройка - нов ред до стария (или към еднакъв ред)
            own["tokens"].remove(token)
            data = {**own["data"], **action["values"]}
            other = same_as(data, own)
            if other is not None:
                other["tokens"].append(token)
            else:
                rows.insert(rows.index(own) + 1, {"data": data, "tokens": [token]})
    elif a == "add":
        data = {**{col: None for col in df.columns}, **action["values"]}
        other = same_as(data, None)
        new = ["new"] * int(action.get("count", 1) or 1)
        if other is not None:
            other["tokens"] += new
        else:   # в края на своя чертеж (чертежите са един след друг)
            drawing = signature(data)[0]
            last = max((i for i, x in enumerate(rows) if signature(x["data"])[0] == drawing), default=len(rows) - 1)
            rows.insert(last + 1, {"data": data, "tokens": new})
    return _rows_to_df(df, rows)


def _rows_to_df(df, rows):
    """Редовете с бройките -> (новата таблица, {(стар ред, k): (нов ред, k)}, [(нов ред, k) на новите бройки])."""
    import pandas as pd
    rows = [x for x in rows if x["tokens"]]
    moves, added = {}, []
    for i, x in enumerate(rows):
        x["data"]["count"] = len(x["tokens"])
        for k, tok in enumerate(x["tokens"]):
            if tok == "new":
                added.append((i, k))
            else:
                moves[tok] = (i, k)
    columns = list(df.columns) + [c for x in rows for c in x["data"] if c not in df.columns]
    new_df = pd.DataFrame([x["data"] for x in rows], columns=list(dict.fromkeys(columns)))
    return new_df, moves, added


# ---------- Обединени елементи (потребителят, 27.11.2026) ----------
# Няколко елемента от плана - един „Обединен елемент <име>“ навсякъде (табове 3-5, PDF, Excel). Частите остават
# отделни редове (1 бр.) и се редят по алгоритъма; колоната group - името, group_pos - мястото в плана (JSON).
GROUP_COLUMNS = ("group", "group_pos")
# краищата на всеки тип: (колона, ръбът на бетона - poly[i] -> poly[i + 1] от _plan_geometry)
END_EDGES = {"wall": (("closed_end_1", 1), ("closed_end_2", 3)),
             "l_wall": (("closed_end_1", 1), ("closed_end_2", 4)),
             "u_wall": (("closed_end_1", 6), ("closed_end_2", 2)),
             "t_wall": (("closed_end_1", 5), ("closed_end_2", 7), ("closed_end_3", 2))}
TOUCH_CM = 2 * PANEL_T + 5   # краят опира в друг елемент: бетонът му е до толкова пред челото (кофражът между тях)


def group_of(data):
    """Името на обединения елемент на реда („“ - не е обединен)."""
    value = data.get("group") if hasattr(data, "get") else None
    return value.strip() if isinstance(value, str) else ""


def touching_ends(pieces, positions):
    """
    Краищата, които опират в друг от елементите (бетонът на другия е до TOUCH_CM пред челото):
    [(id, колона на края, id на другия)]. Само по плана - затворен или отворен е краят, не се гледа.
    """
    shapes = {p["id"]: Path(np.array([to_world(x, y, p, positions[p["id"]]) for x, y in _outer(p)]))
              for p in pieces}
    found = []
    for p in pieces:
        poly = np.array(p["poly"], float)
        own = Path(poly)
        for col, i in END_EDGES.get(p.get("type"), ()):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            mid, d = (a + b) / 2, (b - a) / max(np.hypot(*(b - a)), 1e-9)
            n = np.array([d[1], -d[0]])
            if own.contains_point(mid + n):   # навън - страната без бетон
                n = -n
            for q in pieces:
                if q["id"] == p["id"]:
                    continue
                if any(shapes[q["id"]].contains_point(to_world(*(mid + n * s), p, positions[p["id"]]))
                       for s in np.arange(1, TOUCH_CM + 1, 2)):
                    found.append((p["id"], col, q["id"]))
                    break
    return found


def keep_concrete(pos, old, new):
    """
    Мястото на елемента след смяна на кофража (отворен край - без чело и EX): центърът е на целия елемент с
    кофража, затова се мести така, че бетонът да остане на същото място.
    """
    M, _t = _transform(old, pos)
    d = M @ np.array([new["cx"] - old["cx"], new["cy"] - old["cy"]], float)
    return {**pos, "x": float(pos["x"] + d[0]), "y": float(pos["y"] + d[1])}


def apply_floor_group(df, changes, signature):
    """
    Обединяване / разделяне: changes {(ред, k): стойности} - всяка бройка става свой ред (1 бр.) с новите стойности
    (group, group_pos, отворени краища). Частите на една група - една след друга, на мястото на първата; разделените
    се сливат с еднакъв ред без група (както при промяна от плана). Връща същото като apply_floor_edit.
    """
    import pandas as pd
    df = df.reset_index(drop=True)
    rows = []
    for r, row in enumerate(df.to_dict("records")):
        n = pd.to_numeric(row.get("count"), errors="coerce")
        rows.append({"data": row, "tokens": [(r, k) for k in range(int(n) if pd.notna(n) else 1)]})
    first = list(rows)
    for (r, k), values in changes.items():
        own = first[r]
        data = {**own["data"], **values}
        if len(own["tokens"]) == 1:
            own["data"], target = data, own
        else:   # този брой - нов ред до стария
            own["tokens"].remove((r, k))
            target = {"data": data, "tokens": [(r, k)]}
            rows.insert(rows.index(own) + 1, target)
        if not group_of(data):
            key = signature(data)
            other = next((x for x in rows if x is not target and x["tokens"] and not group_of(x["data"])
                          and signature(x["data"]) == key), None)
            if other is not None:
                other["tokens"] += target["tokens"]
                target["tokens"] = []
    ordered, seen = [], set()
    for x in rows:   # частите на групата - след първата ѝ част
        g = group_of(x["data"])
        if id(x) in seen:
            continue
        for y in [x] if not g else [y for y in rows if group_of(y["data"]) == g]:
            ordered.append(y)
            seen.add(id(y))
    return _rows_to_df(df, ordered)


# ---------- Местата от чертежа (потребителят, 24.11.2026) ----------
# Вариант 3: контурът на всеки брой от Gemini ("places", приблизително) и контурите на бетона от векторния PDF
# (точно); контур от PDF-а се взима, когато е до контура от Gemini или до надпис с името на елемента.
# Елементът се напасва върху контура (завъртане, огледално) - реденето на панелите не се пипа.
FIT_MIN_IOU = 0.5     # контур от PDF-а: елементът трябва да пасва по форма (застъпване поне толкова)
SNAP_ANGLE_DEG = 3    # до толкова от 0 / 90 / 180 / 270° - точно на правия ъгъл
_LOOKALIKE = str.maketrans("ABCEHKMOPTXY", "АВСЕНКМОРТХУ")


def name_key(name):
    """Името за сравнение с надписите на чертежа: главни, латиница -> кирилица (K / К), без интервали и точки."""
    text = str(name or "").upper().translate(_LOOKALIKE)
    return "".join(ch for ch in text if ch not in " .-_")


def _area(poly):
    x, y = np.asarray(poly, float).T
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _centroid(poly):
    """Центърът на тежестта на многоъгълника (при нулева площ - средното на точките)."""
    x, y = np.asarray(poly, float).T
    cross = x * np.roll(y, -1) - np.roll(x, -1) * y
    a = cross.sum() / 2
    if abs(a) < 1e-9:
        return np.array([x.mean(), y.mean()])
    return np.array([((x + np.roll(x, -1)) * cross).sum(), ((y + np.roll(y, -1)) * cross).sum()]) / (6 * a)


def _iou(a, b, n=48):
    """Застъпването на два многоъгълника (сечение / обединение) - по мрежа от точки."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    lo, hi = np.minimum(a.min(0), b.min(0)), np.maximum(a.max(0), b.max(0))
    if np.any(hi - lo <= 0):
        return 0.0
    # точките - вътре в клетките (не по ръбовете: точка точно на ръба зависи от посоката на обхождане)
    k = (np.arange(n) + 0.4137) / n
    gx, gy = np.meshgrid(lo[0] + k * (hi[0] - lo[0]), lo[1] + k * (hi[1] - lo[1]))
    pts = np.column_stack([gx.ravel(), gy.ravel()])
    ina, inb = Path(a).contains_points(pts), Path(b).contains_points(pts)
    union = np.count_nonzero(ina | inb)
    return np.count_nonzero(ina & inb) / union if union else 0.0


def _main_angle(poly):
    """Посоката на най-дългата страна на контура, 0-90°."""
    p = np.asarray(poly, float)
    d = np.roll(p, -1, axis=0) - p
    i = int(np.argmax(np.hypot(d[:, 0], d[:, 1])))
    return float(np.degrees(np.arctan2(d[i, 1], d[i, 0]))) % 90


def fit_piece(piece, outline):
    """
    Мястото, на което бетонът на елемента пасва най-добре върху контура (см на етажа): завъртане по
    най-дългата страна на контура (+ 0 / 90 / 180 / 270°) и огледално; центърът на тежестта - върху центъра
    на контура. (място, застъпване 0-1).
    """
    P, T = np.array(_outer(piece), float), np.asarray(outline, float)
    cP, cT = _centroid(P), _centroid(T)
    c = np.array([piece["cx"], piece["cy"]], float)
    base, best = _main_angle(T), None
    for k in range(4):
        rot = (base + 90 * k) % 360
        near = round(rot / 90) * 90
        rot = float(near % 360) if abs(rot - near) <= SNAP_ANGLE_DEG else float(round(rot) % 360)
        for mir in (False, True):
            pos = {"x": 0.0, "y": 0.0, "rot": rot, "mir": mir}
            M, _t = _transform(piece, pos)
            iou = _iou((M @ (P - cP).T).T + cT, T)
            if best is None or iou > best[1] + 0.02:   # при равенство (симетрична форма) - без огледално, по-малък ъгъл
                x, y = cT + M @ (c - cP)
                best = ({"x": round(float(x), 1), "y": round(float(y), 1), "rot": rot, "mir": mir}, iou)
    return best


def pdf_shapes(page, pt_per_px):
    """
    Векторен PDF: затворените контури (бетонът на чертежа) и надписите - в пиксели на фона (страницата,
    завъртяна както се показва). Контур = правоъгълник / четириъгълник в PDF-а или затворена верига от линии с
    една дебелина, в която всяка точка е край на точно две линии (щриховката е с друга дебелина, а кóтите не
    образуват затворени вериги). (контури [[x, y], ...], надписи [(текст, x, y)]).
    """
    import fitz
    R = page.rotation_matrix

    def px(p):
        q = p * R
        return q.x / pt_per_px, q.y / pt_per_px

    rings, edges = [], {}   # edges - линиите по дебелина
    for g in page.get_drawings():
        for item in g["items"]:
            if item[0] == "l":
                edges.setdefault(round(g.get("width") or 0, 2), []).append((item[1], item[2]))
            elif item[0] in ("re", "qu"):
                q = item[1].quad if item[0] == "re" else item[1]
                rings.append([q.ul, q.ur, q.lr, q.ll])
    node = lambda p: (round(p.x * 2), round(p.y * 2))   # точките до 0,5 pt са една
    for lines in edges.values():
        adj, where, done = {}, {}, set()
        for a, b in lines:
            na, nb = node(a), node(b)
            if na == nb:
                continue
            adj.setdefault(na, set()).add(nb)
            adj.setdefault(nb, set()).add(na)
            where.setdefault(na, a)
            where.setdefault(nb, b)
        for start in adj:
            if start in done:
                continue
            comp, stack = [], [start]   # свързаната част
            done.add(start)
            while stack:
                n = stack.pop()
                comp.append(n)
                for m in adj[n]:
                    if m not in done:
                        done.add(m)
                        stack.append(m)
            if len(comp) < 3 or any(len(adj[n]) != 2 for n in comp):
                continue
            ring, prev, cur = [start], None, start   # обхождане на веригата
            while True:
                nxt = next(m for m in adj[cur] if m != prev) if prev is not None else next(iter(adj[cur]))
                if nxt == start:
                    break
                ring.append(nxt)
                prev, cur = cur, nxt
            rings.append([where[n] for n in ring])

    shapes, seen = [], set()
    w_px, h_px = page.rect.width / pt_per_px, page.rect.height / pt_per_px
    for ring in rings:
        pts = np.array([px(p) for p in ring])
        u, v = pts - np.roll(pts, 1, axis=0), np.roll(pts, -1, axis=0) - pts
        turn = np.abs(u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0])
        keep = np.flatnonzero(turn > 1e-6 * max(1.0, np.ptp(pts[:, 0]) * np.ptp(pts[:, 1])))   # без точките по права
        pts = pts[keep] if len(keep) >= 3 else pts
        size = np.ptp(pts, axis=0)
        if (len(pts) > 12 or size.min() < 1.5 or size[0] > w_px / 2 or size[1] > h_px / 2
                or _area(pts) < 0.5 * size.prod() * (len(pts) <= 4)):
            continue   # кръгчета, рамки на листа и таблици, изкривени четириъгълници
        sig = (tuple(np.round(pts.min(0))), tuple(np.round(pts.max(0))), round(_area(pts)))
        if sig not in seen:   # един контур, начертан два пъти
            seen.add(sig)
            shapes.append(pts.tolist())
    labels = []
    for x0, y0, x1, y1, text, *_ in page.get_text("words"):
        if any(ch.isalpha() for ch in text) and len(text) <= 15:
            cx, cy = px(fitz.Point((x0 + x1) / 2, (y0 + y1) / 2))
            labels.append((text, cx, cy))
    return shapes, labels


def gemini_outlines(elements, page, w_px, h_px):
    """
    Контурите от Gemini ("places") на страницата - в пиксели на фона, по (тип, име): {(тип, name_key): [контур]}.
    elements: [{"type", "name", "places"}] - в реда на разчитането.
    """
    out = {}
    for e in elements or []:
        for place in e.get("places") or []:
            try:
                if int(place.get("page") or 1) != page:
                    continue
                pts = [(float(x) / 1000 * w_px, float(y) / 1000 * h_px) for x, y in place["outline"]]
            except (TypeError, ValueError, KeyError, AttributeError):
                continue
            if len(pts) >= 3 and _area(pts) > 0:
                out.setdefault((e.get("type"), name_key(e.get("name"))), []).append(pts)
    return out


def _bbox_dist(pt, poly):
    lo, hi = np.min(poly, 0), np.max(poly, 0)
    d = np.maximum(np.maximum(lo - pt, pt - hi), 0)
    return float(np.hypot(*d))


def drawing_places(pieces, w_px, h_px, cm_per_px, gemini=None, shapes=(), labels=()):
    """
    Местата на елементите по чертежа (фонът: w_px x h_px пиксела, cm_per_px см на пиксел).
    1. Контур от Gemini -> най-близкият контур от PDF-а със сходна големина (или с надписа на елемента до него);
       няма такъв - контурът от Gemini.
    2. Без контур от Gemini - контурът от PDF-а до надпис с името на елемента.
    Контурът от PDF-а важи само ако елементът пасва в него по форма (FIT_MIN_IOU).
    (места {id: място}, откъде {id: "pdf" / "gemini"}, мащаб по контурите от PDF-а - см на пиксел или None).
    """
    gemini = gemini or {}
    shapes = [np.asarray(s, float) for s in shapes]
    cents = [_centroid(s) for s in shapes]
    areas = [_area(s) for s in shapes]
    diag = float(np.hypot(w_px, h_px))
    by_key = {}
    for p in pieces:
        by_key.setdefault((p.get("type"), name_key(p.get("name"))), []).append(p)
    names = {}   # надписите по име
    for text, x, y in labels:
        names.setdefault(name_key(text), []).append(np.array([x, y]))

    def labelled(shape_i, key):
        lim = 1.2 * float(np.ptp(shapes[shape_i], axis=0).max()) + 0.012 * diag
        return any(_bbox_dist(pt, shapes[shape_i]) <= lim for pt in names.get(key[1], []))

    pairs, approx = [], {}   # (оценка, id, контур от PDF-а)
    for key, outs in gemini.items():
        for p, g in zip(by_key.get(key, []), outs):
            g = np.asarray(g, float)
            approx[p["id"]] = g
            cg, ag = _centroid(g), _area(g)
            reach = max(float(np.hypot(*np.ptp(g, axis=0))), 0.03 * diag)
            for i, (cs, a) in enumerate(zip(cents, areas)):
                d = float(np.hypot(*(cs - cg)))
                if d <= reach and 0.2 <= a / ag <= 5:
                    pairs.append((_iou(g, shapes[i]) + 0.5 * (1 - d / reach) + (0.5 if labelled(i, key) else 0),
                                  p["id"], i))
    for key, group in by_key.items():   # без Gemini - по надписа
        free = [p for p in group if p["id"] not in approx]
        if not free or not key[1]:
            continue
        for i, s in enumerate(shapes):
            pts = names.get(key[1], [])
            if not pts:
                break
            lim = 1.2 * float(np.ptp(s, axis=0).max()) + 0.012 * diag
            d = min(_bbox_dist(pt, s) for pt in pts)
            if d <= lim:
                for p in free:
                    pairs.append((1 - d / lim, p["id"], i))
    pairs.sort(key=lambda x: -x[0])
    chosen, used = {}, set()
    for _score, pid, i in pairs:
        if pid not in chosen and i not in used:
            chosen[pid], used = i, used | {i}

    by_id = {p["id"]: p for p in pieces}
    ratios = [np.sqrt(_area(_outer(by_id[pid])) / areas[i]) for pid, i in chosen.items() if areas[i] > 0]
    scale = float(np.median(ratios)) if ratios else None
    if scale is None and approx:   # само Gemini - приблизително
        ratios = [np.sqrt(_area(_outer(by_id[pid])) / _area(g)) for pid, g in approx.items() if _area(g) > 0]
        scale = float(np.median(ratios)) if ratios else None

    to_cm = lambda poly: np.column_stack([poly[:, 0] * cm_per_px, (h_px - poly[:, 1]) * cm_per_px])
    positions, how = {}, {}
    for p in pieces:
        pid = p["id"]
        if pid in chosen:
            pos, iou = fit_piece(p, to_cm(shapes[chosen[pid]]))
            if iou >= FIT_MIN_IOU:
                positions[pid], how[pid] = pos, "pdf"
                continue
        if pid in approx:
            positions[pid], how[pid] = fit_piece(p, to_cm(approx[pid]))[0], "gemini"
    return positions, how, scale


# ---------- 3D изглед на етажа ----------

def _world_boxes(pieces, positions):
    """
    Кутиите на всички елементи на етажа. Елемент, завъртян под ъгъл, има кутии под ъгъл - затова всяка кутия
    е с правоъгълника си в елемента (локално), основата си на етажа (4 ъгъла) и преобразуването M, t.
    """
    out = []
    for p in pieces:
        M, t = _transform(p, positions[p["id"]])
        for x0, y0, z0, x1, y1, z1, col, axis, parts in p["boxes"]:
            foot = (M @ np.array([[x0, x1, x1, x0], [y0, y0, y1, y1]], float)).T + t
            out.append({"rect": (x0, y0, x1, y1), "z": (z0, z1), "col": col, "axis": axis, "parts": parts,
                        "M": M, "t": t, "foot": foot})
    return out


def _draw_order(boxes, eye, right, up):
    """
    Ред на рисуване отзад напред. Кутиите са изправени призми с правоъгълна основа (под всякакъв ъгъл) и не
    се пресичат - две, които се застъпват на екрана, се разделят от равнина: хоризонтална (едната е над
    другата) или вертикална по страна на някоя от основите. Кутията от страната към гледащия се рисува после.
    """
    n = len(boxes)
    foot = np.array([b["foot"] for b in boxes])                       # (n, 4, 2)
    z0 = np.array([b["z"][0] for b in boxes], float)
    z1 = np.array([b["z"][1] for b in boxes], float)
    pts = np.concatenate([np.concatenate([foot, np.repeat(z0[:, None, None], 4, 1)], 2),
                          np.concatenate([foot, np.repeat(z1[:, None, None], 4, 1)], 2)], 1)   # (n, 8, 3)
    u, v = pts @ right, pts @ up
    umin, umax, vmin, vmax = u.min(1), u.max(1), v.min(1), v.max(1)
    overlap = ((umin[:, None] < umax[None, :] - 1e-6) & (umin[None, :] < umax[:, None] - 1e-6)
               & (vmin[:, None] < vmax[None, :] - 1e-6) & (vmin[None, :] < vmax[:, None] - 1e-6))
    ii, jj = np.nonzero(np.triu(overlap, 1))
    edges = np.zeros((n, n), bool)
    if len(ii):
        axes = np.array([b["M"].T for b in boxes])                    # (n, 2, 2): двете оси на основата
        A = np.concatenate([axes[ii], axes[jj]], 1)                   # (P, 4, 2)
        pi = np.einsum('pkd,pcd->pkc', A, foot[ii])
        pj = np.einsum('pkd,pcd->pkc', A, foot[jj])
        neg = pi.max(2) <= pj.min(2) + 1e-6       # i е от отрицателната страна на оста
        pos = pj.max(2) <= pi.min(2) + 1e-6
        ne = A @ eye[:2]                          # (P, 4): накъде е гледащият по оста
        i_behind = ((neg & (ne > 1e-9)) | (pos & (ne < -1e-9))).any(1)
        j_behind = ((neg & (ne < -1e-9)) | (pos & (ne > 1e-9))).any(1)
        if eye[2] > 0:
            i_behind |= z1[ii] <= z0[jj] + 1e-6
            j_behind |= z1[jj] <= z0[ii] + 1e-6
        edges[ii[i_behind & ~j_behind], jj[i_behind & ~j_behind]] = True
        edges[jj[j_behind & ~i_behind], ii[j_behind & ~i_behind]] = True
    centers = np.column_stack([foot.mean(1), (z0 + z1) / 2])
    depth = centers @ eye
    indeg = edges.sum(0)
    ready = [(depth[i], i) for i in range(n) if indeg[i] == 0]
    heapq.heapify(ready)
    order, done = [], np.zeros(n, bool)
    while ready:
        _d, i = heapq.heappop(ready)
        order.append(i)
        done[i] = True
        for j in np.nonzero(edges[i])[0]:
            indeg[j] -= 1
            if indeg[j] == 0:
                heapq.heappush(ready, (depth[j], j))
    order += sorted(np.nonzero(~done)[0].tolist(), key=lambda i: depth[i])  # при цикъл - по дълбочина
    return order


def _box_quads(b, eye):
    """Видимите стени на кутията (четириъгълници на етажа, с цвета): страните към гледащия и горната."""
    M, t = b["M"], b["t"]
    x0, y0, x1, y1 = b["rect"]
    z0, z1 = b["z"]
    parts = b["parts"] if b["axis"] else []

    def w(x, y, z):
        xy = M @ np.array([x, y], float) + t
        return [xy[0], xy[1], z]

    quads = []
    sides = [((x0, y0), (x1, y0), (0, -1), 'x'), ((x1, y0), (x1, y1), (1, 0), 'y'),
             ((x1, y1), (x0, y1), (0, 1), 'x'), ((x0, y1), (x0, y0), (-1, 0), 'y')]
    for a, c, normal, along in sides:
        if (M @ np.array(normal, float)) @ eye[:2] <= 1e-9:
            continue
        if parts and b["axis"] == along:   # панелите по стената - с фугите и своя цвят
            for s0, s1, col in parts:
                pa, pc = ((s0, a[1]), (s1, a[1])) if along == 'x' else ((a[0], s0), (a[0], s1))
                quads.append(([w(*pa, z0), w(*pc, z0), w(*pc, z1), w(*pa, z1)], col))
        else:
            quads.append(([w(*a, z0), w(*c, z0), w(*c, z1), w(*a, z1)], b["col"]))
    if eye[2] > 0:
        rects = ([(s0, y0, s1, y1, col) if b["axis"] == 'x' else (x0, s0, x1, s1, col) for s0, s1, col in parts]
                 if parts else [(x0, y0, x1, y1, b["col"])])
        for rx0, ry0, rx1, ry1, col in rects:
            quads.append(([w(rx0, ry0, z1), w(rx1, ry0, z1), w(rx1, ry1, z1), w(rx0, ry1, z1)], col))
    return quads


def _background_crop(background, pieces, positions, margin_cm=BG_MARGIN_CM):
    """
    Частта от чертежа (фона) около елементите: (масив на картината, (x0, x1, y0, y1) в см на етажа) или None.
    Фонът е от (0, 0) до (ширина, височина) в см - както в подреждането.
    """
    if not background or not pieces:
        return None
    img, k = background["image"], background["cm_per_px"]
    xs, ys = [], []
    for p in pieces:
        M, t = _transform(p, positions[p["id"]])
        pts = (M @ np.array(p["poly"], float).T).T + t
        xs += [pts[:, 0].min(), pts[:, 0].max()]
        ys += [pts[:, 1].min(), pts[:, 1].max()]
    h_cm = img.height * k
    c0 = max(0, int((min(xs) - margin_cm) / k))
    c1 = min(img.width, int(np.ceil((max(xs) + margin_cm) / k)))
    r0 = max(0, int((h_cm - max(ys) - margin_cm) / k))
    r1 = min(img.height, int(np.ceil((h_cm - min(ys) + margin_cm) / k)))
    if c1 - c0 < 2 or r1 - r0 < 2:
        return None
    crop = np.asarray(img.convert("L").crop((c0, r0, c1, r1)))
    return crop, (c0 * k, c1 * k, h_cm - r1 * k, h_cm - r0 * k)


def draw_floor_3d(ax, pieces, positions, view=VIEW_MAIN, labels=True, label_size=7, background=None):
    """3D изглед на етажа в 2D оста ax (успоредна проекция, рисуване отзад напред); фонът - бледо на пода."""
    elev, azim = np.radians(view[0]), np.radians(view[1])
    eye = np.array([np.cos(elev) * np.cos(azim), np.cos(elev) * np.sin(azim), np.sin(elev)])
    right = np.array([-np.sin(azim), np.cos(azim), 0.0])
    up = np.cross(eye, right)
    boxes = _world_boxes(pieces, positions)
    if not boxes:
        ax.axis('off')
        return
    polys, faces, edges, widths = [], [], [], []
    for i in _draw_order(boxes, eye, right, up):
        for quad, col in _box_quads(boxes[i], eye):
            pts = np.array(quad)
            polys.append(np.column_stack([pts @ right, pts @ up]))
            faces.append(col)
            concrete = col == COLOR_3D_CONCRETE
            edges.append(COLOR_CONCRETE_EDGE if concrete else COLOR_3D_EDGE)
            widths.append(0.15 if concrete else 0.25)
    ax.add_collection(PolyCollection(polys, facecolors=faces, edgecolors=edges, linewidths=widths, zorder=2))
    allp = np.vstack(polys)

    crop = _background_crop(background, pieces, positions)
    if crop is not None:  # чертежът на пода (z = 0): (x, y) -> (x, y, 0) @ (right, up)
        arr, (bx0, bx1, by0, by1) = crop
        im = ax.imshow(arr, cmap='gray', vmin=0, vmax=255, extent=(bx0, bx1, by0, by1), origin='upper',
                       alpha=BG_ALPHA, interpolation='bilinear', zorder=1)
        im.set_transform(Affine2D.from_values(right[0], up[0], right[1], up[1], 0, 0) + ax.transData)
        corners = np.array([[bx0, by0, 0], [bx1, by0, 0], [bx1, by1, 0], [bx0, by1, 0]])
        allp = np.vstack([allp, np.column_stack([corners @ right, corners @ up])])

    pad = 0.03 * max(np.ptp(allp[:, 0]), np.ptp(allp[:, 1]), 1)
    ax.set_xlim(allp[:, 0].min() - pad, allp[:, 0].max() + pad)
    ax.set_ylim(allp[:, 1].min() - pad, allp[:, 1].max() + pad)
    ax.set_aspect('equal')
    ax.axis('off')
    if labels:
        for p in pieces:
            pos = positions[p["id"]]
            top = max(b[5] for b in p["boxes"])
            pt = np.array([pos["x"], pos["y"], top + 40])
            ax.text(pt @ right, pt @ up, p["label"], ha='center', va='bottom', fontsize=label_size,
                    fontweight='bold', color='#111111', zorder=5,
                    bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.75))


def draw_floor_plan(ax, pieces, positions, label_size=6, background=None):
    """Изгледът отгоре на етажа: бетонът и кофражът на местата им, имената в средата; фонът - бледо отдолу."""
    colors = {"P": (TOP_PANEL, TOP_PANEL_BORDER), "EX": (TOP_EX, TOP_PANEL_BORDER), "IN": (TOP_IN, TOP_PANEL_BORDER)}
    xs, ys = [], []
    for p in pieces:
        pos = positions[p["id"]]
        M, t = _transform(p, pos)
        pts = (M @ np.array(p["poly"], float).T).T + t
        ax.add_patch(plt.Polygon(pts, closed=True, fc=PLAN_CONCRETE, ec='none', zorder=2))
        for ring in p.get("rings", [p["poly"]]):   # контурът - по пръстените (шахта - без линия между тях)
            ring_pts = (M @ np.array(ring, float).T).T + t
            ax.add_patch(plt.Polygon(ring_pts, closed=True, fill=False, ec=TOP_CONCRETE_BORDER, lw=0.4, zorder=2))
        for x0, y0, x1, y1, kind in p["forms"]:
            quad = (M @ np.array([[x0, x1, x1, x0], [y0, y0, y1, y1]], float)).T + t
            fc, ec = colors.get(kind, colors["P"])
            ax.add_patch(plt.Polygon(quad, closed=True, fc=fc, ec=ec, lw=0.2, zorder=2))
            xs += list(quad[:, 0])
            ys += list(quad[:, 1])
        ax.text(pos["x"], pos["y"], p["label"], ha='center', va='center', fontsize=label_size, color='#111111',
                zorder=5, bbox=dict(boxstyle='round,pad=0.1', fc='white', ec='none', alpha=0.7))
    crop = _background_crop(background, pieces, positions)
    if crop is not None:
        arr, extent = crop
        ax.imshow(arr, cmap='gray', vmin=0, vmax=255, extent=extent, origin='upper', alpha=BG_ALPHA,
                  interpolation='bilinear', zorder=1)
        xs += [extent[0], extent[1]]
        ys += [extent[2], extent[3]]
    if xs:
        pad = 0.04 * max(max(xs) - min(xs), max(ys) - min(ys), 1)
        ax.set_xlim(min(xs) - pad, max(xs) + pad)
        ax.set_ylim(min(ys) - pad, max(ys) + pad)
    ax.set_aspect('equal')
    ax.axis('off')


def group_view_pngs(pieces, positions, dpi=200):
    """Обединен елемент в PDF-а с чертежите: изгледът отгоре и 3D изгледът на частите на местата им (PNG буфери)."""
    bufs = []
    for draw in (lambda ax: draw_floor_plan(ax, pieces, positions, label_size=7),
                 lambda ax: draw_floor_3d(ax, pieces, positions, VIEW_MAIN, label_size=7)):
        fig, ax = plt.subplots(figsize=(6, 6))
        draw(ax)
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        bufs.append(buf)
    return bufs


def generate_floor_pdf(pieces, positions, info, background=None):
    """
    PDF (А3, хоризонтално): 3D изглед и изглед отгоре.
    info: {"project", "client", "drawing", "date"}; текстовете - на езика на документа (dt).
    background: {"image": PIL картина, "cm_per_px"} - чертежът, бледо под елементите (по желание).
    """
    fig = plt.figure(figsize=(16.54, 11.69))
    head = dt("3D план на етажа")
    if info.get("drawing"):
        head += " - " + dt("Чертеж: {name}", name=info["drawing"])
    fig.text(0.02, 0.965, head, fontsize=18, fontweight='bold', va='top')
    sub = [dt("Обект:") + " " + str(info.get("project", "")), dt("Клиент:") + " " + str(info.get("client", ""))]
    if info.get("date"):
        sub.append(dt("Дата: ") + str(info["date"]))
    fig.text(0.02, 0.925, "     ".join(sub), fontsize=10, va='top', color='#333333')
    fig.text(0.98, 0.965, dt("КОФРАЖНА СИСТЕМА TEKO / TEKO FORMWORK SYSTEM"), fontsize=10, ha='right', va='top',
             color='#555555')

    # един 3D изглед и изгледът отгоре (вторият 3D изглед от другия ъгъл - махнат, потребителят 22.11.2026);
    # потребителят, 24.11.2026 (`reference/screenshots/32. Разпределение 3Д.png`): изгледът отгоре - горе вдясно,
    # 3D изгледът - на целия лист под заглавието (ъгълът - VIEW_MAIN, без промяна)
    ax_top = fig.add_axes([0.61, 0.59, 0.38, 0.31])
    draw_floor_plan(ax_top, pieces, positions, label_size=6, background=background)
    ax_top.set_title(dt("TOP VIEW / ИЗГЛЕД ОТГОРЕ"), fontsize=9, loc='left')
    ax_top.set_anchor('NE')

    ax_main = fig.add_axes([0.01, 0.01, 0.98, 0.86])
    draw_floor_3d(ax_main, pieces, positions, VIEW_MAIN, label_size=8, background=background)
    ax_main.set_anchor('SW')   # излишната ширина - вдясно, под изгледа отгоре
    ax_main.text(0.01, 0.99, dt("3D VIEW / 3D ИЗГЛЕД"), transform=ax_main.transAxes, fontsize=10, va='top')
    ax_main.set_zorder(0)
    ax_top.set_zorder(1)   # изгледът отгоре - над 3D изгледа

    buf = io.BytesIO()
    fig.savefig(buf, format='pdf', dpi=200)
    plt.close(fig)
    return buf.getvalue()


# ---------- Подреждане с мишката (компонент на Streamlit) ----------

FLOOR_CSS = """
.fp-root { font-family: var(--st-font, sans-serif); outline: none; }
.fp-wrap { position: relative; }
.fp-bar { position: absolute; top: 8px; left: 8px; right: 8px; z-index: 2; display: flex; flex-wrap: wrap; gap: 6px;
          align-items: center; padding: 6px 8px; background: rgba(255, 255, 255, 0.92);
          border: 1px solid #dde1e6; border-radius: 8px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08); }
.fp-bar button { border: 1px solid #c9ccd1; background: #fff; border-radius: 6px; padding: 4px 10px;
                 cursor: pointer; font-size: 13px; }
.fp-bar button:hover { border-color: #ff4b4b; }
.fp-bar button.on { background: #ffe9a8; border-color: #e0a800; }
.fp-bar button:disabled { opacity: 0.45; cursor: default; }
.fp-bar label { font-size: 13px; display: flex; align-items: center; gap: 4px; }
.fp-bar input { width: 70px; padding: 3px 6px; border: 1px solid #c9ccd1; border-radius: 6px; font-size: 13px; }
.fp-hint { font-size: 12px; color: #555; margin-left: 4px; }
.fp-sep { width: 1px; align-self: stretch; background: #c9ccd1; margin: 0 2px; }
.fp-svg { width: 100%; height: 680px; background: #fbfcfd; border: 1px solid #dde1e6; border-radius: 6px;
          touch-action: none; user-select: none; display: block; }
.fp-piece { cursor: grab; }
/* бетонът - само контур, чертежът се вижда отвътре (потребителят, 25.11.2026); хваща се и за вътрешността */
.fp-piece .c { fill: transparent; stroke: #2c3e50; pointer-events: all; }
.fp-piece .P { fill: #e5bec0; stroke: #3a2e36; }
.fp-piece .EX { fill: #a0d784; stroke: #3a2e36; }
.fp-piece .IN { fill: #4a8f42; stroke: #3a2e36; }
.fp-piece.sel .c { fill: transparent; stroke: #1565c0; stroke-width: 2px; }
/* обединен елемент (27.11.2026) - лилав контур; избраните с Ctrl / Shift + клик за обединяване - оранжево */
.fp-piece.grp .c { stroke: #7b1fa2; stroke-dasharray: 6 3; stroke-width: 1.5px; }
.fp-piece.multi .c { stroke: #ef6c00; stroke-width: 3px; stroke-dasharray: none; }
.fp-label .g { fill: #7b1fa2; font-weight: bold; }
/* докато се мести или върти - избраният елемент полупрозрачен, вижда се чертежът под панелите */
.fp-root.busy .fp-piece.sel { opacity: 0.5; }
.fp-label { fill: #111; font-family: "Arial Narrow", "Roboto Condensed", "Segoe UI", sans-serif;
            font-stretch: condensed; font-weight: 600; letter-spacing: -0.2px; paint-order: stroke; stroke: #fff;
            stroke-width: 2.5px; stroke-linejoin: round; pointer-events: none; }
.fp-label .k { font-weight: normal; fill: #444; }
.fp-label.on, .fp-label.on .k { fill: #1565c0; font-weight: bold; }
.fp-label.on { stroke-width: 4px; }
.fp-root.busy .fp-label:not(.on) { opacity: 0.25; }
.fp-handle-line { stroke: #1565c0; stroke-dasharray: 4 3; pointer-events: none; }
.fp-handle { fill: #fff; stroke: #1565c0; cursor: grab; }
.fp-handle:hover { fill: #ffe9a8; }
.fp-calib { stroke: #e53935; fill: #e53935; }
"""

FLOOR_JS = r"""
const NS = "http://www.w3.org/2000/svg";
const SNAP = 5;        // местата - през 5 см
const SNAP_DEG = 5;    // завъртане с дръжката - през 5° (със Shift - през 1°)

function el(tag, attrs) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  return e;
}

function norm(a) {
  a = Math.round(a * 10) / 10 % 360;
  return a < 0 ? a + 360 : a;
}

function pieceTransform(p, pos) {
  return `translate(${pos.x},${-pos.y}) scale(1,-1) rotate(${pos.rot || 0}) scale(${pos.mir ? -1 : 1},1) ` +
         `translate(${-p.cx},${-p.cy})`;
}

function worldSize(p, pos) {
  const a = (pos.rot || 0) * Math.PI / 180, c = Math.abs(Math.cos(a)), s = Math.abs(Math.sin(a));
  return [c * p.w + s * p.h, s * p.w + c * p.h];
}

// дръжката за завъртане: над елемента по посоката на завъртането (на етажа, y нагоре)
function handlePoint(S, id) {
  const p = S.byId[id], pos = S.pos[id];
  const r = Math.max(p.w, p.h) / 2 + S.fs * 1.6;
  const a = (pos.rot || 0) * Math.PI / 180;
  return [pos.x - r * Math.sin(a), pos.y + r * Math.cos(a)];
}

function build(parent) {
  const root = document.createElement("div");
  root.className = "fp-root";
  root.tabIndex = 0;
  root.innerHTML = `<div class="fp-wrap"><div class="fp-bar">
      <button data-a="rotl"></button><button data-a="rotr"></button>
      <label><span class="fp-angle-label"></span><input class="fp-angle" type="text" inputmode="decimal">°</label>
      <button data-a="mir"></button><button data-a="fit"></button>
      <button data-a="calib"></button><span class="fp-sep"></span>
      <button data-a="copy"></button><button data-a="paste"></button>
      <button data-a="del"></button><span class="fp-hint"></span></div></div>`;
  const svg = el("svg", { class: "fp-svg" });
  root.querySelector(".fp-wrap").appendChild(svg);
  parent.appendChild(root);
  const S = { pos: {}, token: null, sel: null, view: null, drag: null, pan: null, turn: null, calib: null, fs: 20,
              mouse: null, inside: false, multi: [] };
  root.__s = S;

  const pt = (evt) => {
    const p = svg.createSVGPoint();
    p.x = evt.clientX; p.y = evt.clientY;
    return p.matrixTransform(svg.getScreenCTM().inverse());
  };
  const commit = () => S.api.setStateValue("positions", JSON.parse(JSON.stringify(S.pos)));
  root.__commit = commit;

  root.querySelector(".fp-bar").addEventListener("click", (evt) => {
    const a = evt.target.closest("button")?.dataset.a;
    if (a === "rotl" || a === "rotr" || a === "mir") act(root, a);
    else if (a === "copy" || a === "paste" || a === "del") edit(root, a, false);
    else if (a === "fit") { S.view = null; keep(S).view = null; draw(root); }
    else if (a === "calib") { S.calib = S.calib ? null : []; draw(root); }
  });
  const angle = root.querySelector(".fp-angle");
  angle.addEventListener("change", () => {
    const v = parseFloat(angle.value.replace(",", "."));
    if (!S.sel || !isFinite(v)) { updateBar(root); return; }
    turnGroup(root, groupBase(S, S.sel), v - (S.pos[S.sel].rot || 0));
    commit();
  });
  angle.addEventListener("keydown", (evt) => { if (evt.key === "Enter") angle.blur(); });
  root.addEventListener("keydown", (evt) => {
    if (evt.target.tagName === "INPUT") return;
    // Ctrl+C / Ctrl+V по клавиша (evt.code) - и на кирилица; Delete - изтриване, Esc - без избор
    if ((evt.ctrlKey || evt.metaKey) && (evt.code === "KeyC" || evt.code === "KeyV")) {
      evt.preventDefault();
      edit(root, evt.code === "KeyC" ? "copy" : "paste", true);
      return;
    }
    if (evt.ctrlKey || evt.metaKey || evt.altKey) return;
    if (evt.key === "Delete") edit(root, "del", true);
    else if (evt.key === "Escape") { setMulti(root, []); select(root, null); }
    else if (evt.key === "r" || evt.key === "R") act(root, evt.shiftKey ? "rotr" : "rotl");
    else if (evt.key === "m" || evt.key === "M") act(root, "mir");
  });
  svg.addEventListener("pointerenter", () => (S.inside = true));
  svg.addEventListener("pointerleave", () => (S.inside = false));
  svg.addEventListener("pointerdown", (evt) => {
    root.focus();
    S.down = null;
    const p = pt(evt);
    if (S.calib) {
      S.calib.push([p.x, -p.y]);
      if (S.calib.length === 2) {
        const [a, b] = S.calib;
        const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        S.calib = null;
        if (d > 0) S.api.setTriggerValue("calib", d);
      }
      draw(root);
      return;
    }
    svg.setPointerCapture(evt.pointerId);
    if (evt.target.classList.contains("fp-handle") && S.sel) {
      S.turn = { id: S.sel, moved: false, base: groupBase(S, S.sel) };
      return;
    }
    const g = evt.target.closest(".fp-piece");
    if (g) {
      const id = g.dataset.id;
      // Ctrl / Shift + клик - избор на няколко елемента за „Обедини“ (27.11.2026)
      if (evt.ctrlKey || evt.metaKey || evt.shiftKey) { toggleMulti(root, id); return; }
      if (S.multi.length) setMulti(root, []);
      S.down = id;
      // обединеният елемент се мести целият
      const ids = members(S, id), base = {};
      ids.forEach((i) => (base[i] = { x: S.pos[i].x, y: S.pos[i].y }));
      S.drag = { id, ids, base, p0: p, moved: false, sel: S.sel !== id };
      select(root, id, false);
    } else {
      S.pan = { cx: evt.clientX, cy: evt.clientY, v: { ...S.view }, k: svg.getScreenCTM().a };
    }
  });
  svg.addEventListener("pointermove", (evt) => {
    const m = pt(evt);
    S.mouse = [m.x, -m.y];
    if (S.turn) {
      const p = pt(evt), pos = S.pos[S.turn.id];
      const deg = Math.atan2(-p.y - pos.y, p.x - pos.x) * 180 / Math.PI - 90;
      const step = evt.shiftKey ? 1 : SNAP_DEG;
      const base = S.turn.base, b = base.pos[S.turn.id];
      let target = norm(Math.round(deg / step) * step);
      if (base.ids.length > 1) {   // обединен елемент - около центъра му, с колкото се е завъртяла мишката
        const dg = Math.atan2(-p.y - base.cy, p.x - base.cx) * 180 / Math.PI;
        if (S.turn.a0 === undefined) S.turn.a0 = dg;
        target = (b.rot || 0) + Math.round((dg - S.turn.a0) / step) * step;
      }
      turnGroup(root, base, target - (b.rot || 0));
      if (!S.turn.moved) { S.turn.moved = true; labelState(root); }
    } else if (S.drag) {
      const p = pt(evt);
      for (const i of S.drag.ids) {
        S.pos[i].x = S.drag.base[i].x + (p.x - S.drag.p0.x);
        S.pos[i].y = S.drag.base[i].y - (p.y - S.drag.p0.y);
        place(root, i);
      }
      if (!S.drag.moved) { S.drag.moved = true; labelState(root); }
    } else if (S.pan) {
      S.view.x = S.pan.v.x - (evt.clientX - S.pan.cx) / S.pan.k;
      S.view.y = S.pan.v.y - (evt.clientY - S.pan.cy) / S.pan.k;
      svg.setAttribute("viewBox", `${S.view.x} ${S.view.y} ${S.view.w} ${S.view.h}`);
    }
  });
  const up = () => {
    if (S.turn && S.turn.moved) commit();
    if (S.drag && S.drag.moved) {
      // прилепва през 5 см - обединеният елемент с едно и също преместване (частите остават допрени)
      const pos = S.pos[S.drag.id];
      const dx = Math.round(pos.x / SNAP) * SNAP - pos.x, dy = Math.round(pos.y / SNAP) * SNAP - pos.y;
      for (const i of S.drag.ids) { S.pos[i].x += dx; S.pos[i].y += dy; place(root, i); }
      commit();
    }
    // изборът - към Python (полетата на избрания елемент под плана), след пускането - не по време на влаченето
    if (S.drag && S.drag.sel) S.api.setStateValue("sel", S.sel || "");
    S.drag = null; S.pan = null; S.turn = null;
    labelState(root);
  };
  svg.addEventListener("pointerup", up);
  // двоен клик върху елемент - прозорецът с името и размерите (в Python)
  svg.addEventListener("dblclick", () => {
    if (S.down && S.byId[S.down]) S.api.setTriggerValue("action", { a: "edit", id: S.down });
  });
  svg.addEventListener("pointercancel", up);
  svg.addEventListener("wheel", (evt) => {
    evt.preventDefault();
    const p = pt(evt);
    const f = evt.deltaY > 0 ? 1.15 : 1 / 1.15;
    const v = S.view;
    v.x = p.x - (p.x - v.x) * f; v.y = p.y - (p.y - v.y) * f; v.w *= f; v.h *= f;
    svg.setAttribute("viewBox", `${v.x} ${v.y} ${v.w} ${v.h}`);
    rescale(root);
  }, { passive: false });
  return root;
}

// изборът и копираното, и изгледът - за чертежа (view_key); остават при нов компонент след промяна в таблицата
function keep(S) {
  const all = (globalThis.__tekoFloor = globalThis.__tekoFloor || {});
  return (all[S.data.view_key] = all[S.data.view_key] || {});
}

// частите на обединения елемент (или само елементът)
function members(S, id) {
  const g = S.byId[id] && S.byId[id].group;
  return g ? S.data.pieces.filter((p) => p.group === g).map((p) => p.id) : [id];
}

// местата преди завъртането и центърът на обединения елемент - въртят се заедно около него
function groupBase(S, id) {
  const ids = members(S, id), pos = {};
  let cx = 0, cy = 0;
  for (const i of ids) { pos[i] = { ...S.pos[i] }; cx += pos[i].x / ids.length; cy += pos[i].y / ids.length; }
  return { ids, pos, cx, cy };
}

function turnGroup(root, base, delta) {
  const S = root.__s, a = delta * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
  for (const i of base.ids) {
    const b = base.pos[i], dx = b.x - base.cx, dy = b.y - base.cy;
    const pos = S.pos[i];
    pos.rot = norm((b.rot || 0) + delta);
    if (base.ids.length > 1) { pos.x = base.cx + dx * c - dy * s; pos.y = base.cy + dx * s + dy * c; }
    place(root, i);
  }
}

function setMulti(root, ids) {
  const S = root.__s;
  S.multi = ids;
  root.querySelectorAll(".fp-piece").forEach((n) => n.classList.toggle("multi", ids.includes(n.dataset.id)));
  updateBar(root);
  S.api.setStateValue("multi", ids);
}

function toggleMulti(root, id) {
  const S = root.__s;
  let ids = S.multi.length ? [...S.multi] : (S.sel && S.sel !== id ? [S.sel] : []);
  ids = ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id];
  setMulti(root, ids);
}

function select(root, id, send = true) {
  const S = root.__s;
  S.sel = id;
  const svg = root.querySelector("svg");
  svg.querySelectorAll(".fp-piece").forEach((n) => n.classList.toggle("sel", n.dataset.id === id));
  if (id) place(root, id);
  labelState(root);
  updateBar(root);
  if (send) S.api.setStateValue("sel", id || "");
}

// промени в таблицата (потребителят, 24.11.2026): копирай / постави, изтрий - към Python („Нов елемент“ - вдясно)
function edit(root, a, key) {
  const S = root.__s, K = keep(S);
  if (a === "copy") {
    if (!S.sel) return;
    K.clip = S.sel;
    updateBar(root);
    return;
  }
  if (a === "del") {
    if (S.sel) S.api.setTriggerValue("action", { a: "delete", id: S.sel });
    return;
  }
  const id = K.clip;   // постави: при Ctrl+V - там, където е мишката, от бутона - до копирания
  if (!id || !S.byId[id]) return;
  const src = S.pos[id];
  let [x, y] = key && S.inside && S.mouse ? S.mouse : [src.x + 50, src.y - 50];
  x = Math.round(x / SNAP) * SNAP;
  y = Math.round(y / SNAP) * SNAP;
  S.api.setTriggerValue("action", { a: "paste", id, x, y, rot: src.rot || 0, mir: !!src.mir });
}

function act(root, a) {
  const S = root.__s;
  if (!S.sel || !S.pos[S.sel]) return;
  const pos = S.pos[S.sel];
  if (a === "rotl" || a === "rotr") turnGroup(root, groupBase(S, S.sel), a === "rotl" ? 90 : -90);
  else if (!S.byId[S.sel].group) { pos.mir = !pos.mir; place(root, S.sel); }
  else return;   // обединен елемент - без огледално (частите ще се разместят)
  root.__commit();
}

function place(root, id) {
  const S = root.__s;
  const p = S.byId[id], pos = S.pos[id];
  const svg = root.querySelector("svg");
  const g = svg.querySelector(`.fp-piece[data-id="${CSS.escape(id)}"]`);
  const t = svg.querySelector(`.fp-label[data-id="${CSS.escape(id)}"]`);
  if (g) g.setAttribute("transform", pieceTransform(p, pos));
  if (t) {
    t.setAttribute("x", pos.x); t.setAttribute("y", -pos.y);
    t.querySelectorAll("tspan").forEach((s) => s.setAttribute("x", pos.x));
  }
  if (id === S.sel) {
    const [hx, hy] = handlePoint(S, id);
    const line = svg.querySelector(".fp-handle-line"), h = svg.querySelector(".fp-handle");
    line.setAttribute("x1", pos.x); line.setAttribute("y1", -pos.y);
    line.setAttribute("x2", hx); line.setAttribute("y2", -hy);
    h.setAttribute("cx", hx); h.setAttribute("cy", -hy);
    line.style.display = h.style.display = "";
    const angle = root.querySelector(".fp-angle");
    if (root.getRootNode().activeElement !== angle) angle.value = String(pos.rot || 0).replace(".", ",");
  }
}

// надписите (потребителят, 25.11.2026, вариант Б): еднакъв размер на екрана при всяко приближаване (не растат и не
// се застъпват); на два реда - видът дребно („Колона“), името под него („К16“); избраният - синьо, по-голям и
// най-отгоре; докато се влачи или върти, другите избледняват
const LABEL_PX = 11;

function labelSize(root, S) {
  const svg = root.querySelector("svg");
  const cw = svg.clientWidth || 1000, ch = svg.clientHeight || 680;
  return LABEL_PX * Math.max(S.view.w / cw, S.view.h / ch);
}

function setLabel(t, p, fs, x) {
  const parts = p.label.split(" "), kind = parts.shift(), name = parts.join(" ");
  t.replaceChildren();
  if (p.group) {   // обединен елемент - името му над частта
    const g = el("tspan", { x, dy: name ? "-1.5em" : "-0.5em", class: "g", "font-size": fs * 0.8 });
    g.textContent = "🔗 " + p.group;
    t.append(g);
  }
  if (!name) {
    const n = el("tspan", { x, dy: p.group ? "1.05em" : "0" });
    n.textContent = p.label;
    t.append(n);
    return;
  }
  const a = el("tspan", { x, dy: p.group ? "1.05em" : "-0.5em", class: "k", "font-size": fs * 0.8 });
  a.textContent = kind;
  const b = el("tspan", { x, dy: "1.05em" });
  b.textContent = name;
  t.append(a, b);
}

function labelState(root) {
  const S = root.__s, svg = root.querySelector("svg");
  root.classList.toggle("busy", !!((S.drag && S.drag.moved) || (S.turn && S.turn.moved)));
  svg.querySelectorAll(".fp-label").forEach((t) => {
    const p = S.byId[t.dataset.id], on = t.dataset.id === S.sel, fs = on ? S.fs * 1.25 : S.fs;
    if (!p) return;
    t.classList.toggle("on", on);
    t.setAttribute("font-size", fs);
    setLabel(t, p, fs, S.pos[p.id] ? S.pos[p.id].x : 0);
    if (on) t.parentNode.appendChild(t);
  });
}

// след приближаване с колелцето - надписите и кръгчето за завъртане - пак със същия размер на екрана
function rescale(root) {
  const S = root.__s, svg = root.querySelector("svg");
  S.fs = labelSize(root, S);
  svg.querySelector(".fp-handle")?.setAttribute("r", S.fs * 0.55);
  labelState(root);
  if (S.sel) place(root, S.sel);
}

function updateBar(root) {
  const S = root.__s, T = S.data.texts;
  const b = (a) => root.querySelector(`button[data-a="${a}"]`);
  for (const a of ["rotl", "rotr", "mir", "fit", "calib", "copy", "paste", "del"]) b(a).textContent = T[a];
  const K = keep(S);
  if (K.clip && !S.byId[K.clip]) K.clip = null;
  b("copy").disabled = b("del").disabled = !S.sel;
  b("paste").disabled = !K.clip;
  root.querySelector(".fp-angle-label").textContent = T.angle;
  const angle = root.querySelector(".fp-angle");
  b("rotl").disabled = b("rotr").disabled = b("mir").disabled = angle.disabled = !S.sel;
  if (S.sel && S.byId[S.sel] && S.byId[S.sel].group) b("mir").disabled = true;
  if (!S.sel) angle.value = "";
  b("calib").style.display = S.data.bg ? "" : "none";
  b("calib").classList.toggle("on", !!S.calib);
  root.querySelector(".fp-hint").textContent = S.calib
    ? (S.calib.length ? T.calib2 : T.calib1)
    : S.multi.length ? (T.multi || "").replace("{n}", S.multi.length)
    : K.clip ? T.copied.replace("{name}", S.byId[K.clip]?.label || "")
    : (S.sel ? T.selected.replace("{name}", S.byId[S.sel]?.label || "") : T.hint);
  if (!S.sel) {
    const svg = root.querySelector("svg");
    svg.querySelectorAll(".fp-handle, .fp-handle-line").forEach((n) => (n.style.display = "none"));
  }
}

function fitView(S) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const p of S.data.pieces) {
    const pos = S.pos[p.id];
    const [w, h] = worldSize(p, pos);
    x0 = Math.min(x0, pos.x - w / 2); x1 = Math.max(x1, pos.x + w / 2);
    y0 = Math.min(y0, -pos.y - h / 2); y1 = Math.max(y1, -pos.y + h / 2);
  }
  const bg = S.data.bg;
  if (bg) { x0 = Math.min(x0, 0); x1 = Math.max(x1, bg.w); y0 = Math.min(y0, -bg.h); y1 = Math.max(y1, 0); }
  if (!isFinite(x0)) { x0 = 0; y0 = -1000; x1 = 1000; y1 = 0; }
  const pad = 0.05 * Math.max(x1 - x0, y1 - y0, 100);
  // отгоре - място за лентата с бутоните
  return { x: x0 - pad, y: y0 - 3 * pad, w: x1 - x0 + 2 * pad, h: y1 - y0 + 4 * pad };
}

function draw(root) {
  const S = root.__s, D = S.data;
  const svg = root.querySelector("svg");
  S.byId = {};
  D.pieces.forEach((p) => (S.byId[p.id] = p));
  if (S.sel && !S.byId[S.sel]) S.sel = null;
  S.multi = S.multi.filter((i) => S.byId[i]);
  if (!S.view) S.view = fitView(S);
  keep(S).view = S.view;
  svg.setAttribute("viewBox", `${S.view.x} ${S.view.y} ${S.view.w} ${S.view.h}`);
  svg.replaceChildren();
  const span = Math.max(S.view.w, S.view.h);
  S.fs = labelSize(root, S);

  const gid = "fpgrid" + Math.random().toString(36).slice(2, 8);
  const defs = el("defs", {});
  const pat = el("pattern", { id: gid, width: 100, height: 100, patternUnits: "userSpaceOnUse" });
  pat.appendChild(el("path", { d: "M 100 0 L 0 0 0 100", fill: "none", stroke: "#e3e7ec",
                               "stroke-width": 1, "vector-effect": "non-scaling-stroke" }));
  defs.appendChild(pat);
  svg.appendChild(defs);
  svg.appendChild(el("rect", { x: S.view.x - 20 * span, y: S.view.y - 20 * span, width: 41 * span,
                               height: 41 * span, fill: `url(#${gid})` }));
  if (D.bg) {
    const img = el("image", { x: 0, y: -D.bg.h, width: D.bg.w, height: D.bg.h, opacity: D.bg.opacity,
                              preserveAspectRatio: "none" });
    img.setAttribute("href", D.bg.url);
    svg.appendChild(img);
  }
  const gp = el("g", {}), gl = el("g", {});
  for (const p of D.pieces) {
    const g = el("g", { class: "fp-piece" + (p.id === S.sel ? " sel" : "") + (p.group ? " grp" : "") +
                          (S.multi.includes(p.id) ? " multi" : "") });
    g.dataset.id = p.id;
    // бетонът - контурите (шахта - пръстен: външният и вътрешният, дупката не се хваща)
    const rings = p.rings || [p.poly];
    g.appendChild(el("path", { class: "c", "fill-rule": "evenodd",
                               d: rings.map((r) => "M " + r.map((q) => q.join(",")).join(" L ") + " Z").join(" "),
                               "vector-effect": "non-scaling-stroke", "stroke-width": 1 }));
    for (const f of p.forms) {
      g.appendChild(el("rect", { class: f[4], x: f[0], y: f[1], width: f[2] - f[0], height: f[3] - f[1],
                                 "vector-effect": "non-scaling-stroke", "stroke-width": 0.5 }));
    }
    gp.appendChild(g);
    const t = el("text", { class: "fp-label", "text-anchor": "middle", "dominant-baseline": "middle",
                           "font-size": S.fs });
    t.dataset.id = p.id;
    t.textContent = p.label;
    gl.appendChild(t);
  }
  svg.appendChild(gp);
  svg.appendChild(gl);
  svg.appendChild(el("line", { class: "fp-handle-line", "vector-effect": "non-scaling-stroke", "stroke-width": 1.5 }));
  svg.appendChild(el("circle", { class: "fp-handle", r: S.fs * 0.55, "vector-effect": "non-scaling-stroke",
                                 "stroke-width": 2 }));
  if (S.calib && S.calib.length) {
    const [a] = S.calib;
    svg.appendChild(el("circle", { class: "fp-calib", cx: a[0], cy: -a[1], r: S.fs / 3 }));
  }
  D.pieces.forEach((p) => place(root, p.id));
  labelState(root);
  updateBar(root);
}

export default function (component) {
  const { data, parentElement, setStateValue, setTriggerValue } = component;
  if (!data) return;
  let root = parentElement.querySelector(".fp-root");
  if (!root) root = build(parentElement);
  const S = root.__s;
  S.api = { setStateValue, setTriggerValue };
  if (S.token !== data.token) {
    S.pos = JSON.parse(JSON.stringify(data.positions || {}));
    S.token = data.token;
    S.data = data;
    // след промяна в таблицата - същият изглед и изборът (новият или копираният елемент)
    S.view = data.keep_view && keep(S).view ? { ...keep(S).view } : null;
    S.sel = data.select || null;
    S.multi = [];
  } else {
    for (const id in data.positions) if (!(id in S.pos)) S.pos[id] = { ...data.positions[id] };
  }
  S.data = data;
  draw(root);
}
"""

_component = None


def floor_component():
    """
    Компонентът за подреждане. Регистрира се веднъж за runtime-а на Streamlit (модулът не се презарежда с
    app.py, а повторна регистрация пише предупреждение); нов runtime (тестовете) - регистрира се наново.
    """
    global _component
    import streamlit as st
    from streamlit.runtime import Runtime
    if _component is None or Runtime.instance().bidi_component_registry.get("teko_floor_plan") is None:
        _component = st.components.v2.component("teko_floor_plan", css=FLOOR_CSS, js=FLOOR_JS)
    return _component
