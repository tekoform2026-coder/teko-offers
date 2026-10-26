# drawing_generator.py
import io
import os
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from reportlab.lib.utils import ImageReader

from accessories_calculator import waler_heights_cm, NARROW_LIMIT_CM
from teko_calculator import IN_CORNER_CM

# Висока резолюция за чисти линии и четливи надписи
DPI_RESOLUTION = 300

# Настройки на шрифтовете и рендирането
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['text.antialiased'] = True
matplotlib.rcParams['path.simplify'] = False

# Цветова палитра TEKO
COLOR_PANEL = '#F1948A'         # Кофражен панел (розово-червен)
COLOR_PANEL_BORDER = '#681910'  # Кант на панел (тъмночервен)
COLOR_CORNER_EX = '#52BE80'     # Външен ъгъл EX (яркозелено)
COLOR_CORNER_IN = '#1E8449'     # Вътрешен ъгъл IN (тъмнозелено)
COLOR_WALER = '#27AE60'         # Ригел AW / Вертикализатори (зелено)
COLOR_CONCRETE = '#D5D8DC'      # Бетонно ядро (светлосиво)

def setup_pdf_fonts():
    """Регистрира кирилски шрифт в ReportLab."""
    try:
        font_dir = os.path.join(matplotlib.get_data_path(), 'fonts', 'ttf')
        regular_path = os.path.join(font_dir, 'DejaVuSans.ttf')
        bold_path = os.path.join(font_dir, 'DejaVuSans-Bold.ttf')
        
        if os.path.exists(regular_path):
            pdfmetrics.registerFont(TTFont('DejaVuSans', regular_path))
        if os.path.exists(bold_path):
            pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', bold_path))
        return True
    except Exception:
        return False

# ==========================================
# 1. ОБЩ 3D ИЗГЛЕД НА ЦЕЛИЯ ОБЕКТ
# ==========================================
def generate_overall_project_3d_buf(pdf_elements):
    fig = plt.figure(figsize=(7.5, 3.5), dpi=DPI_RESOLUTION)
    ax = fig.add_subplot(111, projection='3d')
    
    def draw_prism_3d(x0, y0, z0, dx, dy, dz, facecolor, edgecolor='#2C3E50', alpha=0.85):
        vertices = np.array([
            [x0, y0, z0], [x0+dx, y0, z0], [x0+dx, y0+dy, z0], [x0, y0+dy, z0],
            [x0, y0, z0+dz], [x0+dx, y0, z0+dz], [x0+dx, y0+dy, z0+dz], [x0, y0, z0+dz]
        ])
        faces = [
            [vertices[0], vertices[1], vertices[2], vertices[3]],
            [vertices[4], vertices[5], vertices[6], vertices[7]],
            [vertices[0], vertices[1], vertices[5], vertices[4]],
            [vertices[2], vertices[3], vertices[7], vertices[6]],
            [vertices[0], vertices[3], vertices[7], vertices[4]],
            [vertices[1], vertices[2], vertices[6], vertices[5]]
        ]
        poly = Poly3DCollection(faces, facecolors=facecolor, edgecolors=edgecolor, linewidths=0.5, alpha=alpha)
        ax.add_collection3d(poly)

    grid_cols = 3
    spacing_x = 250.0
    spacing_y = 250.0
    
    max_x, max_y, max_z = 300.0, 300.0, 300.0

    for idx, elem in enumerate(pdf_elements):
        row = idx // grid_cols
        col = idx % grid_cols
        
        pos_x = col * spacing_x
        pos_y = row * spacing_y
        
        l_a = float(elem.get('length_a_cm') or elem.get('length_cm') or 100)
        l_b = float(elem.get('length_b_cm') or elem.get('width_cm') or l_a)
        h_cm = float(elem.get('height_cm') or 300)
        thick = float(elem.get('thickness_cm') or 30)
        w_type = str(elem.get('type_bg') or elem.get('wall_type') or 'Стена')
        e_name = str(elem.get('name', f'E{idx+1}'))

        is_column = "колона" in w_type.lower() or "column" in w_type.lower() or "колона" in e_name.lower()
        dim_y = l_b if is_column else thick

        draw_prism_3d(pos_x, pos_y, 0, l_a, dim_y, h_cm, COLOR_CONCRETE, alpha=0.6)
        
        draw_prism_3d(pos_x - 10, pos_y - 10, 0, l_a + 20, 10, h_cm, COLOR_PANEL)
        draw_prism_3d(pos_x - 10, pos_y + dim_y, 0, l_a + 20, 10, h_cm, COLOR_PANEL)
        if is_column:
            draw_prism_3d(pos_x - 10, pos_y, 0, 10, dim_y, h_cm, COLOR_PANEL)
            draw_prism_3d(pos_x + l_a, pos_y, 0, 10, dim_y, h_cm, COLOR_PANEL)

        draw_prism_3d(pos_x - 10, pos_y - 10, 0, 10, 10, h_cm, COLOR_CORNER_EX)
        draw_prism_3d(pos_x + l_a, pos_y - 10, 0, 10, 10, h_cm, COLOR_CORNER_EX)
        if is_column:
            draw_prism_3d(pos_x - 10, pos_y + dim_y, 0, 10, 10, h_cm, COLOR_CORNER_EX)
            draw_prism_3d(pos_x + l_a, pos_y + dim_y, 0, 10, 10, h_cm, COLOR_CORNER_EX)

        ax.text(pos_x + l_a/2, pos_y + dim_y/2, h_cm + 60, e_name, 
                ha='center', va='bottom', fontsize=8, fontweight='bold', color='#111111')

        max_x = max(max_x, pos_x + l_a + 100)
        max_y = max(max_y, pos_y + dim_y + 100)
        max_z = max(max_z, h_cm + 100)

    ax.set_xlim(-50, max_x)
    ax.set_ylim(-50, max_y)
    ax.set_zlim(0, max_z)
    ax.set_box_aspect([max_x + 50, max_y + 50, max_z])
    
    ax.axis('off')
    ax.view_init(elev=26, azim=-55)
    ax.set_title("3D Общ кофражен план на обект (Project Overview)", fontsize=10, fontweight='bold', pad=10)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.05, dpi=DPI_RESOLUTION)
    plt.close(fig)
    buf.seek(0)
    return buf

# ==========================================
# 2. ГЕОМЕТРИЯ В ПЛАН (ОБЩА ЗА ИЗГЛЕД ОТГОРЕ И 3D)
# ==========================================
PANEL_T = 10  # дебелина на панела/ъгъла в чертежа (cm)

def _plan_geometry(layout):
    """
    Разполага страните от teko_calculator.layout_element в план.
    Връща (контур на бетона, {страна: (x0, y0, ос)}, [(тип ъгъл, x, y)]).
    Всяка страна е лента с дебелина PANEL_T, започваща от (x0, y0) по оста 'x' или 'y'.
    """
    T = PANEL_T
    t = layout["thickness_cm"]
    k = t + IN_CORNER_CM
    d = layout["dims"]
    end_1, end_2 = layout["closed"]
    typ = layout["type"]

    if typ == "column":
        a, b = d["a"], d["b"]
        poly = [[0, 0], [a, 0], [a, b], [0, b]]
        place = {"A": (0, -T, 'x'), "A1": (0, b, 'x'), "B": (-T, 0, 'y'), "B1": (a, 0, 'y')}
        corners = [("EX", -T, -T), ("EX", a, -T), ("EX", a, b), ("EX", -T, b)]

    elif typ == "wall":
        L = d["length"]
        poly = [[0, 0], [L, 0], [L, t], [0, t]]
        place = {"A": (0, -T, 'x'), "A1": (0, t, 'x'), "Край 1": (L, 0, 'y'), "Край 2": (-T, 0, 'y')}
        corners = []
        if end_1:
            corners += [("EX", L, -T), ("EX", L, t)]
        if end_2:
            corners += [("EX", -T, -T), ("EX", -T, t)]

    elif typ == "l_wall":
        l1, l2 = d["l1"], d["l2"]
        poly = [[0, 0], [l1, 0], [l1, t], [t, t], [t, l2], [0, l2]]
        place = {"A": (0, -T, 'x'), "A1": (k, t, 'x'), "B": (-T, 0, 'y'), "B1": (t, k, 'y'),
                 "Край A": (l1, 0, 'y'), "Край B": (0, l2, 'x')}
        corners = [("EX", -T, -T), ("IN", t, t)]
        if end_1:
            corners += [("EX", l1, -T), ("EX", l1, t)]
        if end_2:
            corners += [("EX", -T, l2), ("EX", t, l2)]

    else:  # u_wall: рамо A вляво, гръб B отдолу, рамо C вдясно
        l1, m, l3 = d["l1"], d["l2"], d["l3"]
        poly = [[0, 0], [m, 0], [m, l3], [m - t, l3], [m - t, t], [t, t], [t, l1], [0, l1]]
        place = {"B": (0, -T, 'x'), "B1": (k, t, 'x'),
                 "A": (-T, 0, 'y'), "A1": (t, k, 'y'),
                 "C": (m, 0, 'y'), "C1": (m - t - T, k, 'y'),
                 "Край A": (0, l1, 'x'), "Край C": (m - t, l3, 'x')}
        corners = [("EX", -T, -T), ("EX", m, -T), ("IN", t, t), ("IN", m - t - T, t)]
        if end_1:
            corners += [("EX", -T, l1), ("EX", t, l1)]
        if end_2:
            corners += [("EX", m - t - T, l3), ("EX", m, l3)]


    return poly, place, corners

def _closed_label(layout):
    """Кои челни краища са затворени: "няма", "край 1", "край 2" или "край 1 и 2"."""
    ends = [str(i + 1) for i, c in enumerate(layout["closed"]) if c]
    return f"край {' и '.join(ends)}" if ends else "няма"

def _dims_label(layout):
    d = layout["dims"]
    typ = layout["type"]
    if typ == "column":
        return f"{int(d['a'])}x{int(d['b'])} cm"
    if typ == "wall":
        return f"L={int(d['length'])} cm, B={int(d['t'])} cm"
    if typ == "l_wall":
        return f"A={int(d['l1'])}, B={int(d['l2'])}, дебелина {int(d['t'])} cm"
    return f"A={int(d['l1'])}, B={int(d['l2'])}, C={int(d['l3'])}, дебелина {int(d['t'])} cm"

# ==========================================
# 3. ИЗГЛЕД ОТГОРЕ (TOP VIEW)
# ==========================================
# Стил по еталонните PDF (Turkey.pdf, Жилищна сграда Шумен1.pdf)
TOP_PANEL = '#E5BEC0'
TOP_PANEL_BORDER = '#3A2E36'
TOP_EX = '#A0D784'
TOP_EX_BORDER = '#4F6B45'
TOP_IN = '#4A8F42'
TOP_CONCRETE = '#F1F4F9'
TOP_CONCRETE_BORDER = '#2C3E50'
TOP_GRID = '#E8EBEE'
TOP_TEXT = '#111111'
TOP_GRID_STEP_CM = 10
TOP_LABEL_FS = 9.5      # размер на надписите на панелите (pt)
TOP_LABEL_FS_MIN = 6.0  # под това надписът излиза до панела
TOP_MARGIN_CM = 18


def _text_width_per_pt(text):
    """Ширина на удебелен надпис (pt) при размер на шрифта 1 pt."""
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties
    return TextPath((0, 0), text, size=1, prop=FontProperties(weight='bold')).get_extents().width


def _top_view_title(layout, name):
    """Надпис като в еталона: 'SZ02 колона 80x40' (името без водещото 'Колона')."""
    d = layout["dims"]
    if layout["type"] == "column":
        raw = str(name).strip()
        if raw.lower().startswith("колона"):
            raw = raw[len("колона"):].strip()
        return f"{raw} колона {int(d['a'])}x{int(d['b'])}".strip()
    return str(name)


TOP_WALER = '#5DBB63'
TOP_WALER_BORDER = '#2E7D32'
TOP_PROP = '#9BDB8F'
TOP_PROP_BORDER = '#3E8E41'
TOP_WALER_T = 4  # дебелина на ригела в изгледа отгоре (cm)


def _face_strips(layout, place, poly):
    """
    Лентите с панели в план: {страна: (ос, начало, край по оста, долна и горна граница напречно, посока навън)}.
    Посоката навън (+1/-1 напречно на оста) е към страната без бетон.
    """
    from matplotlib.path import Path
    core = Path(poly)
    T = PANEL_T
    strips = {}
    for face in layout["faces"]:
        x0, y0, axis, *_ = place[face["name"]]
        length = face["length_cm"]
        a0, c0 = (x0, y0) if axis == 'x' else (y0, x0)
        mid = a0 + length / 2
        probe = (lambda c: (mid, c)) if axis == 'x' else (lambda c: (c, mid))
        normal = 1 if core.contains_point(probe(c0 - 1)) else -1
        strips[face["name"]] = (axis, a0, a0 + length, c0, c0 + T, normal)
    return strips


def _prop_marks(layout, strips):
    """Местата на вертикализаторите в план: [(страна, координата по оста)], по calculate_push_pull_props."""
    from accessories_calculator import _prop_positions, _props_per_side
    faces = {f["name"]: f for f in layout["faces"]}

    def covering(axis, coord, normal):
        return [n for n, (ax_, a0, a1, *_r, nrm) in strips.items()
                if ax_ == axis and nrm == normal and a0 <= coord <= a1 and not n.startswith("Край")]

    marks = []
    if layout["type"] == "column":
        for name in ("A", "B"):
            marks.append((name, strips[name][1] + faces[name]["length_cm"] / 2))
    else:
        for name in ("A", "B", "C"):
            if name not in faces:
                continue
            axis, a0, _a1, c_lo, _c_hi, normal = strips[name]
            length = faces[name]["length_cm"]
            for pos in _prop_positions(length, _props_per_side(length)):
                coord = a0 + pos
                marks.append((name, coord))
                # срещу него, от другата страна на същата стена (най-близката лента)
                names = covering(axis, coord, -normal) or [n for n, s in strips.items()
                                                           if s[0] == axis and s[5] == -normal and not n.startswith("Край")]
                if names:
                    opp = min(names, key=lambda n: abs(strips[n][3] - c_lo))
                    o_a0, o_a1 = strips[opp][1], strips[opp][2]
                    marks.append((opp, min(max(coord, o_a0), o_a1)))
    return marks


def _top_accessories(layout, place, poly):
    """
    Ригели (ленти по външната страна на панелите) и вертикализатори с условна дължина.
    Връща (ригели като правоъгълници, вертикализатори като (начало, край)) в координати на плана.
    """
    T = PANEL_T
    strips = _face_strips(layout, place, poly)
    faces = {f["name"]: f for f in layout["faces"]}
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    prop_len = min(80.0, max(40.0, 0.3 * span))

    def to_xy(axis, along, cross):
        return (along, cross) if axis == 'x' else (cross, along)

    walers = []
    with_waler = set()
    for name, (axis, a0, a1, c_lo, c_hi, normal) in strips.items():
        if faces[name]["length_cm"] <= NARROW_LIMIT_CM:
            continue
        with_waler.add(name)
        ext = T + TOP_WALER_T  # над външните ъгли ригелите се застъпват
        s0 = a0 - (ext if faces[name]["start"] == "EX" else 0)
        s1 = a1 + (ext if faces[name]["end"] == "EX" else 0)
        edge = c_hi if normal > 0 else c_lo
        w_lo = edge if normal > 0 else edge - TOP_WALER_T
        x, y = to_xy(axis, s0, w_lo)
        w, h = (s1 - s0, TOP_WALER_T) if axis == 'x' else (TOP_WALER_T, s1 - s0)
        walers.append((x, y, w, h))

    # Препятствия: лентите с панели и ригелите - вертикализаторът спира преди тях;
    # ако се застъпва с вече начертан вертикализатор, не се рисува (в сметката си остава)
    boxes = [(x, y, x + w, y + h) for x, y, w, h in walers]
    for axis, a0, a1, c_lo, c_hi, _n in strips.values():
        (x0, y0), (x1, y1) = to_xy(axis, a0, c_lo), to_xy(axis, a1, c_hi)
        boxes.append((x0, y0, x1, y1))
    drawn = []

    def free_length(p0, d, length, obstacles):
        k = 0 if d[0] else 1  # ос на вертикализатора
        for bx0, by0, bx1, by1 in obstacles:
            lo, hi = (by0, by1) if k == 0 else (bx0, bx1)
            if lo - 3 < p0[1 - k] < hi + 3:
                near = (bx0, by0)[k] if d[k] > 0 else (bx1, by1)[k]
                dist = (near - p0[k]) * d[k]
                if dist > 0.5:
                    length = min(length, dist - 6)
        return length

    marks = _prop_marks(layout, strips)
    # първо външните страни (пълна дължина), после вътрешните - по-късите страни първи (симетрично)
    marks.sort(key=lambda m: (m[0] not in ("A", "B", "C"), faces[m[0]]["length_cm"]))
    props = []
    for name, coord in marks:
        axis, _a0, _a1, c_lo, c_hi, normal = strips[name]
        edge = (c_hi if normal > 0 else c_lo) + (normal * TOP_WALER_T if name in with_waler else 0)
        p0 = to_xy(axis, coord, edge)
        d = to_xy(axis, 0, normal)
        length = max(15.0, free_length(p0, d, prop_len, boxes))
        if free_length(p0, d, length + 6, drawn) < length:
            continue
        p1 = (p0[0] + d[0] * length, p0[1] + d[1] * length)
        bx = (min(p0[0], p1[0]) - 4, min(p0[1], p1[1]) - 4, max(p0[0], p1[0]) + 4, max(p0[1], p1[1]) + 4)
        if any(bx[0] < o[2] and o[0] < bx[2] and bx[1] < o[3] and o[1] < bx[3] for o in drawn):
            continue
        props.append((p0, p1))
        drawn.append(bx)
    return walers, props


def generate_top_view_buf(layout, name="Елемент"):
    T = PANEL_T
    poly, place, corners = _plan_geometry(layout)
    walers, props = _top_accessories(layout, place, poly)

    # Граници на чертежа: бетон + ленти с панели + ъгли + ригели + вертикализатори
    xs = [p[0] for p in poly] + [x for _, x, _ in corners] + [x + T for _, x, _ in corners]
    ys = [p[1] for p in poly] + [y for _, _, y in corners] + [y + T for _, _, y in corners]
    for face in layout["faces"]:
        x0, y0, axis, *_ = place[face["name"]]
        length = sum(face["rows"][0])
        xs += [x0, x0 + (length if axis == 'x' else T)]
        ys += [y0, y0 + (T if axis == 'x' else length)]
    for x, y, w, h in walers:
        xs += [x, x + w]
        ys += [y, y + h]
    for (px0, py0), (px1, py1) in props:
        xs += [px0 - 4, px1 - 4, px0 + 4, px1 + 4]
        ys += [py0 - 4, py1 - 4, py0 + 4, py1 + 4]
    x_min, x_max = min(xs) - TOP_MARGIN_CM, max(xs) + TOP_MARGIN_CM
    y_min, y_max = min(ys) - TOP_MARGIN_CM, max(ys) + TOP_MARGIN_CM + 8  # място за надписите отгоре

    fig_w = 6.0
    fig_h = max(1.6, fig_w * (y_max - y_min) / (x_max - x_min))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=DPI_RESOLUTION)

    # Мрежа през 10 cm
    g = TOP_GRID_STEP_CM
    for gx in range(int(math.ceil(x_min / g)) * g, int(x_max) + 1, g):
        ax.plot([gx, gx], [y_min, y_max], color=TOP_GRID, linewidth=0.6, zorder=0)
    for gy in range(int(math.ceil(y_min / g)) * g, int(y_max) + 1, g):
        ax.plot([x_min, x_max], [gy, gy], color=TOP_GRID, linewidth=0.6, zorder=0)

    ax.add_patch(patches.Polygon(poly, facecolor=TOP_CONCRETE, edgecolor=TOP_CONCRETE_BORDER, linewidth=1.0, zorder=1))

    # Размер на надписа според мащаба: да се събира по дължината на панела (без застъпване);
    # ако и най-малкият размер не стига - надписът излиза до панела, към бетона, на два реда през един
    pt_per_cm = min(fig_w * 72 / (x_max - x_min), fig_h * 72 / (y_max - y_min))
    strips = _face_strips(layout, place, poly)

    # Долният ред на всяка страна; точка на всяка фуга между панели
    for face in layout["faces"]:
        x0, y0, axis, *rev = place[face["name"]]
        normal = strips[face["name"]][5]
        s = 0
        outside = 0
        widths = face["rows"][0][::-1] if rev and rev[0] else face["rows"][0]
        for i, w in enumerate(widths):
            label = f"{int(w)}"
            fs = min(TOP_LABEL_FS, w * pt_per_cm * 0.65 / _text_width_per_pt(label))
            cross = T / 2
            if fs < TOP_LABEL_FS_MIN:
                fs = TOP_LABEL_FS_MIN
                line_cm = fs * 1.15 / pt_per_cm
                step_in = T / 2 + 1 + line_cm * (0.5 + outside % 2)
                cross = T / 2 - normal * step_in
                outside += 1
            if axis == 'x':
                ax.add_patch(patches.Rectangle((x0 + s, y0), w, T, facecolor=TOP_PANEL, edgecolor=TOP_PANEL_BORDER, linewidth=0.7, zorder=2))
                ax.text(x0 + s + w/2, y0 + cross, label, ha='center', va='center', fontsize=fs, fontweight='bold', color=TOP_TEXT, zorder=4)
                if i > 0:
                    ax.plot(x0 + s, y0 + T/2, 'o', markersize=1.8, color=TOP_TEXT, zorder=5)
            else:
                ax.add_patch(patches.Rectangle((x0, y0 + s), T, w, facecolor=TOP_PANEL, edgecolor=TOP_PANEL_BORDER, linewidth=0.7, zorder=2))
                ax.text(x0 + cross, y0 + s + w/2, label, ha='center', va='center', fontsize=fs, fontweight='bold', color=TOP_TEXT, rotation=90, zorder=4)
                if i > 0:
                    ax.plot(x0 + T/2, y0 + s, 'o', markersize=1.8, color=TOP_TEXT, zorder=5)
            s += w

    panel_boxes = []
    for face in layout["faces"]:
        x0, y0, axis, *_ = place[face["name"]]
        length = face["length_cm"]
        panel_boxes.append((x0, y0, x0 + (length if axis == 'x' else T), y0 + (T if axis == 'x' else length)))

    # Ъгли: EX - светлозелено, надписът отвън; IN - тъмнозелено, надписът вътре
    center_x = (min(p[0] for p in poly) + max(p[0] for p in poly)) / 2
    for kind, x, y in corners:
        if kind == "EX":
            ax.add_patch(patches.Rectangle((x, y), T, T, facecolor=TOP_EX, edgecolor=TOP_EX_BORDER, linewidth=0.7, zorder=3))
            left = x + T/2 < center_x
            # надписът отива от страната без панел до ъгъла
            side_busy = [any(sx0 <= px <= sx1 and sy0 <= y + T/2 <= sy1 for sx0, sy0, sx1, sy1 in panel_boxes)
                         for px in (x - 1, x + T + 1)]
            if side_busy[0 if left else 1] and not side_busy[1 if left else 0]:
                left = not left
            gap = 2 + (TOP_WALER_T if walers else 0)  # надписът е извън ригела
            ax.text(x - gap if left else x + T + gap, y + T/2, "EX", ha='right' if left else 'left', va='center',
                    fontsize=8.5, fontweight='bold', color=TOP_TEXT, zorder=4)
        else:
            ax.add_patch(patches.Rectangle((x, y), T, T, facecolor=TOP_IN, edgecolor=TOP_EX_BORDER, linewidth=0.7, zorder=3))
            ax.text(x + T/2, y + T/2, "IN", ha='center', va='center', fontsize=6.5, fontweight='bold', color='white', zorder=4)

    # Ригели по външната страна на панелите
    for x, y, w, h in walers:
        ax.add_patch(patches.Rectangle((x, y), w, h, facecolor=TOP_WALER, edgecolor=TOP_WALER_BORDER,
                                       linewidth=0.5, zorder=2.5))

    # Вертикализатори (условна дължина): закрепване при панела, регулируема част, опорна плоча
    for (px0, py0), (px1, py1) in props:
        ax.plot([px0, px1], [py0, py1], color=TOP_PROP_BORDER, linewidth=2.6, solid_capstyle='butt', zorder=6)
        ax.plot([px0, px1], [py0, py1], color=TOP_PROP, linewidth=1.6, solid_capstyle='butt', zorder=6.1)
        ax.plot([px0 + 0.3 * (px1 - px0), px0 + 0.8 * (px1 - px0)], [py0 + 0.3 * (py1 - py0), py0 + 0.8 * (py1 - py0)],
                color=TOP_PROP_BORDER, linewidth=0.8, linestyle=(0, (1, 2)), zorder=6.2)
        ax.add_patch(patches.Rectangle((px1 - 3, py1 - 3), 6, 6, facecolor=TOP_PROP, edgecolor=TOP_PROP_BORDER,
                                       linewidth=0.6, zorder=6.3))
        ax.plot(px0, py0, 'o', markersize=3.2, markerfacecolor='white', markeredgecolor=TOP_PROP_BORDER,
                markeredgewidth=0.7, zorder=6.4)

    # Надписи: размер отгоре, наименование под него, размер вляво (вертикално)
    top_y = max(ys)
    mid_x = (min(p[0] for p in poly) + max(p[0] for p in poly)) / 2
    if layout["type"] == "column":
        d = layout["dims"]
        ax.text(mid_x, top_y + 7.5, f"{int(d['a'])} cm", ha='center', va='bottom', fontsize=9.5, fontweight='bold', color=TOP_TEXT)
        # вдясно, където няма вертикализатор
        ax.text(d["a"] + T + TOP_WALER_T + 4, d["b"] / 2, f"{int(d['b'])} cm", ha='left', va='center', fontsize=9.5,
                fontweight='bold', color=TOP_TEXT, rotation=90)
    ax.text(mid_x, top_y + 2.5, _top_view_title(layout, name), ha='center', va='bottom', fontsize=11.5,
            fontweight='bold', color=TOP_TEXT)

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_aspect('equal', adjustable='box')
    ax.axis('off')
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.02, dpi=DPI_RESOLUTION)
    plt.close(fig)
    buf.seek(0)
    return buf

# ==========================================
# 4. ИЗГЛЕД ОТПРЕД (FRONT VIEW) - ВСИЧКИ СТРАНИ
# ==========================================
FRONT_FIG_W_IN = 7.5  # ширина на фигурата на изгледа отпред (2 страни на ред)


def generate_front_view_buf(layout, name="Елемент"):
    """Изгледът отпред с всички страни в една картинка."""
    return _front_view_buf(layout, _front_faces(layout), title=True)


def generate_front_view_row_bufs(layout, name="Елемент"):
    """Изгледът отпред по редове (по 2 страни), за да се разпределя по страниците без празни места."""
    faces = _front_faces(layout)
    return [_front_view_buf(layout, faces[i:i + 2], title=(i == 0)) for i in range(0, len(faces), 2)]


def _front_faces(layout):
    return [f for f in layout["faces"] if not f["name"].startswith("Край")]


def _front_view_buf(layout, faces, title=True):
    h_cm = layout["height_cm"]
    h_levels = layout["height_levels"]
    waler_levels = waler_heights_cm(h_cm, h_levels[0] if h_levels else 150)

    n_rows = int(math.ceil(len(faces) / 2.0))
    fig, axes = plt.subplots(n_rows, 2, figsize=(FRONT_FIG_W_IN, 2.9 * n_rows), dpi=DPI_RESOLUTION, squeeze=False)

    def draw_side_front(ax, face):
        side_len = sum(face["rows"][0])

        for edge, x in [("start", -10), ("end", side_len)]:
            kind = face[edge]
            if kind:
                color = COLOR_CORNER_EX if kind == "EX" else COLOR_CORNER_IN
                ax.add_patch(patches.Rectangle((x, 0), 10, h_cm, facecolor=color, edgecolor='black', linewidth=0.8, zorder=1))
                ax.text(x + 5, h_cm + 6, kind, ha='center', va='bottom', fontsize=5, fontweight='bold')

        waler_positions = []
        if side_len > NARROW_LIMIT_CM:
            waler_positions = waler_levels
            for w_y in waler_positions:
                if w_y < h_cm:
                    ax.add_patch(patches.Rectangle((-14, w_y - 4), side_len + 28, 8,
                                                   facecolor=COLOR_WALER, edgecolor='#1E8449', linewidth=0.6, alpha=0.9, zorder=2))

        top_y = h_cm + 20  # горна граница на чертежа
        curr_y = 0
        for h_val, row in zip(h_levels, face["rows"]):
            curr_x = 0
            # надписът е в средата на видимата част на панела (горният ред може да излиза над чертежа)
            label_y = (curr_y + min(curr_y + h_val, top_y)) / 2
            for w_val in row:
                rect = patches.Rectangle((curr_x, curr_y), w_val, h_val,
                                         linewidth=0.8, edgecolor=COLOR_PANEL_BORDER, facecolor=COLOR_PANEL, zorder=1)
                ax.add_patch(rect)
                text_str = f"{int(h_val)}/{int(w_val)}" if h_val != 60 else f"{int(w_val)}/60"
                ax.text(curr_x + w_val / 2, label_y, text_str,
                        ha='center', va='center', fontsize=5, color='#111111', fontweight='bold',
                        rotation=90, zorder=5,
                        bbox=dict(boxstyle='round,pad=0.15', facecolor='white', alpha=0.9, edgecolor='none'))
                curr_x += w_val
            curr_y += h_val

        dim_line_x = -24
        ax.plot([dim_line_x, dim_line_x], [0, h_cm], color='#333333', linewidth=0.8, zorder=3)
        ax.plot([dim_line_x - 2, dim_line_x + 2], [0, 0], color='#333333', linewidth=0.8)
        ax.text(dim_line_x - 4, 0, "0", ha='right', va='center', fontsize=5, fontweight='bold', color='#333333')

        ax.plot([dim_line_x - 2, dim_line_x + 2], [h_cm, h_cm], color='#333333', linewidth=0.8)
        ax.text(dim_line_x - 4, h_cm, f"{int(h_cm)}", ha='right', va='center', fontsize=5, fontweight='bold', color='#333333')

        for w_y in waler_positions:
            if 0 < w_y < h_cm:
                ax.plot([dim_line_x - 3, dim_line_x + 3], [w_y, w_y], color='#27AE60', linewidth=1.2, zorder=4)
                ax.text(dim_line_x - 5, w_y, f"{int(w_y)}", ha='right', va='center', fontsize=5, fontweight='bold', color='#1E8449')

        ax.set_xlim(-35, side_len + 20)
        ax.set_ylim(-10, top_y)
        ax.set_aspect('equal', adjustable='box')
        ax.axis('off')
        ax.set_title(f"Страна {face['name']} ({int(side_len)}x{int(h_cm)} cm)", fontsize=8, fontweight='bold')

    flat_axes = axes.flatten()
    for ax, face in zip(flat_axes, faces):
        draw_side_front(ax, face)
    for ax in flat_axes[len(faces):]:
        ax.axis('off')

    if title:
        fig.suptitle("Изглед отпред (Front View)", fontsize=9, fontweight='bold', y=0.99)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.05, dpi=DPI_RESOLUTION)
    plt.close(fig)
    buf.seek(0)
    return buf

# ==========================================
# 5. ИНДИВИДУАЛЕН 3D КОФРАЖЕН ИЗГЛЕД
# ==========================================
# Цветове на 3D изгледа (взети от еталона)
COLOR_3D_PANEL = '#E5BFBE'
COLOR_3D_CORNER = '#A0D784'
COLOR_3D_CORNER_IN = '#4A8F42'
COLOR_3D_CORNER_EDGE = '#4F8F3A'
COLOR_3D_CONCRETE = '#A7A7A9'
COLOR_3D_EDGE = '#211018'
COLOR_3D_GRID = (0.80, 0.83, 0.87)

# Камера по тип елемент (височина и посока на гледане), като в еталона:
# колона - дългата страна вляво; стени - срещу външния ъгъл / външната страна
VIEW_3D = {
    "column": (28, 32),
    "wall": (28, -62),
    "l_wall": (30, -130),
    "u_wall": (32, -115),
}


def generate_3d_axonometry_buf(layout, name="Елемент"):
    """
    3D изглед на елемент като в еталона: перспектива, реални пропорции, плътни цветове,
    бетон до височината на елемента и мрежа на земята. Ъглите стигат до горния край на панелите.
    Рисуват се само видимите и непокрити стени на кутиите (matplotlib няма z-buffer),
    а контурите са в същата колекция, за да се закриват от предните стени.
    """
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    from mpl_toolkits.mplot3d import proj3d
    from matplotlib.path import Path

    T = PANEL_T
    h = layout["height_cm"]
    top = sum(layout["height_levels"])  # горен край на панелите
    poly, place, corners = _plan_geometry(layout)
    elev, azim = VIEW_3D.get(layout["type"], (28, -62))

    # Кутии: (x0, y0, z0, dx, dy, dz, цвят, цвят на контура)
    boxes = []
    for face in layout["faces"]:
        x0, y0, axis, *rev = place[face["name"]]
        curr_z = 0
        for h_val, row in zip(layout["height_levels"], face["rows"]):
            s = 0
            for w_val in (row[::-1] if rev and rev[0] else row):
                if axis == 'x':
                    boxes.append((x0 + s, y0, curr_z, w_val, T, h_val, COLOR_3D_PANEL, COLOR_3D_EDGE))
                else:
                    boxes.append((x0, y0 + s, curr_z, T, w_val, h_val, COLOR_3D_PANEL, COLOR_3D_EDGE))
                s += w_val
            curr_z += h_val
    for kind, x, y in corners:
        col = COLOR_3D_CORNER if kind == "EX" else COLOR_3D_CORNER_IN
        boxes.append((x, y, 0, T, T, top, col, COLOR_3D_CORNER_EDGE))

    core = Path(poly)

    def in_box(p, skip=None):
        for j, (bx, by, bz, dx, dy, dz, *_) in enumerate(boxes):
            if j != skip and bx < p[0] < bx + dx and by < p[1] < by + dy and bz < p[2] < bz + dz:
                return True
        return False

    def solid_at(p, skip):
        return (0 < p[2] < h and core.contains_point(p[:2])) or in_box(p, skip)

    er, ea = np.radians(elev), np.radians(azim)
    eye = np.array([np.cos(er) * np.cos(ea), np.cos(er) * np.sin(ea), np.sin(er)])

    box_faces = [[] for _ in boxes]  # видимите стени на всяка кутия: (четириъгълник, цвят, контур, дебелина)
    for i, (bx, by, bz, dx, dy, dz, col, ecol) in enumerate(boxes):
        lo, hi = np.array([bx, by, bz]), np.array([bx + dx, by + dy, bz + dz])
        for ax_i in range(3):
            for sign in (-1, 1):
                normal = np.zeros(3)
                normal[ax_i] = sign
                if normal @ eye <= 0:
                    continue
                u, v = [k for k in range(3) if k != ax_i]
                plane = hi[ax_i] if sign > 0 else lo[ax_i]
                # стена, допряна до друга кутия или до бетона, не се вижда
                # проби до самите ръбове: и тясна открита ивица (напр. над бетона) прави стената видима
                covered = True
                for pu in (lo[u] + 0.5, (lo[u] + hi[u]) / 2, hi[u] - 0.5):
                    for pv in (lo[v] + 0.5, (lo[v] + hi[v]) / 2, hi[v] - 0.5):
                        p = np.zeros(3)
                        p[ax_i] = plane + sign * 0.5
                        p[u], p[v] = pu, pv
                        if not solid_at(p, i):
                            covered = False
                if covered:
                    continue
                quad = []
                for cu, cv in ((lo[u], lo[v]), (hi[u], lo[v]), (hi[u], hi[v]), (lo[u], hi[v])):
                    q = np.zeros(3)
                    q[ax_i], q[u], q[v] = plane, cu, cv
                    quad.append(q)
                box_faces[i].append((quad, col, ecol, 0.8 if ecol == COLOR_3D_EDGE else 0.5))

    # Ред на рисуване отзад напред. Кутиите не се пресичат и са успоредни на осите, затова
    # за всяка двойка, която се застъпва на екрана, има ос, по която едната е изцяло зад другата.
    right = np.array([-np.sin(ea), np.cos(ea), 0.0])
    up = np.cross(eye, right)

    def screen_bbox(b):
        bx, by, bz, dx, dy, dz = b[:6]
        pts = np.array([[x, y, z] for x in (bx, bx + dx) for y in (by, by + dy) for z in (bz, bz + dz)])
        u, v = pts @ right, pts @ up
        return u.min(), u.max(), v.min(), v.max()

    def behind(a, b):
        for k in range(3):
            a_lo, a_hi = a[k], a[k] + a[k + 3]
            b_lo, b_hi = b[k], b[k] + b[k + 3]
            if eye[k] > 1e-9 and a_hi <= b_lo + 1e-6:
                return True
            if eye[k] < -1e-9 and a_lo >= b_hi - 1e-6:
                return True
        return False

    shown = [i for i in range(len(boxes)) if box_faces[i]]
    bbs = {i: screen_bbox(boxes[i]) for i in shown}
    after = {i: set() for i in shown}   # i трябва да е преди всички в after[i]
    n_before = {i: 0 for i in shown}
    for ii, i in enumerate(shown):
        for j in shown[ii + 1:]:
            bi, bj = bbs[i], bbs[j]
            if bi[1] <= bj[0] or bj[1] <= bi[0] or bi[3] <= bj[2] or bj[3] <= bi[2]:
                continue
            if behind(boxes[i], boxes[j]):
                after[i].add(j)
                n_before[j] += 1
            elif behind(boxes[j], boxes[i]):
                after[j].add(i)
                n_before[i] += 1
    depth = {i: float(np.array(boxes[i][:3]) @ eye + np.array(boxes[i][3:6]) @ eye / 2) for i in shown}
    order, ready = [], sorted([i for i in shown if n_before[i] == 0], key=lambda i: depth[i])
    while ready:
        i = ready.pop(0)
        order.append(i)
        for j in after[i]:
            n_before[j] -= 1
            if n_before[j] == 0:
                ready.append(j)
        ready.sort(key=lambda k: depth[k])
    order += sorted(set(shown) - set(order), key=lambda i: depth[i])  # при цикъл - по дълбочина

    # Бетон: откритите странични стени (напр. при отворен край на стена) и горната плоскост.
    # Рисува се преди панелите - не ги закрива, а те могат да го закриват.
    polys, fcols, ecols, lws = [], [], [], []
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        length = math.hypot(x1 - x0, y1 - y0)
        if length == 0:
            continue
        nx, ny = (y1 - y0) / length, (x0 - x1) / length
        if core.contains_point(((x0 + x1) / 2 + nx, (y0 + y1) / 2 + ny)):
            nx, ny = -nx, -ny
        if nx * eye[0] + ny * eye[1] <= 0:
            continue
        samples = [(x0 + f * (x1 - x0) + nx * 0.5, y0 + f * (y1 - y0) + ny * 0.5, z)
                   for f in (0.1, 0.5, 0.9) for z in (0.1 * h, 0.5 * h, 0.9 * h)]
        if all(in_box(p) for p in samples):
            continue
        polys.append([[x0, y0, 0], [x1, y1, 0], [x1, y1, h], [x0, y0, h]])
        fcols.append(COLOR_3D_CONCRETE)
        ecols.append(COLOR_3D_CONCRETE)
        lws.append(0.5)
    polys.append([[x, y, h] for x, y in poly])
    fcols.append(COLOR_3D_CONCRETE)
    ecols.append(COLOR_3D_CONCRETE)
    lws.append(0.5)

    fig = plt.figure(figsize=(5, 5), dpi=DPI_RESOLUTION)
    ax = fig.add_subplot(111, projection='3d')
    ax.set_position([0, 0, 1, 1])
    ax.computed_zorder = False

    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    plan_span = max(max(xs) - min(xs), max(ys) - min(ys)) + 2 * T

    # Мрежа на земята, избледняваща с отдалечаването
    step = 100
    reach = max(700, int(math.ceil(plan_span / step)) * step + 400)
    segs, seg_cols = [], []
    ticks = np.arange(-reach, reach + step, step)
    pieces = np.arange(-reach, reach + 25, 25)
    for t in ticks:
        for s0, s1 in zip(pieces[:-1], pieces[1:]):
            for p0, p1 in (((cx + t, cy + s0), (cx + t, cy + s1)), ((cx + s0, cy + t), (cx + s1, cy + t))):
                mx, my = (p0[0] + p1[0]) / 2 - cx, (p0[1] + p1[1]) / 2 - cy
                fade = max(0.0, 1 - (np.hypot(mx, my) / reach) ** 2)
                segs.append([(*p0, 0), (*p1, 0)])
                seg_cols.append((*COLOR_3D_GRID, fade))
    grid = Line3DCollection(segs, colors=seg_cols, linewidths=0.5, zorder=1)
    grid.set_clip_on(False)
    ax.add_collection3d(grid)

    concrete = Poly3DCollection(polys, facecolors=fcols, edgecolors=ecols, linewidths=lws, zorder=2)
    concrete.set_sort_zpos(0)
    ax.add_collection3d(concrete)
    for rank, i in enumerate(order):
        quads, cols, eds, ws = zip(*box_faces[i])
        polys += quads
        ax.add_collection3d(Poly3DCollection(list(quads), facecolors=list(cols), edgecolors=list(eds),
                                             linewidths=list(ws), zorder=3 + rank * 1e-3))

    half = max(plan_span, top) / 2
    ax.set_xlim(cx - half, cx + half)
    ax.set_ylim(cy - half, cy + half)
    ax.set_zlim(0.5 * top - half, 0.5 * top + half)
    ax.set_proj_type('persp', focal_length=0.45)
    ax.view_init(elev=elev, azim=azim)
    ax.axis('off')

    # Мащаб и център: елементът да запълва около 88% от кадъра
    pts = np.array([q for quad in polys for q in quad])
    zoom, pos = 1.0, [0, 0, 1, 1]
    for _ in range(3):
        ax.set_box_aspect((1, 1, 1), zoom=zoom)
        ax.set_position(pos)
        fig.canvas.draw()
        px, py, _pz = proj3d.proj_transform(pts[:, 0], pts[:, 1], pts[:, 2], ax.get_proj())
        disp = ax.transData.transform(np.column_stack([px, py]))
        W, H = fig.bbox.width, fig.bbox.height
        zoom *= min(0.88 * W / np.ptp(disp[:, 0]), 0.88 * H / np.ptp(disp[:, 1]))
        pos = [pos[0] + (W / 2 - (disp[:, 0].min() + disp[:, 0].max()) / 2) / W,
               pos[1] + (H / 2 - (disp[:, 1].min() + disp[:, 1].max()) / 2) / H, 1, 1]

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI_RESOLUTION, facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return buf

# ==========================================
# 6. ГЕНЕРИРАНЕ НА ЦЕЛИЯ ДОКУМЕНТ
# ==========================================
def generate_pdf_drawings(pdf_elements, bom_summary, proj_info):
    has_dejavu = setup_pdf_fonts()
    font_name = 'DejaVuSans' if has_dejavu else 'Helvetica'
    font_bold = 'DejaVuSans-Bold' if has_dejavu else 'Helvetica-Bold'
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'PDFTitle', parent=styles['Heading1'],
        fontName=font_bold, fontSize=13, leading=16,
        textColor=colors.HexColor('#003366'), spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'PDFSubtitle', parent=styles['Normal'],
        fontName=font_name, fontSize=9, leading=12,
        textColor=colors.HexColor('#444444'), spaceAfter=8
    )

    section_style = ParagraphStyle('SectionLabel', parent=styles['Normal'], fontName=font_bold, fontSize=7.5,
                                   leading=10, textColor=colors.HexColor('#5B6B7A'), spaceAfter=4)
    cell_style = ParagraphStyle('CellText', parent=styles['Normal'], fontName=font_name, fontSize=8, leading=10)
    cell_bold_style = ParagraphStyle('CellTextBold', parent=styles['Normal'], fontName=font_bold, fontSize=8, leading=10, textColor=colors.white)

    story = []
    
    client = proj_info.get('client') or 'Няма посочен клиент'
    project = proj_info.get('project') or 'Обект TEKO'
    
    story.append(Paragraph("<b>КОФРАЖНА СИСТЕМА TEKO / TEKO FORMWORK SYSTEM</b>", title_style))
    story.append(Paragraph(f"<b>Обект:</b> {project} | <b>Клиент:</b> {client}", subtitle_style))
    story.append(Spacer(1, 8))

    # --- ОБОБЩЕНА КОЛИЧЕСТВЕНА СМЕТКА (PROJECT BOM) ---
    story.append(Paragraph("<b>Обобщена количествена сметка (Project BOM)</b>", title_style))
    story.append(Spacer(1, 4))
    
    table_data = [[
        Paragraph("<b>№</b>", cell_bold_style),
        Paragraph("<b>Артикул / Код</b>", cell_bold_style),
        Paragraph("<b>Система</b>", cell_bold_style),
        Paragraph("<b>Количество (бр.)</b>", cell_bold_style)
    ]]
    
    idx = 1
    for code, qty in sorted(bom_summary.items()):
        table_data.append([
            Paragraph(str(idx), cell_style),
            Paragraph(str(code), cell_style),
            Paragraph("TEKO", cell_style),
            Paragraph(str(qty), cell_style)
        ])
        idx += 1

    summary_table = Table(table_data, colWidths=[30, 270, 70, 110])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
    ]))
    
    story.append(summary_table)
    story.append(PageBreak())

    # --- ИНДИВИДУАЛНИ ЧЕРТЕЖИ И СПЕЦИФИКАЦИИ ---
    for idx, elem in enumerate(pdf_elements):
        w_type = str(elem.get('wall_type') or 'Стена')
        e_name = str(elem.get('name', f'Елемент {idx+1}'))
        layout = elem['layout']
        e_count = int(elem.get('count') or 1)

        story.append(Paragraph(f"<b>Чертеж и Спецификация: {e_name}</b>", title_style))
        story.append(Paragraph(f"Тип: {w_type} | Размери: {_dims_label(layout)} | Височина: {int(layout['height_cm'])} cm | "
                               f"Затворени краища: {_closed_label(layout)} | Брой: {e_count}", subtitle_style))
        story.append(Spacer(1, 4))

        top_buf = generate_top_view_buf(layout, e_name)
        front_bufs = generate_front_view_row_bufs(layout, e_name)
        ax_buf = generate_3d_axonometry_buf(layout, e_name)

        # Изглед отгоре вляво и 3D изглед вдясно, на един ред
        top_w, top_h = ImageReader(top_buf).getSize()
        top_buf.seek(0)
        img_w, img_h = 250, 250 * top_h / top_w
        if img_h > 300:
            img_w, img_h = img_w * 300 / img_h, 300
        img_top = RLImage(top_buf, width=img_w, height=img_h)

        ax_w, ax_h = ImageReader(ax_buf).getSize()
        ax_buf.seek(0)
        box = 275
        scale = min(box / ax_w, box / ax_h)
        img_ax = RLImage(ax_buf, width=ax_w * scale, height=ax_h * scale)

        views_table = Table([
            [Paragraph("TOP VIEW / ИЗГЛЕД ОТГОРЕ", section_style), Paragraph("3D VIEW / 3D ИЗГЛЕД", section_style)],
            [img_top, img_ax],
        ], colWidths=[260, 285])
        views_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, 1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'BOTTOM'),
            ('VALIGN', (0, 1), (-1, 1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(views_table)
        story.append(Spacer(1, 6))

        # Изглед отпред по редове (по 2 страни): всеки ред отива там, където има място,
        # без празно пространство, когато целият изглед не се събира на страницата
        pt_per_px = 420.0 / (FRONT_FIG_W_IN * DPI_RESOLUTION)  # еднакъв мащаб за всички редове
        for row_buf in front_bufs:
            row_w, row_h = ImageReader(row_buf).getSize()
            row_buf.seek(0)
            img_w, img_h = row_w * pt_per_px, row_h * pt_per_px
            if img_h > 680:
                img_w, img_h = img_w * 680 / img_h, 680
            row_table = Table([[RLImage(row_buf, width=img_w, height=img_h)]], colWidths=[480])
            row_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                ('TOPPADDING', (0,0), (-1,-1), 2),
            ]))
            story.append(row_table)
        story.append(Spacer(1, 6))

        story.append(Paragraph("<b>Необходим артикул за елемента</b>", ParagraphStyle('SubHeading', parent=title_style, fontSize=10, leading=12)))
        story.append(Spacer(1, 2))

        elem_bom = elem['bom']

        elem_table_data = [[
            Paragraph("<b>Артикул / Код</b>", cell_bold_style),
            Paragraph("<b>Количество (бр.)</b>", cell_bold_style)
        ]]
        
        for code, qty in sorted(elem_bom.items()):
            elem_table_data.append([
                Paragraph(str(code), cell_style),
                Paragraph(str(qty), cell_style)
            ])

        elem_table = Table(elem_table_data, colWidths=[300, 180])
        elem_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ]))
        
        story.append(elem_table)

        if idx < len(pdf_elements) - 1:
            story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    return buffer
