import io
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm

# Палитра за чертежите (без шрафировки и прозрачност за чист PDF рендер)
COLOR_PANEL = '#E2E8F0'       # Светло сив кофражен панел
COLOR_PANEL_BORDER = '#1E293B'# Тъмен кант за панел
COLOR_CONCRETE = '#94A3B8'   # Плътно сиво бетоново ядро (без точки)
COLOR_WALER = '#2563EB'      # Сини ригели
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
    """Генерира изглед отгоре (Top View) с бял плътен фон без черни точки/артефакти"""
    fig, ax = plt.subplots(figsize=(8, 3), dpi=300, facecolor='white')
    ax.set_facecolor('white')
    
    thickness = elem.get('thickness_cm', 25)
    length = elem.get('length_a_cm', 300)
    
    # Бетоново ядро (плътен цвят без hatch шрафировка)
    rect_conc = patches.Rectangle((0, 0), length, thickness, facecolor=COLOR_CONCRETE, edgecolor='#475569', lw=1.2)
    ax.add_patch(rect_conc)
    
    widths = _calculate_width_breakdown(length)
    
    # Лице A
    curr_x = 0
    for w in widths:
        p_rect = patches.Rectangle((curr_x, thickness), w, 8, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, lw=0.8)
        ax.add_patch(p_rect)
        if w >= 15:
            ax.text(curr_x + w/2, thickness + 4, str(int(w)), color='#0F172A', fontsize=7, ha='center', va='center', fontweight='bold')
        curr_x += w
        
    # Лице B
    curr_x = 0
    for w in widths:
        p_rect = patches.Rectangle((curr_x, -8), w, 8, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, lw=0.8)
        ax.add_patch(p_rect)
        if w >= 15:
            ax.text(curr_x + w/2, -4, str(int(w)), color='#0F172A', fontsize=7, ha='center', va='center', fontweight='bold')
        curr_x += w

    # Оразмерителна линия за дължина
    ax.annotate('', xy=(0, -18), xytext=(length, -18),
                arrowprops=dict(arrowstyle='<->', color=COLOR_DIM, lw=1.0))
    ax.text(length/2, -26, f"L = {int(length)} cm", color=COLOR_DIM, fontsize=8, ha='center', va='center', fontweight='bold',
            bbox=dict(boxstyle='square,pad=0.15', facecolor='white', edgecolor='none'))

    # Оразмерителна линия за дебелина
    ax.annotate('', xy=(-15, 0), xytext=(-15, thickness),
                arrowprops=dict(arrowstyle='<->', color=COLOR_DIM, lw=1.0))
    ax.text(-28, thickness/2, f"B = {int(thickness)}", color=COLOR_DIM, fontsize=8, ha='center', va='center', rotation=90, fontweight='bold',
            bbox=dict(boxstyle='square,pad=0.15', facecolor='white', edgecolor='none'))

    ax.set_xlim(-40, length + 25)
    ax.set_ylim(-35, thickness + 25)
    ax.set_aspect('equal')
    ax.axis('off')
    
    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf)


def draw_front_view_img(elem):
    """Генерира изглед отпред / разгъвка с чист бял фон без точки"""
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300, facecolor='white')
    ax.set_facecolor('white')
    
    length = elem.get('length_a_cm', 300)
    height = elem.get('height_cm', 270)
    
    h_levels = _calculate_height_breakdown(height)
    w_breakdown = _calculate_width_breakdown(length)
    
    curr_y = 0
    for h_val in h_levels:
        curr_x = 0
        for w_val in w_breakdown:
            p_rect = patches.Rectangle((curr_x, curr_y), w_val, h_val, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, lw=0.8, zorder=1)
            ax.add_patch(p_rect)
            
            label_text = f"{int(w_val)}/{int(h_val)}"
            rot = 90 if w_val < 25 else 0
            fsize = 5.5 if w_val < 20 else 7
            
            ax.text(curr_x + w_val/2, curr_y + h_val/2, label_text, 
                    color='#0F172A', fontsize=fsize, ha='center', va='center', rotation=rot, fontweight='bold', zorder=3,
                    bbox=dict(boxstyle='square,pad=0.15', facecolor='white', edgecolor='none'))
            curr_x += w_val
            
        y1 = curr_y + h_val * 0.25
        y2 = curr_y + h_val * 0.75
        ax.plot([0, length], [y1, y1], color=COLOR_WALER, lw=1.2, alpha=0.7, zorder=2)
        ax.plot([0, length], [y2, y2], color=COLOR_WALER, lw=1.2, alpha=0.7, zorder=2)
        curr_y += h_val

    # Оразмерителна линия за височина
    ax.annotate('', xy=(-18, 0), xytext=(-18, height),
                arrowprops=dict(arrowstyle='<->', color=COLOR_DIM, lw=1.0))
    ax.text(-30, height/2, f"H = {int(height)} cm", color=COLOR_DIM, fontsize=8, ha='center', va='center', rotation=90, fontweight='bold',
            bbox=dict(boxstyle='square,pad=0.15', facecolor='white', edgecolor='none'))

    ax.set_xlim(-40, length + 20)
    ax.set_ylim(-20, height + 20)
    ax.set_aspect('equal')
    ax.axis('off')
    
    buf = io.BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf)


def _get_aspect_rl_image(pil_img, max_width_mm, max_height_mm):
    """Запазва точните пропорции на чертежа"""
    img_w, img_h = pil_img.size
    aspect = float(img_h) / float(img_w)
    
    target_w = max_width_mm * mm
    target_h = target_w * aspect
    
    if target_h > (max_height_mm * mm):
        target_h = max_height_mm * mm
        target_w = target_h / aspect
        
    buf = io.BytesIO()
    pil_img.save(buf, format='PNG')
    buf.seek(0)
    return RLImage(buf, width=target_w, height=target_h)


def generate_wall_2d(*args, **kwargs):
    return None

def generate_wall_3d(*args, **kwargs):
    return None


def generate_pdf_drawings(elements_data, project_bom=None, project_info=None):
    """Генерира изчистен PDF файл без точки и дефекти"""
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
        'DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=16, textColor=colors.HexColor('#0F172A'), spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle', parent=styles['Normal'], fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#475569'), spaceAfter=10
    )
    heading_style = ParagraphStyle(
        'SectionHeading', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#1E293B'), spaceAfter=4
    )

    story = []

    # 1. ОБОБЩЕНА СПЕЦИФИКАЦИЯ (BOM)
    p_info = project_info or {}
    client = p_info.get('client', '—')
    project = p_info.get('project', '—')

    story.append(Paragraph("TEKO FORMWORK SYSTEM — ТЕХНИЧЕСКА ДОКУМЕНТАЦИЯ", title_style))
    story.append(Paragraph(f"Обект: <b>{project}</b> | Клиент: <b>{client}</b> | Производител: <b>ПЛАСПАНЕЛ ООД</b>", subtitle_style))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Обобщена количествена сметка (Project BOM)", heading_style))
    
    bom_data = [["№", "Код / Компонент TEKO", "Описание", "Общо количество"]]
    idx = 1
    if project_bom:
        for item_code, qty in sorted(project_bom.items()):
            bom_data.append([str(idx), str(item_code), "Кофражен панел / Аксесоар TEKO", f"{qty} бр."])
            idx += 1

    table_bom = Table(bom_data, colWidths=[15*mm, 70*mm, 120*mm, 50*mm])
    table_bom.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (3, 0), (3, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(table_bom)
    story.append(PageBreak())

    # 2. СТРАНИЦИ С ЧЕРТЕЖИ
    if not isinstance(elements_data, list) or len(elements_data) == 0:
        elements_data = [{'name': 'Елемент 1', 'length_a_cm': 300, 'height_cm': 270, 'thickness_cm': 25}]

    for elem in elements_data:
        e_name = elem.get('name', 'Елемент')
        e_len = elem.get('length_a_cm', elem.get('length_a', 300))
        e_h = elem.get('height_cm', elem.get('height', 270))
        e_t = elem.get('thickness_cm', 25)
        
        elem_dict = {'name': e_name, 'length_a_cm': e_len, 'height_cm': e_h, 'thickness_cm': e_t}

        story.append(Paragraph(f"ЧЕРТЕЖ: {e_name.upper()}", title_style))
        story.append(Paragraph(f"Размери на елемента: Дължина L = {int(e_len)} cm | Височина H = {int(e_h)} cm | Дебелина B = {int(e_t)} cm", subtitle_style))

        top_img = draw_top_view_img(elem_dict)
        front_img = draw_front_view_img(elem_dict)

        rl_top = _get_aspect_rl_image(top_img, max_width_mm=250, max_height_mm=65)
        rl_front = _get_aspect_rl_image(front_img, max_width_mm=250, max_height_mm=95)

        story.append(Paragraph("<b>1. Изглед отгоре (Top View)</b>", heading_style))
        story.append(rl_top)
        story.append(Spacer(1, 4 * mm))
        
        story.append(Paragraph("<b>2. Изглед отпред / Разгъвка на панелите (Front View)</b>", heading_style))
        story.append(rl_front)
        
        story.append(PageBreak())

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
