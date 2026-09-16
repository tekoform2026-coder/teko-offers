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

# Висока разделителна способност за кристална яснота
DPI_RESOLUTION = 300

# Настройки на шрифтовете
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
matplotlib.rcParams['font.family'] = 'sans-serif'

# Цветова палитра (стандарт TEKO / PERI / Doka)
COLOR_PANEL = '#F5B7B1'        # Светлорозов цвят за панели
COLOR_PANEL_BORDER = '#78281F' # Тъмночервен кант за контраст
COLOR_CORNER_EX = '#82E0AA'    # Светлозелено за външен ъгъл EX
COLOR_CORNER_IN = '#27AE60'    # Тъмнозелено за вътрешен ъгъл IN
COLOR_WALER = '#2ECC71'        # Яркозелено за ригели AW
COLOR_CONCRETE = '#D5D8DC'     # Сиво за бетонната сърцевина

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
    """Разбива височината на стандартни модули (150, 120, 60 cm)."""
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
    """Разбива ширината на стандартни ширини на панели."""
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
# 1. ИЗГЛЕД ОТГОРЕ (TOP VIEW)
# ==========================================
def generate_top_view_buf(wall_type, dim_a, dim_b, thickness, name="Елемент"):
    fig, ax = plt.subplots(figsize=(4.5, 3.0), dpi=DPI_RESOLUTION)
    
    a = float(dim_a or 100)
    b = float(dim_b or 100)
    t = float(thickness or 30)
    
    if wall_type in ["Колона", "Квадратна колона"]:
        # Бетонно ядро
        ax.add_patch(patches.Rectangle((0, 0), a, b, facecolor=COLOR_CONCRETE, edgecolor='#2C3E50', linewidth=1.5))
        # 4 броя EX ъгли
        for x_pos, y_pos in [(-15, -15), (a, -15), (a, b), (-15, b)]:
            ax.add_patch(patches.Rectangle((x_pos, y_pos), 15, 15, facecolor=COLOR_CORNER_EX, edgecolor='black', linewidth=1.0))
            ax.text(x_pos+7.5, y_pos+7.5, "EX", ha='center', va='center', fontsize=7, fontweight='bold')

        # Панели по страните
        w_a = calculate_panel_width_breakdown(a)
        curr_x = 0
        for w in w_a:
            ax.add_patch(patches.Rectangle((curr_x, -15), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=1.0))
            ax.text(curr_x + w/2, -7.5, f"{int(w)}", ha='center', va='center', fontsize=6.5, fontweight='bold')
            ax.add_patch(patches.Rectangle((curr_x, b), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=1.0))
            ax.text(curr_x + w/2, b + 7.5, f"{int(w)}", ha='center', va='center', fontsize=6.5, fontweight='bold')
            curr_x += w

        ax.set_xlim(-25, a + 25)
        ax.set_ylim(-25, b + 25)

    elif wall_type == "L-образна стена":
        poly = patches.Polygon([[0, 0], [a, 0], [a, t], [t, t], [t, b], [0, b]], 
                               facecolor=COLOR_CONCRETE, edgecolor='#2C3E50', linewidth=1.5)
        ax.add_patch(poly)
        
        ax.add_patch(patches.Rectangle((-15, -15), 15, 15, facecolor=COLOR_CORNER_EX, edgecolor='black', linewidth=1.0))
        ax.text(-7.5, -7.5, "EX", ha='center', va='center', fontsize=7, fontweight='bold')
        
        ax.add_patch(patches.Rectangle((t, t), 15, 15, facecolor=COLOR_CORNER_IN, edgecolor='black', linewidth=1.0))
        ax.text(t+7.5, t+7.5, "IN", ha='center', va='center', fontsize=7, fontweight='bold', color='white')

        ax.set_xlim(-25, a + 25)
        ax.set_ylim(-25, b + 25)

    else: # Прави стени
        ax.add_patch(patches.Rectangle((0, 0), a, t, facecolor=COLOR_CONCRETE, edgecolor='#2C3E50', linewidth=1.5))
        w_a = calculate_panel_width_breakdown(a)
        curr_x = 0
        for w in w_a:
            ax.add_patch(patches.Rectangle((curr_x, -15), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=1.0))
            ax.text(curr_x + w/2, -7.5, f"{int(w)}", ha='center', va='center', fontsize=6.5, fontweight='bold')
            ax.add_patch(patches.Rectangle((curr_x, t), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=1.0))
            ax.text(curr_x + w/2, t + 7.5, f"{int(w)}", ha='center', va='center', fontsize=6.5, fontweight='bold')
            curr_x += w

        ax.set_xlim(-20, a + 20)
        ax.set_ylim(-25, t + 25)

    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title("Изглед отгоре (Top View)", fontsize=8.5, fontweight='bold', pad=4)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=DPI_RESOLUTION)
    plt.close(fig)
    buf.seek(0)
    return buf

# ==========================================
# 2. ИЗГЛЕД ОТПРЕД (FRONT VIEW)
# ==========================================
def generate_front_view_buf(wall_type, dim_a, dim_b, height_cm, name="Елемент"):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.0, 3.6), dpi=DPI_RESOLUTION)
    
    a = float(dim_a or 100)
    b = float(dim_b or 100)
    h_cm = float(height_cm or 300)
    h_levels = calculate_height_breakdown(h_cm)
    
    def draw_side_front(ax, side_len, title_label):
        w_panels = calculate_panel_width_breakdown(side_len)
        
        # EX ъглови профили по страните
        ax.add_patch(patches.Rectangle((-10, 0), 10, h_cm, facecolor=COLOR_CORNER_EX, edgecolor='black', linewidth=1.0))
        ax.add_patch(patches.Rectangle((side_len, 0), 10, h_cm, facecolor=COLOR_CORNER_EX, edgecolor='black', linewidth=1.0))

        # Панели
        curr_y = 0
        for h_val in h_levels:
            curr_x = 0
            for w_val in w_panels:
                rect = patches.Rectangle((curr_x, curr_y), w_val, h_val, 
                                         linewidth=1.0, edgecolor=COLOR_PANEL_BORDER, facecolor=COLOR_PANEL)
                ax.add_patch(rect)
                text_str = f"{int(w_val)}/{int(h_val)}"
                
                # Ясно четим текст
                font_sz = 6.5 if w_val >= 25 else 5.5
                ax.text(curr_x + w_val / 2, curr_y + h_val / 2, text_str,
                        ha='center', va='center', fontsize=font_sz, color='#4A235A', fontweight='bold', rotation=90)
                curr_x += w_val
            curr_y += h_val

        # Ригели AW
        waler_positions = [h for h in [50, 120, 180, 240, 300] if h < h_cm]
        for w_y in waler_positions:
            ax.add_patch(patches.Rectangle((-14, w_y - 4), side_len + 28, 8, 
                                     facecolor=COLOR_WALER, edgecolor='#1E8449', linewidth=0.8, alpha=0.9, zorder=3))

        ax.set_xlim(-22, side_len + 22)
        ax.set_ylim(-12, h_cm + 18)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title(f"Страна {title_label} ({int(side_len)}x{int(h_cm)} cm)", fontsize=8, fontweight='bold')

    draw_side_front(ax1, a, "A")
    draw_side_front(ax2, b, "B" if wall_type in ["L-образна стена", "Колона", "Квадратна колона"] else "A1")

    fig.suptitle("Изглед отпред (Front View)", fontsize=9.5, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=DPI_RESOLUTION)
    plt.close(fig)
    buf.seek(0)
    return buf

# ==========================================
# 3. 3D ИЗОМЕТРИЧЕН ИЗГЛЕД (3D VIEW)
# ==========================================
def generate_3d_axonometry_buf(wall_type, dim_a, dim_b, height_cm, thickness, name="Елемент"):
    fig = plt.figure(figsize=(4.5, 3.0), dpi=DPI_RESOLUTION)
    ax = fig.add_subplot(111, projection='3d')
    
    a = float(dim_a or 100) / 10.0
    b = float(dim_b or 100) / 10.0
    h = float(height_cm or 270) / 10.0
    t = float(thickness or 30) / 10.0
    
    def draw_prism_3d(x0, y0, z0, dx, dy, dz, facecolor, edgecolor='#2C3E50'):
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
        poly = Poly3DCollection(faces, facecolors=facecolor, edgecolors=edgecolor, linewidths=0.6, alpha=0.85)
        ax.add_collection3d(poly)

    if wall_type == "L-образна стена":
        draw_prism_3d(0, 0, 0, a, t, h, COLOR_PANEL)
        draw_prism_3d(0, t, 0, t, max(b - t, 1.0), h, COLOR_PANEL)
        draw_prism_3d(-1.5, -1.5, 0, 1.5, 1.5, h, COLOR_CORNER_EX)
    else:
        draw_prism_3d(0, 0, 0, a, b, h, COLOR_PANEL)
        draw_prism_3d(-1.5, -1.5, 0, 1.5, 1.5, h, COLOR_CORNER_EX)
        draw_prism_3d(a, -1.5, 0, 1.5, 1.5, h, COLOR_CORNER_EX)

    ax.set_xlim(-3, max(a, b) + 3)
    ax.set_ylim(-3, max(a, b) + 3)
    ax.set_zlim(0, h + 2)
    ax.axis('off')
    ax.view_init(elev=22, azim=-40)
    ax.set_title("3D Изометрия (3D View)", fontsize=8.5, fontweight='bold', pad=2)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=DPI_RESOLUTION)
    plt.close(fig)
    buf.seek(0)
    return buf

# ==========================================
# 4. СПЕЦИФИКАЦИЯ ЗА ЕЛЕМЕНТА
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
# 5. ГЕНЕРИРАНЕ НА ЦЕЛИЯ PDF ДОКУМЕНТ
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
        fontName=font_bold, fontSize=14, leading=18,
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
    
    # 1. СТРАНИЦА: ОБЩА КОЛИЧЕСТВЕНА СМЕТКА
    story.append(Paragraph("<b>КОФРАЖНА СИСТЕМА TEKO / TEKO FORMWORK SYSTEM</b>", title_style))
    story.append(Paragraph(f"<b>Обект:</b> {project} | <b>Клиент:</b> {client}", subtitle_style))
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
        
        rl_top = RLImage(buf_top, width=235, height=140)
        rl_axon = RLImage(buf_axon, width=235, height=140)
        
        row_table = Table([[rl_top, rl_axon]], colWidths=[240, 240])
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
        rl_front = RLImage(buf_front, width=485, height=210)
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
            
        t_elem = Table(e_table_data, colWidths=[345, 140])
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
