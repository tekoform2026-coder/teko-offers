import io
import os
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Задаване на шрифт с поддръжка на кирилица за Matplotlib
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
matplotlib.rcParams['font.family'] = 'sans-serif'

# Цветова палитра според професионалните стандарти (PERI / Doka / TEKO)
COLOR_PANEL = '#F5B7B1'       # Розов цвят за кофражни панели
COLOR_PANEL_BORDER = '#78281F'# Тъмночервен кант за панелите
COLOR_CORNER_EX = '#82E0AA'   # Светлозелено за външен ъгъл EX
COLOR_CORNER_IN = '#27AE60'   # Тъмнозелено за вътрешен ъгъл IN
COLOR_WALER = '#2ECC71'       # Зелен цвят за ригели (AW)
COLOR_CONCRETE = '#EAEDED'    # Светлосиво за бетонната сърцевина

def setup_pdf_fonts():
    """Регистрира кирилски шрифт в ReportLab от пакета matplotlib."""
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
    """Разбива височината на стандартни височини на панели (150cm, 120cm, 60cm)."""
    height_levels = []
    rem = height_cm
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
    """Разбива дължината на стандартни ширини на панели (60, 35, 30, 25, 20 cm)."""
    panel_widths = [60, 35, 30, 25, 20]
    compensators = [15, 10, 5]
    remaining = width_cm
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
# 1. ЧЕРТАНЕ НА ИЗГЛЕД ОТГОРЕ (TOP VIEW)
# ==========================================
def generate_top_view(wall_type, dim_a, dim_b, dim_c, thickness, name="Елемент"):
    fig, ax = plt.subplots(figsize=(7, 4), dpi=300)
    
    a = float(dim_a or 100)
    b = float(dim_b or 100)
    t = float(thickness or 30)
    
    if wall_type == "L-образна стена":
        # Бетонна сърцевина
        poly = patches.Polygon([[0, 0], [a, 0], [a, t], [t, t], [t, b], [0, b]], 
                               facecolor=COLOR_CONCRETE, edgecolor='#333333', linewidth=1.5)
        ax.add_patch(poly)
        
        # Външни / Вътрешни ъгли
        ax.add_patch(patches.Rectangle((-15, -15), 15, 15, facecolor=COLOR_CORNER_EX, edgecolor='black'))
        ax.text(-7.5, -7.5, "EX", ha='center', va='center', fontsize=7, fontweight='bold')
        
        ax.add_patch(patches.Rectangle((t, t), 15, 15, facecolor=COLOR_CORNER_IN, edgecolor='black'))
        ax.text(t+7.5, t+7.5, "IN", ha='center', va='center', fontsize=7, fontweight='bold', color='white')

        # Панели по рамо А (външни и вътрешни)
        w_outer_a = calculate_panel_width_breakdown(a)
        curr_x = 0
        for w in w_outer_a:
            ax.add_patch(patches.Rectangle((curr_x, -15), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER))
            ax.text(curr_x + w/2, -7.5, f"{int(w)}", ha='center', va='center', fontsize=6)
            curr_x += w
            
        w_inner_a = calculate_panel_width_breakdown(max(a - t - 15, 20))
        curr_x = t + 15
        for w in w_inner_a:
            ax.add_patch(patches.Rectangle((curr_x, t), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER))
            ax.text(curr_x + w/2, t + 7.5, f"{int(w)}", ha='center', va='center', fontsize=6)
            curr_x += w

        # Размери
        ax.text(a/2, t + 30, f"A {int(a)} cm", ha='center', va='center', fontsize=9, fontweight='bold')
        ax.text(-35, b/2, f"B {int(b)} cm", ha='center', va='center', fontsize=9, fontweight='bold', rotation=90)

    elif wall_type == "Колона":
        # Правоъгълна колона с 4 EX ъгъла
        ax.add_patch(patches.Rectangle((0, 0), a, b, facecolor=COLOR_CONCRETE, edgecolor='#333333', linewidth=1.5))
        
        # 4-те EX ъгъла по краищата
        for x_pos, y_pos in [(-15, -15), (a, -15), (a, b), (-15, b)]:
            ax.add_patch(patches.Rectangle((x_pos, y_pos), 15, 15, facecolor=COLOR_CORNER_EX, edgecolor='black'))
            ax.text(x_pos+7.5, y_pos+7.5, "EX", ha='center', va='center', fontsize=6, fontweight='bold')

        # Панели Страна А и Страна B
        w_a = calculate_panel_width_breakdown(a)
        curr_x = 0
        for w in w_a:
            ax.add_patch(patches.Rectangle((curr_x, -15), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER))
            ax.text(curr_x + w/2, -7.5, f"{int(w)}", ha='center', va='center', fontsize=6)
            ax.add_patch(patches.Rectangle((curr_x, b), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER))
            ax.text(curr_x + w/2, b + 7.5, f"{int(w)}", ha='center', va='center', fontsize=6)
            curr_x += w

        ax.text(a/2, b + 30, f"{int(a)} cm", ha='center', va='center', fontsize=9, fontweight='bold')
        ax.text(-35, b/2, f"{int(b)} cm", ha='center', va='center', fontsize=9, fontweight='bold', rotation=90)

    else: # Прав кофражен щит / Стена
        ax.add_patch(patches.Rectangle((0, 0), a, t, facecolor=COLOR_CONCRETE, edgecolor='#333333'))
        w_a = calculate_panel_width_breakdown(a)
        curr_x = 0
        for w in w_a:
            ax.add_patch(patches.Rectangle((curr_x, -15), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER))
            ax.text(curr_x + w/2, -7.5, f"{int(w)}", ha='center', va='center', fontsize=6)
            ax.add_patch(patches.Rectangle((curr_x, t), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER))
            ax.text(curr_x + w/2, t + 7.5, f"{int(w)}", ha='center', va='center', fontsize=6)
            curr_x += w
        ax.text(a/2, t + 25, f"Дължина A: {int(a)} cm", ha='center', va='center', fontsize=9, fontweight='bold')

    ax.autoscale_view()
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title(f"ИЗГЛЕД ОТГОРЕ / TOP VIEW - {name}", fontsize=10, fontweight='bold', pad=10)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=300)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf)

# ==========================================
# 2. ЧЕРТАНЕ НА ИЗГЛЕД ОТПРЕД (FRONT VIEW)
# ==========================================
def generate_front_view(wall_type, dim_a, dim_b, height_cm, name="Елемент"):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8, 4.5), dpi=300)
    
    a = float(dim_a or 100)
    b = float(dim_b or 100)
    h_levels = calculate_height_breakdown(height_cm)
    
    def draw_side_front(ax, side_len, title_label):
        w_panels = calculate_panel_width_breakdown(side_len)
        
        # Чертане на EX профил отляво и отдясно
        ax.add_patch(patches.Rectangle((-10, 0), 10, height_cm, facecolor=COLOR_CORNER_EX, edgecolor='black'))
        ax.text(-5, height_cm + 10, "EX", ha='center', va='center', fontsize=7, fontweight='bold')
        
        ax.add_patch(patches.Rectangle((side_len, 0), 10, height_cm, facecolor=COLOR_CORNER_EX, edgecolor='black'))
        ax.text(side_len + 5, height_cm + 10, "EX", ha='center', va='center', fontsize=7, fontweight='bold')

        # Чертане на решетката от панели
        curr_y = 0
        for h_val in h_levels:
            curr_x = 0
            for w_val in w_panels:
                rect = patches.Rectangle((curr_x, curr_y), w_val, h_val, 
                                         linewidth=1.0, edgecolor=COLOR_PANEL_BORDER, facecolor=COLOR_PANEL)
                ax.add_patch(rect)
                
                text_str = f"{int(h_val)}/{int(w_val)}"
                font_sz = 6 if w_val >= 25 else 4.5
                ax.text(curr_x + w_val / 2, curr_y + h_val / 2, text_str,
                        ha='center', va='center', fontsize=font_sz, color='#4A235A', fontweight='bold', rotation=90)
                curr_x += w_val
            curr_y += h_val

        # Добавяне на хоризонтални РИГЕЛИ (AW)
        waler_positions = [h for h in [50, 120, 170, 240, 290] if h < height_cm]
        for w_y in waler_positions:
            ax.add_patch(patches.Rectangle((-15, w_y - 5), side_len + 30, 10, 
                                     facecolor=COLOR_WALER, edgecolor='#1E8449', alpha=0.85, zorder=3))

        ax.set_xlim(-25, side_len + 25)
        ax.set_ylim(-15, height_cm + 25)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title(f"Страна {title_label} ({int(side_len)}x{int(height_cm)} cm)", fontsize=9, fontweight='bold')

    draw_side_front(ax1, a, "A")
    draw_side_front(ax2, b, "B" if wall_type in ["L-образна стена", "Колона"] else "A1")

    fig.suptitle(f"ИЗГЛЕД ОТПРЕД / FRONT VIEW - {name}", fontsize=11, fontweight='bold')
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=300)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf)

# ==========================================
# 3. ЧЕРТАНЕ НА 3D ИЗОМЕТРИЧЕН ИЗГЛЕД
# ==========================================
def generate_3d_axonometry(wall_type, dim_a, dim_b, height_cm, thickness, name="Елемент"):
    fig = plt.figure(figsize=(6, 4.5), dpi=300)
    ax = fig.add_subplot(111, projection='3d')
    
    a = float(dim_a or 100) / 10.0
    b = float(dim_b or 100) / 10.0
    h = float(height_cm or 270) / 10.0
    t = float(thickness or 30) / 10.0
    
    def draw_prism(x0, y0, z0, dx, dy, dz, color, alpha=0.9):
        # 8 върха на паралелепипед
        vertices = [
            [x0, y0, z0], [x0+dx, y0, z0], [x0+dx, y0+dy, z0], [x0, y0+dy, z0],
            [x0, y0, z0+dz], [x0+dx, y0, z0+dz], [x0+dx, y0+dy, z0+dz], [x0, y0+dy, z0+dz]
        ]
        faces = [
            [0,1,2,3], [4,5,6,7], [0,1,5,4], 
            [2,3,7,6], [0,3,7,4], [1,2,6,5]
        ]
        for face in faces:
            x_f = [vertices[i][0] for i in face]
            y_f = [vertices[i][1] for i in face]
            z_f = [vertices[i][2] for i in face]
            ax.plot_surface(
                plt.np.array([x_f[:2], x_f[3:1:-1]]),
                plt.np.array([y_f[:2], y_f[3:1:-1]]),
                plt.np.array([z_f[:2], z_f[3:1:-1]]),
                color=color, alpha=alpha, edgecolor='black', linewidth=0.5
            )

    if wall_type == "L-образна стена":
        draw_prism(0, 0, 0, a, t, h, COLOR_PANEL)
        draw_prism(0, t, 0, t, b - t, h, COLOR_PANEL)
        draw_prism(0, 0, 0, t, t, h, COLOR_CORNER_EX) # EX ъгъл
    else:
        draw_prism(0, 0, 0, a, b, h, COLOR_PANEL)

    ax.set_title(f"3D ИЗГЛЕД / 3D VIEW - {name}", fontsize=10, fontweight='bold')
    ax.axis('off')
    ax.view_init(elev=25, azim=-45)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=300)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf)

# ==========================================
# 4. КАЛКУЛАЦИЯ НА КОЛИЧЕСТВА (BOM)
# ==========================================
def calculate_element_bom(wall_type, dim_a, dim_b, height_cm):
    """Изчислява количествената сметка за конкретния елемент."""
    bom = {}
    h_levels = calculate_height_breakdown(height_cm)
    w_a = calculate_panel_width_breakdown(dim_a)
    w_b = calculate_panel_width_breakdown(dim_b if dim_b else dim_a)
    
    # Броене на панелите за двете страни
    for h in h_levels:
        for w in w_a + w_b:
            code = f"Панел ТК {int(h)}/{int(w)}"
            bom[code] = bom.get(code, 0) + 2

    # Добавяне на ъгли и ригели
    if wall_type == "L-образна стена":
        bom["Външен ъгъл EX240"] = 2
        bom["Вътрешен ъгъл IN120/150"] = 2
        bom["Ригел AW 100/200"] = len(h_levels) * 4
    elif wall_type == "Колона":
        bom["Външен ъгъл EX240"] = 4
        bom["Стега H4/H8"] = len(h_levels) * 8
        bom["Ригел AW 100"] = len(h_levels) * 4
    else:
        bom["Ригел AW 200"] = len(h_levels) * 2
        bom["Стега H4"] = len(h_levels) * 6

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
        fontName=font_bold, fontSize=16, leading=20,
        textColor=colors.HexColor('#003366'), spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'PDFSubtitle', parent=styles['Normal'],
        fontName=font_name, fontSize=10, leading=14,
        textColor=colors.HexColor('#444444'), spaceAfter=10
    )

    cell_style = ParagraphStyle('CellText', parent=styles['Normal'], fontName=font_name, fontSize=8, leading=10)
    cell_bold_style = ParagraphStyle('CellTextBold', parent=styles['Normal'], fontName=font_bold, fontSize=8, leading=10, textColor=colors.white)

    story = []
    
    client = proj_info.get('client', 'Muhammet Ali')
    project = proj_info.get('project', 'Обект TEKO')
    
    # Шапка на документа
    story.append(Paragraph("<b>КОФРАЖНА СИСТЕМА TEKO / TEKO FORMWORK SYSTEM</b>", title_style))
    story.append(Paragraph(f"<b>Client / Клиент:</b> {client} | <b>Project / Обект:</b> {project}", subtitle_style))
    story.append(Spacer(1, 10))
    
    # 1. ОБЩА КОЛИЧЕСТВЕНА СМЕТКА (BOM SUMMARY)
    story.append(Paragraph("<b>Project bill of materials / Обобщена количествена сметка</b>", title_style))
    
    table_data = [[
        Paragraph("<b>№</b>", cell_bold_style),
        Paragraph("<b>Item / Артикул</b>", cell_bold_style),
        Paragraph("<b>System / Система</b>", cell_bold_style),
        Paragraph("<b>Qty / Бр.</b>", cell_bold_style)
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
    story.append(Spacer(1, 15))
    story.append(PageBreak())

    # 2. ЧЕРТЕЖИ И КОЛИЧЕСТВА ПО ЕЛЕМЕНТИ
    for elem in pdf_elements:
        e_name = elem.get('name', 'Елемент')
        w_type = elem.get('type_bg', 'Стена')
        l_a = elem.get('length_a_cm', 100)
        l_b = elem.get('length_b_cm', 100)
        h_cm = elem.get('height_cm', 270)
        thick = elem.get('thickness_cm', 30)

        story.append(Paragraph(f"<b>{e_name} ({w_type} - {int(l_a)}x{int(l_b)}x{int(h_cm)} cm)</b>", title_style))
        
        # 1. Изглед отгоре
        top_img = generate_top_view(w_type, l_a, l_b, 0, thick, name=e_name)
        buf_top = io.BytesIO()
        top_img.save(buf_top, format='PNG')
        story.append(RLImage(buf_top, width=480, height=200))
        story.append(Spacer(1, 10))

        # 2. Изглед отпред
        front_img = generate_front_view(w_type, l_a, l_b, h_cm, name=e_name)
        buf_front = io.BytesIO()
        front_img.save(buf_front, format='PNG')
        story.append(RLImage(buf_front, width=480, height=220))
        story.append(Spacer(1, 10))

        # 3. Таблица с количества за конкретния елемент (ELEMENT QUANTITIES)
        elem_bom = calculate_element_bom(w_type, l_a, l_b, h_cm)
        story.append(Paragraph("<b>ELEMENT QUANTITIES / КОЛИЧЕСТВА ЗА ЕЛЕМЕНТА</b>", subtitle_style))
        
        e_table_data = [[
            Paragraph("<b>Item / Артикул</b>", cell_bold_style),
            Paragraph("<b>Qty / Бр.</b>", cell_bold_style)
        ]]
        for item_code, item_qty in elem_bom.items():
            e_table_data.append([
                Paragraph(item_code, cell_style),
                Paragraph(str(item_qty), cell_style)
            ])
            
        t_elem = Table(e_table_data, colWidths=[340, 140])
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
