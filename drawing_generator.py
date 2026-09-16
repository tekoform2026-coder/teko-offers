import io
import os
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

# Висока резолюция за векторно изглеждащи растерни чертежи
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
COLOR_WALER = '#27AE60'         # Ригел AW (зелено)
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

def calculate_height_breakdown(height_cm):
    """Разбива височината на модули (150, 120, 60 cm)."""
    height_levels = []
    rem = float(height_cm)
    while rem >= 150:
        height_levels.append(150)
        rem -= 150
    while rem >= 120:
        height_levels.append(120)
        rem -= 120
    while rem >= 60:
        height_levels.append(60)
        rem -= 60
    if rem > 0:
        height_levels.append(rem)
    return height_levels

def calculate_panel_width_breakdown(width_cm):
    """Разбива ширината на стандартни модули."""
    panel_widths = [60, 35, 30, 25, 20]
    compensators = [15, 10, 5]
    remaining = float(width_cm)
    result = []
    
    for w in panel_widths:
        count = int(remaining // w)
        if count > 0:
            for _ in range(count):
                result.append(w)
            remaining -= count * w
            
    for c in compensators:
        count = int(remaining // c)
        if count > 0:
            for _ in range(count):
                result.append(c)
            remaining -= count * c
            
    if remaining > 0:
        result.append(remaining)
        
    return result

# ==========================================
# 1. ОБЩ 3D ИЗГЛЕД НА ЦЕЛИЯ ОБЕКТ (PROJECT 3D)
# ==========================================
def generate_overall_project_3d_buf(pdf_elements):
    """Чертае всички колони, стени и фундаменти в обща 3D координатна система."""
    fig = plt.figure(figsize=(7.5, 4.0), dpi=DPI_RESOLUTION)
    ax = fig.add_subplot(111, projection='3d')
    
    def draw_prism_3d(x0, y0, z0, dx, dy, dz, facecolor, edgecolor='#2C3E50', alpha=0.85):
        vertices = np.array([
            [x0, y0, z0], [x0+dx, y0, z0], [x0+dx, y0+dy, z0], [x0, y0+dy, z0],
            [x0, y0, z0+dz], [x0+dx, y0, z0+dz], [x0+dx, y0+dy, z0+dz], [x0, y0+dy, z0+dz]
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
        w_type = elem.get('type_bg') or elem.get('wall_type') or 'Стена'
        e_name = elem.get('name', f'E{idx+1}')

        # Бетонно ядро
        draw_prism_3d(pos_x, pos_y, 0, l_a, l_b if "Колона" in w_type else thick, h_cm, COLOR_CONCRETE, alpha=0.6)
        
        # Кофражни платна
        draw_prism_3d(pos_x - 10, pos_y - 10, 0, l_a + 20, 10, h_cm, COLOR_PANEL)
        draw_prism_3d(pos_x - 10, pos_y + (l_b if "Колона" in w_type else thick), 0, l_a + 20, 10, h_cm, COLOR_PANEL)
        
        # Ъглови профили
        draw_prism_3d(pos_x - 10, pos_y - 10, 0, 10, 10, h_cm, COLOR_CORNER_EX)
        draw_prism_3d(pos_x + l_a, pos_y - 10, 0, 10, 10, h_cm, COLOR_CORNER_EX)

        ax.text(pos_x + l_a/2, pos_y + (l_b/2 if "Колона" in w_type else thick/2), h_cm + 20, e_name, ha='center', va='bottom', fontsize=7, fontweight='bold')

        max_x = max(max_x, pos_x + l_a + 100)
        max_y = max(max_y, pos_y + (l_b if "Колона" in w_type else thick) + 100)
        max_z = max(max_z, h_cm + 50)

    ax.set_xlim(-50, max_x)
    ax.set_ylim(-50, max_y)
    ax.set_zlim(0, max_z)
    
    # Фиксиране на пропорциите в 3D (предотвратява деформацията)
    ax.set_box_aspect([max_x + 50, max_y + 50, max_z])
    
    ax.axis('off')
    ax.view_init(elev=28, azim=-55)
    ax.set_title("3D Общ кофражен план на обект (Project Overview)", fontsize=10, fontweight='bold', pad=10)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.05, dpi=DPI_RESOLUTION)
    plt.close(fig)
    buf.seek(0)
    return buf

# ==========================================
# 2. ИЗГЛЕД ОТГОРЕ (TOP VIEW)
# ==========================================
def generate_top_view_buf(wall_type, dim_a, dim_b, thickness, name="Елемент"):
    fig, ax = plt.subplots(figsize=(4.0, 2.6), dpi=DPI_RESOLUTION)
    
    a = float(dim_a or 100)
    b = float(dim_b or 100)
    t = float(thickness or 30)
    
    if wall_type in ["Колона", "Квадратна колона"]:
        ax.add_patch(patches.Rectangle((0, 0), a, b, facecolor=COLOR_CONCRETE, edgecolor='#2C3E50', linewidth=1.2))
        for x_pos, y_pos in [(-15, -15), (a, -15), (a, b), (-15, b)]:
            ax.add_patch(patches.Rectangle((x_pos, y_pos), 15, 15, facecolor=COLOR_CORNER_EX, edgecolor='black', linewidth=0.8))
            ax.text(x_pos+7.5, y_pos+7.5, "EX", ha='center', va='center', fontsize=6, fontweight='bold')

        w_a = calculate_panel_width_breakdown(a)
        curr_x = 0
        for w in w_a:
            ax.add_patch(patches.Rectangle((curr_x, -15), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(curr_x + w/2, -7.5, f"{int(w)}", ha='center', va='center', fontsize=6, fontweight='bold')
            ax.add_patch(patches.Rectangle((curr_x, b), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(curr_x + w/2, b + 7.5, f"{int(w)}", ha='center', va='center', fontsize=6, fontweight='bold')
            curr_x += w

        ax.set_xlim(-25, a + 25)
        ax.set_ylim(-25, b + 25)

    elif wall_type == "L-образна стена":
        poly = patches.Polygon([[0, 0], [a, 0], [a, t], [t, t], [t, b], [0, b]], 
                               facecolor=COLOR_CONCRETE, edgecolor='#2C3E50', linewidth=1.2)
        ax.add_patch(poly)
        
        ax.add_patch(patches.Rectangle((-15, -15), 15, 15, facecolor=COLOR_CORNER_EX, edgecolor='black', linewidth=0.8))
        ax.text(-7.5, -7.5, "EX", ha='center', va='center', fontsize=6, fontweight='bold')
        
        ax.add_patch(patches.Rectangle((t, t), 15, 15, facecolor=COLOR_CORNER_IN, edgecolor='black', linewidth=0.8))
        ax.text(t+7.5, t+7.5, "IN", ha='center', va='center', fontsize=6, fontweight='bold', color='white')

        ax.set_xlim(-25, a + 25)
        ax.set_ylim(-25, b + 25)

    else:
        ax.add_patch(patches.Rectangle((0, 0), a, t, facecolor=COLOR_CONCRETE, edgecolor='#2C3E50', linewidth=1.2))
        w_a = calculate_panel_width_breakdown(a)
        curr_x = 0
        for w in w_a:
            ax.add_patch(patches.Rectangle((curr_x, -15), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(curr_x + w/2, -7.5, f"{int(w)}", ha='center', va='center', fontsize=6, fontweight='bold')
            ax.add_patch(patches.Rectangle((curr_x, t), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(curr_x + w/2, t + 7.5, f"{int(w)}", ha='center', va='center', fontsize=6, fontweight='bold')
            curr_x += w

        ax.set_xlim(-20, a + 20)
        ax.set_ylim(-25, t + 25)

    ax.set_aspect('equal', adjustable='datalim')
    ax.axis('off')
    ax.set_title("Изглед отгоре (Top View)", fontsize=8, fontweight='bold', pad=4)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.05, dpi=DPI_RESOLUTION)
    plt.close(fig)
    buf.seek(0)
    return buf

# ==========================================
# 3. ИЗГЛЕД ОТПРЕД (FRONT VIEW) С ЯСНИ НАДПИСИ
# ==========================================
def generate_front_view_buf(wall_type, dim_a, dim_b, height_cm, name="Елемент"):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.0, 3.4), dpi=DPI_RESOLUTION)
    
    a = float(dim_a or 100)
    b = float(dim_b or 100)
    h_cm = float(height_cm or 300)
    h_levels = calculate_height_breakdown(h_cm)
    
    def draw_side_front(ax, side_len, title_label):
        w_panels = calculate_panel_width_breakdown(side_len)
        
        # EX ъгли
        ax.add_patch(patches.Rectangle((-10, 0), 10, h_cm, facecolor=COLOR_CORNER_EX, edgecolor='black', linewidth=0.8))
        ax.add_patch(patches.Rectangle((side_len, 0), 10, h_cm, facecolor=COLOR_CORNER_EX, edgecolor='black', linewidth=0.8))

        # Панели
        curr_y = 0
        for h_val in h_levels:
            curr_x = 0
            for w_val in w_panels:
                rect = patches.Rectangle((curr_x, curr_y), w_val, h_val, 
                                         linewidth=0.8, edgecolor=COLOR_PANEL_BORDER, facecolor=COLOR_PANEL)
                ax.add_patch(rect)
                
                # ИЗЧИСТЕНИ НАДПИСИ С КРИСТАЛЕН ФОН
                text_str = f"{int(w_val)}/{int(h_val)}"
                font_sz = 6.5 if w_val >= 35 else (5.5 if w_val >= 20 else 4.5)
                
                ax.text(curr_x + w_val / 2, curr_y + h_val / 2, text_str,
                        ha='center', va='center', fontsize=font_sz, color='#111111', fontweight='bold', 
                        rotation=90 if w_val < 35 else 0,
                        bbox=dict(boxstyle='round,pad=0.15', facecolor='white', alpha=0.75, edgecolor='none'))
                
                curr_x += w_val
            curr_y += h_val

        # Ригели AW
        waler_positions = [h for h in [50, 120, 180, 240, 300] if h < h_cm]
        for w_y in waler_positions:
            ax.add_patch(patches.Rectangle((-14, w_y - 4), side_len + 28, 8, 
                                     facecolor=COLOR_WALER, edgecolor='#1E8449', linewidth=0.6, alpha=0.9, zorder=3))

        ax.set_xlim(-20, side_len + 20)
        ax.set_ylim(-10, h_cm + 15)
        ax.set_aspect('equal', adjustable='datalim')
        ax.axis('off')
        ax.set_title(f"Страна {title_label} ({int(side_len)}x{int(h_cm)} cm)", fontsize=8, fontweight='bold')

    draw_side_front(ax1, a, "A")
    draw_side_front(ax2, b, "B" if wall_type in ["L-образна стена", "Колона", "Квадратна колона"] else "A1")

    fig.suptitle("Изглед отпред (Front View)", fontsize=9, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.05, dpi=DPI_RESOLUTION)
    plt.close(fig)
    buf.seek(0)
    return buf

# ==========================================
# 4. ИНДИВИДУАЛЕН 3D КОФРАЖЕН ИЗГЛЕД
# ==========================================
def generate_3d_axonometry_buf(wall_type, dim_a, dim_b, height_cm, thickness, name="Елемент"):
    fig = plt.figure(figsize=(4.0, 2.6), dpi=DPI_RESOLUTION)
    ax = fig.add_subplot(111, projection='3d')
    
    a = float(dim_a or 100)
    b = float(dim_b or 100)
    h = float(height_cm or 270)
    t = float(thickness or 30)
    
    dim_y = b if "Колона" in wall_type else t

    def draw_prism_3d(x0, y0, z0, dx, dy, dz, facecolor, edgecolor='#2C3E50', alpha=0.85):
        vertices = np.array([
            [x0, y0, z0], [x0+dx, y0, z0], [x0+dx, y0+dy, z0], [x0, y0+dy, z0],
            [x0, y0, z0+dz], [x0+dx, y0, z0+dz], [x0+dx, y0+dy, z0+dz], [x0, y0+dy, z0+dz]
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

    # Бетонно ядро
    draw_prism_3d(0, 0, 0, a, dim_y, h, COLOR_CONCRETE, alpha=0.5)

    # Кофражни платна
    draw_prism_3d(-12, -12, 0, a + 24, 12, h, COLOR_PANEL)
    draw_prism_3d(-12, dim_y, 0, a + 24, 12, h, COLOR_PANEL)
    draw_prism_3d(-12, 0, 0, 12, dim_y, h, COLOR_PANEL)
    draw_prism_3d(a, 0, 0, 12, dim_y, h, COLOR_PANEL)

    # 4 Ъглови профила EX
    for xc, yc in [(-12, -12), (a, -12), (a, dim_y), (-12, dim_y)]:
        draw_prism_3d(xc, yc, 0, 12, 12, h, COLOR_CORNER_EX)

    ax.set_xlim(-30, a + 30)
    ax.set_ylim(-30, dim_y + 30)
    ax.set_zlim(0, h + 20)
    
    # Фиксиране на 3D пропорциите, за да не се сплесква геометрията
    ax.set_box_aspect([a + 60, dim_y + 60, h + 20])
    
    ax.axis('off')
    ax.view_init(elev=22, azim=-45)
    ax.set_title("3D Изометрия (3D View)", fontsize=8, fontweight='bold', pad=2)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.05, dpi=DPI_RESOLUTION)
    plt.close(fig)
    buf.seek(0)
    return buf

# ==========================================
# 5. СПЕЦИФИКАЦИЯ ЗА ЕЛЕМЕНТА
# ==========================================
def calculate_element_bom(wall_type, dim_a, dim_b, height_cm):
    bom = {}
    h_levels = calculate_height_breakdown(height_cm)
    w_a = calculate_panel_width_breakdown(dim_a)
    w_b = calculate_panel_width_breakdown(dim_b if dim_b else dim_a)
    
    for h in h_levels:
        for w in w_a + w_b:
            code = f"Панел ТК {int(w)}/{int(h)}"
            bom[code] = bom.get(code, 0) + 2

    if wall_type == "L-образна стена":
        bom["Външен ъгъл EX"] = len(h_levels)
        bom["Вътрешен ъгъл IN"] = len(h_levels)
        bom["Ригел AW 100/200"] = len(h_levels) * 4
    elif wall_type in ["Колона", "Квадратна колона"]:
        bom["Външен ъгъл EX"] = len(h_levels) * 4
        bom["Стега за колона"] = len(h_levels) * 8
        bom["Ригел AW 100"] = len(h_levels) * 4
    else:
        bom["Ригел AW 200"] = len(h_levels) * 2
        bom["Стега за стена"] = len(h_levels) * 6

    bom["Вертикализатор PP"] = 2
    return bom

# ==========================================
# 6. ГЕНЕРИРАНЕ НА ЦЕЛИЯ PDF ДОКУМЕНТ
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

    cell_style = ParagraphStyle('CellText', parent=styles['Normal'], fontName=font_name, fontSize=8, leading=10)
    cell_bold_style = ParagraphStyle('CellTextBold', parent=styles['Normal'], fontName=font_bold, fontSize=8, leading=10, textColor=colors.white)

    story = []
    
    client = proj_info.get('client', 'Клиент')
    project = proj_info.get('project', 'Обект TEKO')
    
    # 1. СТРАНИЦА: ОБЩА СМЕТКА + ОБЩ 3D МОДЕЛ НА ЦЕЛИЯ ОБЕКТ
    story.append(Paragraph("<b>КОФРАЖНА СИСТЕМА TEKO / TEKO FORMWORK SYSTEM</b>", title_style))
    story.append(Paragraph(f"<b>Обект:</b> {project} | <b>Клиент:</b> {client}", subtitle_style))
    story.append(Spacer(1, 4))
    
    # ОБЩ 3D МОДЕЛ НА ОБЕКТА
    overall_3d_buf = generate_overall_project_3d_buf(pdf_elements)
    rl_overall_3d = RLImage(overall_3d_buf, width=490, height=261)
    story.append(rl_overall_3d)
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>Обобщена количествена сметка (Project BOM)</b>", title_style))
    
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
        
    t_summary = Table(table_data, colWidths=[30, 260, 100, 100])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9F9')])
    ]))
    story.append(t_summary)
    story.append(PageBreak())

    # 2. ВСЕКИ ЕЛЕМЕНТ НА ОТДЕЛНА СТРАНИЦА
    for elem in pdf_elements:
        e_name = elem.get('name', 'Елемент')
        w_type = elem.get('type_bg') or elem.get('wall_type') or 'Стена'
        l_a = elem.get('length_a_cm') or elem.get('length_cm') or 100
        l_b = elem.get('length_b_cm') or elem.get('width_cm') or l_a
        h_cm = elem.get('height_cm') or 300
        thick = elem.get('thickness_cm') or 30

        story.append(Paragraph(f"<b>Чертеж и Спецификация: {e_name}</b>", title_style))
        story.append(Paragraph(f"Тип: {w_type} | Размери: {int(l_a)}x{int(l_b)} cm | Височина: {int(h_cm)} cm", subtitle_style))
        
        # Изглед отгоре + 3D Изометрия (Рамо до рамо)
        buf_top = generate_top_view_buf(w_type, l_a, l_b, thick, name=e_name)
        buf_axon = generate_3d_axonometry_buf(w_type, l_a, l_b, h_cm, thick, name=e_name)
        
        rl_top = RLImage(buf_top, width=240, height=156)
        rl_axon = RLImage(buf_axon, width=240, height=156)
        
        row_table = Table([[rl_top, rl_axon]], colWidths=[245, 245])
        row_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(row_table)
        story.append(Spacer(1, 4))

        # Изглед отпред (Front View)
        buf_front = generate_front_view_buf(w_type, l_a, l_b, h_cm, name=e_name)
        rl_front = RLImage(buf_front, width=490, height=208)
        story.append(rl_front)
        story.append(Spacer(1, 6))

        # Таблица с количества за елемента
        elem_bom = calculate_element_bom(w_type, l_a, l_b, h_cm)
        
        e_table_data = [[
            Paragraph("<b>Необходим артикул за елемента</b>", cell_bold_style),
            Paragraph("<b>Количество (бр.)</b>", cell_bold_style)
        ]]
        for item_code, item_qty in elem_bom.items():
            e_table_data.append([
                Paragraph(item_code, cell_style),
                Paragraph(str(item_qty), cell_style)
            ])
            
        t_elem = Table(e_table_data, colWidths=[350, 140])
        t_elem.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E4053')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F4F6F7')])
        ]))
        story.append(t_elem)
        story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
