import io
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import plotly.graph_objects as go
from PIL import Image

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Задаване на шрифт с поддръжка на кирилица за Matplotlib
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
matplotlib.rcParams['font.family'] = 'sans-serif'

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

def generate_wall_2d(length_cm, height_cm, wall_name="Стена"):
    if length_cm <= 0 or height_cm <= 0:
        return None
        
    h_levels = calculate_height_breakdown(height_cm)
    w_panels = calculate_panel_width_breakdown(length_cm)
    
    fig, ax = plt.subplots(figsize=(8, 4), dpi=150)
    
    curr_y = 0
    for h_val in h_levels:
        curr_x = 0
        for w_val in w_panels:
            rect = patches.Rectangle(
                (curr_x, curr_y), w_val, h_val,
                linewidth=1, edgecolor='#003366', facecolor='#E3F2FD'
            )
            ax.add_patch(rect)
            
            if w_val >= 10 and h_val >= 20:
                ax.text(
                    curr_x + w_val / 2, curr_y + h_val / 2,
                    f"{int(w_val)}/{int(h_val)}",
                    ha='center', va='center', fontsize=7, color='#003366', fontweight='bold'
                )
            curr_x += w_val
        curr_y += h_val
        
    ax.set_xlim(-10, length_cm + 10)
    ax.set_ylim(-10, height_cm + 20)
    ax.set_aspect('equal')
    ax.set_title(f"2D Развертка: {wall_name} ({int(length_cm)}x{int(height_cm)} cm)", fontsize=10, fontweight='bold', pad=10)
    ax.set_xlabel("Дължина (cm)", fontsize=8)
    ax.set_ylabel("Височина (cm)", fontsize=8)
    ax.grid(True, linestyle='--', alpha=0.3)
    
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf)

def create_box_mesh(x0, y0, z0, dx, dy, dz, color='#1E88E5', opacity=0.8, name=''):
    x = [x0, x0+dx, x0+dx, x0, x0, x0+dx, x0+dx, x0]
    y = [y0, y0, y0+dy, y0+dy, y0, y0, y0+dy, y0+dy]
    z = [z0, z0, z0, z0, z0+dz, z0+dz, z0+dz, z0+dz]
    
    i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k = [0, 7, 2, 3, 6, 7, 1, 1, 1, 5, 7, 6]
    
    return go.Mesh3d(
        x=x, y=y, z=z,
        i=i, j=j, k=k,
        color=color, opacity=opacity,
        name=name, flatshading=True
    )

def generate_wall_3d(wall_type, dim_a, dim_b, dim_c, height, thickness):
    fig = go.Figure()
    
    a = max(float(dim_a or 100), 10.0)
    b = max(float(dim_b or 100), 10.0)
    c = max(float(dim_c or 100), 10.0)
    h = max(float(height or 300), 10.0)
    t = max(float(thickness or 25), 5.0)
    
    if wall_type == "L-образна стена":
        fig.add_trace(create_box_mesh(0, 0, 0, a, t, h, color='#2E7D32', name='Рамо 1'))
        fig.add_trace(create_box_mesh(0, t, 0, t, max(b - t, 5.0), h, color='#1B5E20', name='Рамо 2'))
    elif wall_type == "U-образна стена":
        fig.add_trace(create_box_mesh(0, 0, 0, a, t, h, color='#2E7D32', name='Стена 1'))
        fig.add_trace(create_box_mesh(0, t, 0, t, max(b - t, 5.0), h, color='#1B5E20', name='Стена 2'))
        fig.add_trace(create_box_mesh(max(a - t, 5.0), t, 0, t, max(c - t, 5.0), h, color='#4CAF50', name='Стена 3'))
    else:
        fig.add_trace(create_box_mesh(0, 0, 0, a, t, h, color='#2E7D32', name='Стена'))
        
    fig.update_layout(
        scene=dict(
            xaxis_title='X (cm)',
            yaxis_title='Y (cm)',
            zaxis_title='Z (cm)',
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=30),
        height=400
    )
    return fig

def generate_pdf_drawings(pdf_elements, bom_summary, proj_info):
    has_dejavu = setup_pdf_fonts()
    font_name = 'DejaVuSans' if has_dejavu else 'Helvetica'
    font_bold = 'DejaVuSans-Bold' if has_dejavu else 'Helvetica-Bold'
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'PDFTitle',
        parent=styles['Heading1'],
        fontName=font_bold,
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#003366'),
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'PDFSubtitle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#555555'),
        spaceAfter=15
    )

    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=9,
        leading=11
    )
    
    cell_bold_style = ParagraphStyle(
        'CellTextBold',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=9,
        leading=11,
        textColor=colors.white
    )

    story = []
    
    client = proj_info.get('client', 'Клиент')
    project = proj_info.get('project', 'Обект TEKO')
    
    story.append(Paragraph("<b>КОФРАЖНА СИСТЕМА TEKO</b>", title_style))
    story.append(Paragraph(f"<b>Обект:</b> {project} | <b>Клиент:</b> {client}", subtitle_style))
    story.append(Spacer(1, 10))
    
    story.append(Paragraph("<b>Спецификация на необходимите панели (BOM)</b>", title_style))
    
    table_data = [[
        Paragraph("<b>№</b>", cell_bold_style),
        Paragraph("<b>Код на панел</b>", cell_bold_style),
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
        
    t = Table(table_data, colWidths=[40, 200, 100, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')])
    ]))
    story.append(t)
    story.append(Spacer(1, 20))
    
    story.append(Paragraph("<b>2D Чертежи и Развертки на Елементите</b>", title_style))
    story.append(Spacer(1, 10))
    
    for elem in pdf_elements:
        e_name = elem.get('name', 'Елемент')
        l_cm = elem.get('length_a_cm', 100)
        h_cm = elem.get('height_cm', 300)
        
        img_obj = generate_wall_2d(l_cm, h_cm, wall_name=e_name)
        if img_obj:
            img_buf = io.BytesIO()
            img_obj.save(img_buf, format='PNG')
            img_buf.seek(0)
            
            story.append(Paragraph(f"<b>{e_name}</b> ({int(l_cm)}x{int(h_cm)} cm)", subtitle_style))
            rl_img = RLImage(img_buf, width=450, height=225)
            story.append(rl_img)
            story.append(Spacer(1, 15))
            
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
