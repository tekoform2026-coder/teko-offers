import io
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from mpl_toolkits.mplot3d import Axes3D
from PIL import Image

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm

# Цветова палитра за чертежите
COLOR_PANEL = '#E2E8F0'       # Светло сив кофражен панел
COLOR_PANEL_BORDER = '#1E293B'# Тъмен кант за панел
COLOR_CORNER = '#86EFAC'     # Зелен цвят за ъгли (EX/IN)
COLOR_CONCRETE = '#CBD5E1'   # Сив цвят за бетона
COLOR_WALER = '#3B82F6'      # Син цвят за укрепващи ригели (AW)
COLOR_DIM = '#0284C7'        # Синьо за оразмерителни линии


def _calculate_height_breakdown(height_cm):
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


def _calculate_width_breakdown(width_cm):
    panel_widths = [60, 35, 30, 25, 20]
    rem = width_cm
    result = []
    for w in panel_widths:
        count = int(rem // w)
        for _ in range(count):
            result.append(w)
        rem -= count * w
    if rem > 0:
        result.append(round(rem, 1))
    return result


def draw_top_view_img(elem):
    """Генерира векторно 2D изображение 'Изглед отгоре' (Top View)"""
    fig, ax = plt.subplots(figsize=(6, 3), dpi=200)
    
    elem_type = elem.get('type', 'wall')
    thickness = elem.get('thickness_cm', 25)
    length = elem.get('length_a_cm', 300)
    
    # 1. Чертаене на бетоновото ядро
    rect_conc = patches.Rectangle((0, 0), length, thickness, facecolor=COLOR_CONCRETE, edgecolor='#64748B', hatch='//', lw=1.5)
    ax.add_patch(rect_conc)
    
    # 2. Подредба на панелите от двете страни
    widths = _calculate_width_breakdown(length)
    
    # Външна страна (Лице A)
    curr_x = 0
    for w in widths:
        p_rect = patches.Rectangle((curr_x, thickness), w, 6, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, lw=1)
        ax.add_patch(p_rect)
        ax.text(curr_x + w/2, thickness + 3, str(int(w)), color='#0F172A', fontsize=7, ha='center', va='center', fontweight='bold')
        curr_x += w
        
    # Вътрешна страна (Лице B)
    curr_x = 0
    for w in widths:
        p_rect = patches.Rectangle((curr_x, -6), w, 6, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, lw=1)
        ax.add_patch(p_rect)
        ax.text(curr_x + w/2, -3, str(int(w)), color='#0F172A', fontsize=7, ha='center', va='center', fontweight='bold')
        curr_x += w

    # Оразмерителна линия за дължина
    ax.annotate('', xy=(0, -15), xytext=(length, -15),
                arrowprops=dict(arrowstyle='<->', color=COLOR_DIM, lw=1.2))
    ax.text(length/2, -22, f"L = {int(length)} cm", color=COLOR_DIM, fontsize=8, ha='center', va='center', fontweight='bold')

    # Оразмерителна линия за дебелина
    ax.annotate('', xy=(-12, 0), xytext=(-12, thickness),
                arrowprops=dict(arrowstyle='<->', color=COLOR_DIM, lw=1.2))
    ax.text(-22, thickness/2, f"B={int(thickness)}", color=COLOR_DIM, fontsize=8, ha='center', va='center', rotation=90, fontweight='bold')

    ax.set_xlim(-35, length + 20)
    ax.set_ylim(-30, thickness + 20)
    ax.set_aspect('equal')
    ax.axis('off')
    
    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png', bbox_inches='tight', transparent=True)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf)


def draw_front_view_img(elem):
    """Генерира векторно 2D изображение 'Изглед отпред / Разгъвка' (Front View)"""
    fig, ax = plt.subplots(figsize=(6, 3.5), dpi=200)
    
    length = elem.get('length_a_cm', 300)
    height = elem.get('height_cm', 270)
    
    h_levels = _calculate_height_breakdown(height)
    w_breakdown = _calculate_width_breakdown(length)
    
    curr_y = 0
    for h_val in h_levels:
        curr_x = 0
        for w_val in w_breakdown:
            p_rect = patches.Rectangle((curr_x, curr_y), w_val, h_val, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, lw=0.8)
            ax.add_patch(p_rect)
            ax.text(curr_x + w_val/2, curr_y + h_val/2, f"{int(w_val)}/{int(h_val)}", 
                    color='#334155', fontsize=6, ha='center', va='center', rotation=45 if w_val < 30 else 0)
            curr_x += w_val
            
        # Ригел (Waler AW) през нивото
        waler_y = curr_y + h_val / 2
        ax.plot([0, length], [waler_y, waler_y], color=COLOR_WALER, lw=2.5, label='Ригел AW' if curr_y == 0 else "")
        curr_y += h_val

    # Оразмерителна линия за височина
    ax.annotate('', xy=(-15, 0), xytext=(-15, height),
                arrowprops=dict(arrowstyle='<->', color=COLOR_DIM, lw=1.2))
    ax.text(-25, height/2, f"H = {int(height)} cm", color=COLOR_DIM, fontsize=8, ha='center', va='center', rotation=90, fontweight='bold')

    ax.set_xlim(-35, length + 15)
    ax.set_ylim(-15, height + 15)
    ax.set_aspect('equal')
    ax.axis('off')
    
    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png', bbox_inches='tight', transparent=True)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf)


def draw_3d_view_img(elem):
    """Генерира 3D изометричен изглед на кофражния елемент"""
    fig = plt.figure(figsize=(5, 3.5), dpi=200)
    ax = fig.add_subplot(111, projection='3d')
    
    length = elem.get('length_a_cm', 300) / 100.0
    thickness = elem.get('thickness_cm', 25) / 100.0
    height = elem.get('height_cm', 270) / 100.0

    # Бетонно ядро
    ax.bar3d(0, 0, 0, length, thickness, height, color=COLOR_CONCRETE, alpha=0.6, edgecolor='#475569', linewidth=0.5)
    
    # Кофражни панели отвън
    ax.bar3d(0, thickness, 0, length, 0.05, height, color='#CBD5E1', alpha=0.9, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8)
    # Кофражни панели отвътре
    ax.bar3d(0, -0.05, 0, length, 0.05, height, color='#CBD5E1', alpha=0.9, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8)

    ax.set_title("3D Изометрия", fontsize=9, fontweight='bold', pad=0)
    ax.view_init(elev=25, azim=-55)
    ax.axis('off')

    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png', bbox_inches='tight', transparent=True)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf)


def generate_wall_2d(length_cm=300, height_cm=270, wall_name="Стена"):
    """За съвместимост с приложението"""
    elem = {'length_a_cm': length_cm, 'height_cm': height_cm, 'thickness_cm': 25}
    return draw_front_view_img(elem)


def generate_wall_3d(wall_type="Права стена", dim_a=300, dim_b=150, dim_c=150, height=270, thickness=25):
    """За съвместимост с приложението"""
    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Mesh3d(x=[0, dim_a/100, dim_a/100, 0], y=[0, 0, thickness/100, thickness/100], z=[0, 0, height/100, height/100], color='#CBD5E1'))
    return fig


def generate_pdf_drawings(elements_data, project_bom=None, project_info=None):
    """Генерира пълен PDF документ с чертежи и спецификация"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#475569'),
        spaceAfter=12
    )
    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=6
    )

    story = []

    # ------------------ СТРАНИЦА 1: ОБОБЩЕНА КОЛИЧЕСТВЕНА СМЕТКА ------------------
    p_info = project_info or {}
    client = p_info.get('client', 'Клиент')
    project = p_info.get('project', 'Обект')

    story.append(Paragraph("TEKO FORMWORK SYSTEM — ТЕХНИЧЕСКИ ЧЕРТЕЖИ", title_style))
    story.append(Paragraph(f"Обект: <b>{project}</b> | Клиент: <b>{client}</b> | Производител: <b>ПЛАСПАНЕЛ ООД</b>", subtitle_style))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("Обобщена спецификация за целия обект (Project BOM)", heading_style))
    
    bom_data = [["№", "Код / Компонент на кофража TEKO", "Описание / Размери", "Количество (бр.)"]]
    idx = 1
    if project_bom:
        for item_code, qty in sorted(project_bom.items()):
            bom_data.append([str(idx), str(item_code), "Кофражен панел / Аксесоар TEKO", f"{qty} бр."])
            idx += 1
    else:
        bom_data.append(["1", "TK 60/270", "Панел TEKO 60x270 см", "12 бр."])

    table_bom = Table(bom_data, colWidths=[15*mm, 80*mm, 120*mm, 45*mm])
    table_bom.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (3, 0), (3, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(table_bom)
    story.append(PageBreak())

    # ------------------ СТРАНИЦИ ЗА ВСЕКИ ЕЛЕМЕНТ ------------------
    if not isinstance(elements_data, list) or len(elements_data) == 0:
        elements_data = [{'name': 'Елемент 1', 'type': 'wall', 'length_a_cm': 300, 'height_cm': 270, 'thickness_cm': 25}]

    for elem in elements_data:
        e_name = elem.get('name', 'Елемент')
        e_len = elem.get('length_a_cm', elem.get('length_a', 300))
        e_h = elem.get('height_cm', elem.get('height', 270))
        e_t = elem.get('thickness_cm', 25)
        
        elem_dict = {'name': e_name, 'length_a_cm': e_len, 'height_cm': e_h, 'thickness_cm': e_t}

        story.append(Paragraph(f"ЧЕРТЕЖ И СПЕЦИФИКАЦИЯ: {e_name.upper()}", title_style))
        story.append(Paragraph(f"Тип: Чертеж на кофраж | Дължина: L={int(e_len)} cm | Височина: H={int(e_h)} cm | Дебелина: B={int(e_t)} cm", subtitle_style))

        # Генериране на трите чертежа като картинки
        top_img = draw_top_view_img(elem_dict)
        front_img = draw_front_view_img(elem_dict)
        iso_img = draw_3d_view_img(elem_dict)

        top_bytes = io.BytesIO()
        front_bytes = io.BytesIO()
        iso_bytes = io.BytesIO()

        top_img.save(top_bytes, format='PNG')
        front_img.save(front_bytes, format='PNG')
        iso_img.save(iso_bytes, format='PNG')

        top_bytes.seek(0)
        front_bytes.seek(0)
        iso_bytes.seek(0)

        rl_top = RLImage(top_bytes, width=130*mm, height=55*mm)
        rl_front = RLImage(front_bytes, width=130*mm, height=65*mm)
        rl_iso = RLImage(iso_bytes, width=120*mm, height=65*mm)

        # Подредба на чертежите в мрежа (Таблица)
        drawings_table_data = [
            [Paragraph("<b>ИЗГЛЕД ОТГОРЕ (TOP VIEW)</b>", heading_style), Paragraph("<b>3D ИЗОМЕТРИЧЕН ИЗГЛЕД</b>", heading_style)],
            [rl_top, rl_iso],
            [Paragraph("<b>ИЗГЛЕД ОТПРЕД / РАЗГЪВКА (FRONT VIEW)</b>", heading_style), ""]
        ]

        table_drawings = Table(
            [[rl_top, rl_iso], [rl_front, Paragraph("<b>Спецификация за елемента:</b><br/>• Кофражни панели TK<br/>• Укрепващи ригели AW<br/>• Стяги и шпилки H4/H8", subtitle_style)]],
            colWidths=[140*mm, 130*mm]
        )
        table_drawings.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))

        story.append(table_drawings)
        story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
