import io
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import rcParams
import plotly.graph_objects as go
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Настройка за кирилица в Matplotlib
rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']

# ==========================================
# 1. 2D ЧЕРТАЕНЕ НА СТЕНИ (MATPLOTLIB)
# ==========================================

def calculate_panel_layout(length_cm, height_cm):
    """
    Изчислява разположението на кофражните панели, ригели и подпори.
    """
    # Определяне на вертикалната конфигурация от панели
    if height_cm <= 240:
        vertical_stack = [120, 120]
        rigel_heights = [45, 105, 165, 225]
    elif height_cm <= 270:
        vertical_stack = [150, 120]
        rigel_heights = [45, 105, 165, 225]
    elif height_cm <= 300:
        vertical_stack = [150, 150]
        rigel_heights = [30, 90, 150, 210, 270]
    elif height_cm <= 330:
        vertical_stack = [150, 120, 60]
        rigel_heights = [30, 90, 150, 210, 270, 310]
    else:  # 360 cm
        vertical_stack = [150, 150, 60]
        rigel_heights = [30, 90, 150, 210, 270, 330]

    # Разпределяне на ширината на панелите (60, 30, 25, 20 cm)
    panel_widths = []
    rem = length_cm
    while rem > 0:
        if rem >= 60:
            panel_widths.append(60)
            rem -= 60
        elif rem >= 30:
            panel_widths.append(30)
            rem -= 30
        elif rem >= 25:
            panel_widths.append(25)
            rem -= 25
        else:
            panel_widths.append(rem)
            rem = 0

    return vertical_stack, panel_widths, rigel_heights


def generate_wall_2d(length_cm, height_cm, wall_name="Стена"):
    """
    Генерира 2D развертка на панелите с оразмеряване.
    """
    vertical_stack, panel_widths, rigel_heights = calculate_panel_layout(length_cm, height_cm)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_aspect('equal')

    # Панели (розов цвят)
    current_y = 0
    for h in vertical_stack:
        current_x = 0
        for w in panel_widths:
            rect = patches.Rectangle(
                (current_x, current_y), w, h,
                linewidth=1, edgecolor='#856404', facecolor='#FADBD8'
            )
            ax.add_patch(rect)

            if w >= 20:
                ax.text(
                    current_x + w / 2, current_y + h / 2,
                    f"{int(w)}/{h}", ha='center', va='center',
                    fontsize=7, color='#78281F', fontweight='bold'
                )
            current_x += w
        current_y += h

    # Хоризонтални ригели (зелен цвят)
    for rh in rigel_heights:
        rigel = patches.Rectangle(
            (0, rh - 4), length_cm, 8,
            linewidth=1, edgecolor='#1E8449', facecolor='#58D68D', alpha=0.9
        )
        ax.add_patch(rigel)

    # Вертикализатори / подпори
    step = 150
    for x_pos in range(75, int(length_cm), step):
        ax.plot([x_pos, x_pos - 40], [height_cm * 0.6, -30], color='#2E7D32', linewidth=3)
        ax.plot([x_pos - 45, x_pos - 35], [-30, -30], color='#1B5E20', linewidth=5)

    # Котни линии (височина)
    ax.annotate('', xy=(-15, 0), xytext=(-15, height_cm),
                arrowprops=dict(arrowstyle='<->', color='black', lw=1.2))
    ax.text(-25, height_cm / 2, f"{height_cm} cm", va='center', ha='right', rotation=90, fontweight='bold')

    # Котни линии (дължина)
    ax.annotate('', xy=(0, height_cm + 15), xytext=(length_cm, height_cm + 15),
                arrowprops=dict(arrowstyle='<->', color='black', lw=1.2))
    ax.text(length_cm / 2, height_cm + 25, f"{length_cm} cm", ha='center', va='bottom', fontweight='bold')

    ax.set_xlim(-50, length_cm + 50)
    ax.set_ylim(-50, height_cm + 50)
    ax.axis('off')
    plt.title(f"Развертка на панелите - {wall_name}", fontsize=12, pad=20, fontweight='bold')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf


# ==========================================
# 2. 3D МОДЕЛИРАНЕ (PLOTLY)
# ==========================================

def generate_wall_3d(wall_type="Права стена", dim_a=300, dim_b=150, dim_c=150, height=300, thickness=25):
    """
    Генерира интерактивен 3D модел на права, L-образна или U-образна стена.
    """
    fig = go.Figure()

    def add_box(x0, y0, z0, dx, dy, dz, color='#F5B7B1', name='Стена'):
        x = [x0, x0+dx, x0+dx, x0, x0, x0+dx, x0+dx, x0]
        y = [y0, y0, y0+dy, y0+dy, y0, y0, y0+dy, y0+dy]
        z = [z0, z0, z0, z0, z0+dz, z0+dz, z0+dz, z0+dz]

        i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
        j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
        k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]

        fig.add_trace(go.Mesh3d(
            x=x, y=y, z=z, i=i, j=j, k=k,
            color=color, opacity=0.85, flatshading=True, name=name
        ))

    if wall_type == "Права стена":
        add_box(0, 0, 0, dim_a, thickness, height, color='#F5B7B1', name='Стена A')

    elif wall_type == "L-образна стена":
        add_box(0, 0, 0, dim_a, thickness, height, color='#F5B7B1', name='Рамо A')
        add_box(dim_a - thickness, thickness, 0, thickness, dim_b - thickness, height, color='#D87093', name='Рамо B')

    elif wall_type == "U-образна стена":
        add_box(0, 0, 0, thickness, dim_b, height, color='#D87093', name='Рамо B')
        add_box(0, 0, 0, dim_a, thickness, height, color='#F5B7B1', name='Рамо A')
        add_box(dim_a - thickness, 0, 0, thickness, dim_c, height, color='#D87093', name='Рамо C')

    fig.update_layout(
        scene=dict(
            xaxis=dict(title='X (cm)', backgroundcolor="#F9F9F9"),
            yaxis=dict(title='Y (cm)', backgroundcolor="#F9F9F9"),
            zaxis=dict(title='Z (cm)', backgroundcolor="#F9F9F9"),
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=10),
        height=450
    )
    return fig


# ==========================================
# 3. PDF ГЕНЕРАТОР ЗА ЧЕРТЕЖИ
# ==========================================

def generate_pdf_drawings(elements, bom_data):
    """
    Генерира PDF файл с количествена сметка и 2D чертежи.
    """
    pdf_buf = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buf, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#2E7D32'))
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#1B5E20'))

    # Заглавие
    story.append(Paragraph("TEKO Formwork - Чертежи и Количествена сметка", title_style))
    story.append(Spacer(1, 15))

    # Спецификация
    story.append(Paragraph("Количествена сметка", h2_style))
    story.append(Spacer(1, 5))

    table_data = [["Артикул", "Количество (бр.)"]]
    for item, qty in bom_data.items():
        table_data.append([item, str(qty)])

    t = Table(table_data, colWidths=[250, 150])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))

    # 2D Чертежи
    story.append(Paragraph("Развертки на панелите", h2_style))
    story.append(Spacer(1, 10))

    for elem in elements:
        img_buf = generate_wall_2d(elem['length_a'], elem['height'], elem['name'])
        story.append(Image(img_buf, width=480, height=270))
        story.append(Spacer(1, 15))

    doc.build(story)
    pdf_buf.seek(0)
    return pdf_buf
