# drawing_generator.py
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

from accessories_calculator import calculate_accessories, calculate_walers
from teko_calculator import solve_height_cm, solve_width_cm, format_panel_code

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

def calculate_height_breakdown(height_cm):
    """Разбива височината на стандартни модули."""
    return solve_height_cm(height_cm)

def calculate_panel_width_breakdown(width_cm):
    """Разбива ширината в рамките на наличната дължина."""
    panels_dict, _ = solve_width_cm(width_cm, 150)
    result = []
    for w, count in panels_dict.items():
        for _ in range(count):
            result.append(w)
    return result

# ==========================================
# 1. ОБЩ 3D ИЗГЛЕД НА ЦЕЛИЯ ОБЕКТ (PROJECT 3D)
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
# 2. ИЗГЛЕД ОТГОРЕ (TOP VIEW)
# ==========================================
def generate_top_view_buf(wall_type, dim_a, dim_b, thickness, name="Елемент"):
    fig, ax = plt.subplots(figsize=(3.5, 2.5), dpi=DPI_RESOLUTION)
    
    a = float(dim_a or 100)
    b = float(dim_b or 100)
    t = float(thickness or 30)
    
    w_str = str(wall_type).lower()
    n_str = str(name).lower()
    is_column = "колона" in w_str or "column" in w_str or "колона" in n_str
    is_l_wall = "l" in w_str or "l-образна" in w_str or "l_wall" in w_str or "l-стена" in n_str
    is_u_wall = "u" in w_str or "u-образна" in w_str or "u_wall" in w_str or "п" in w_str or "п-образна" in w_str or "ядро" in w_str or "ядро" in n_str

    if is_column:
        ax.add_patch(patches.Rectangle((0, 0), a, b, facecolor=COLOR_CONCRETE, edgecolor='#2C3E50', linewidth=1.2))
        
        for x_pos, y_pos in [(-15, -15), (a, -15), (a, b), (-15, b)]:
            ax.add_patch(patches.Rectangle((x_pos, y_pos), 15, 15, facecolor=COLOR_CORNER_EX, edgecolor='black', linewidth=0.8))
            ax.text(x_pos+7.5, y_pos+7.5, "EX", ha='center', va='center', fontsize=5.5, fontweight='bold')

        w_a = calculate_panel_width_breakdown(a)
        curr_x = 0
        for w in w_a:
            ax.add_patch(patches.Rectangle((curr_x, -15), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(curr_x + w/2, -7.5, f"{int(w)}", ha='center', va='center', fontsize=5.5, fontweight='bold')
            ax.add_patch(patches.Rectangle((curr_x, b), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(curr_x + w/2, b + 7.5, f"{int(w)}", ha='center', va='center', fontsize=5.5, fontweight='bold')
            curr_x += w

        w_b = calculate_panel_width_breakdown(b)
        curr_y = 0
        for w in w_b:
            ax.add_patch(patches.Rectangle((-15, curr_y), 15, w, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(-7.5, curr_y + w/2, f"{int(w)}", ha='center', va='center', fontsize=5.5, fontweight='bold', rotation=90)
            ax.add_patch(patches.Rectangle((a, curr_y), 15, w, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(a + 7.5, curr_y + w/2, f"{int(w)}", ha='center', va='center', fontsize=5.5, fontweight='bold', rotation=90)
            curr_y += w

        ax.set_xlim(-25, a + 25)
        ax.set_ylim(-25, b + 25)

    elif is_l_wall:
        poly = patches.Polygon([[0, 0], [a, 0], [a, t], [t, t], [t, b], [0, b]], 
                               facecolor=COLOR_CONCRETE, edgecolor='#2C3E50', linewidth=1.2)
        ax.add_patch(poly)
        
        for x_pos, y_pos in [(-15, -15), (a, -15), (-15, b)]:
            ax.add_patch(patches.Rectangle((x_pos, y_pos), 15, 15, facecolor=COLOR_CORNER_EX, edgecolor='black', linewidth=0.8))
            ax.text(x_pos+7.5, y_pos+7.5, "EX", ha='center', va='center', fontsize=5.5, fontweight='bold')

        ax.add_patch(patches.Rectangle((t, t), 15, 15, facecolor=COLOR_CORNER_IN, edgecolor='black', linewidth=0.8))
        ax.text(t + 7.5, t + 7.5, "IN", ha='center', va='center', fontsize=5.5, fontweight='bold', color='white')

        w_a = calculate_panel_width_breakdown(a)
        curr_x = 0
        for w in w_a:
            ax.add_patch(patches.Rectangle((curr_x, -15), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(curr_x + w/2, -7.5, f"{int(w)}", ha='center', va='center', fontsize=5.5, fontweight='bold')
            curr_x += w

        w_b = calculate_panel_width_breakdown(b)
        curr_y = 0
        for w in w_b:
            ax.add_patch(patches.Rectangle((-15, curr_y), 15, w, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(-7.5, curr_y + w/2, f"{int(w)}", ha='center', va='center', fontsize=5.5, fontweight='bold', rotation=90)
            curr_y += w

        ax.add_patch(patches.Rectangle((a, 0), 15, t, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
        ax.text(a + 7.5, t/2, f"{int(t)}", ha='center', va='center', fontsize=5.5, fontweight='bold', rotation=90)

        ax.add_patch(patches.Rectangle((0, b), t, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
        ax.text(t/2, b + 7.5, f"{int(t)}", ha='center', va='center', fontsize=5.5, fontweight='bold')

        w_inner_a = calculate_panel_width_breakdown(max(0, a - t - 15))
        curr_x = t + 15
        for w in w_inner_a:
            if curr_x + w <= a:
                ax.add_patch(patches.Rectangle((curr_x, t), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
                ax.text(curr_x + w/2, t + 7.5, f"{int(w)}", ha='center', va='center', fontsize=5.5, fontweight='bold')
                curr_x += w

        w_inner_b = calculate_panel_width_breakdown(max(0, b - t - 15))
        curr_y = t + 15
        for w in w_inner_b:
            if curr_y + w <= b:
                ax.add_patch(patches.Rectangle((t, curr_y), 15, w, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
                ax.text(t + 7.5, curr_y + w/2, f"{int(w)}", ha='center', va='center', fontsize=5.5, fontweight='bold', rotation=90)
                curr_y += w

        ax.set_xlim(-25, max(a, b) + 25)
        ax.set_ylim(-25, max(a, b) + 25)

    elif is_u_wall:
        m_len = b if b else a
        poly = patches.Polygon([[0, 0], [m_len, 0], [m_len, a], [m_len - t, a], [m_len - t, t], [t, t], [t, a], [0, a]], 
                               facecolor=COLOR_CONCRETE, edgecolor='#2C3E50', linewidth=1.2)
        ax.add_patch(poly)

        for x_pos, y_pos in [(-15, -15), (m_len, -15), (-15, a), (m_len, a)]:
            ax.add_patch(patches.Rectangle((x_pos, y_pos), 15, 15, facecolor=COLOR_CORNER_EX, edgecolor='black', linewidth=0.8))
            ax.text(x_pos+7.5, y_pos+7.5, "EX", ha='center', va='center', fontsize=5.5, fontweight='bold')

        for in_x, in_y in [(t, t), (m_len - t - 15, t)]:
            ax.add_patch(patches.Rectangle((in_x, in_y), 15, 15, facecolor=COLOR_CORNER_IN, edgecolor='black', linewidth=0.8))
            ax.text(in_x + 7.5, in_y + 7.5, "IN", ha='center', va='center', fontsize=5.5, fontweight='bold', color='white')

        w_m = calculate_panel_width_breakdown(m_len)
        curr_x = 0
        for w in w_m:
            ax.add_patch(patches.Rectangle((curr_x, -15), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(curr_x + w/2, -7.5, f"{int(w)}", ha='center', va='center', fontsize=5.5, fontweight='bold')
            curr_x += w

        w_side = calculate_panel_width_breakdown(a)
        curr_y = 0
        for w in w_side:
            ax.add_patch(patches.Rectangle((-15, curr_y), 15, w, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(-7.5, curr_y + w/2, f"{int(w)}", ha='center', va='center', fontsize=5.5, fontweight='bold', rotation=90)
            ax.add_patch(patches.Rectangle((m_len, curr_y), 15, w, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(m_len + 7.5, curr_y + w/2, f"{int(w)}", ha='center', va='center', fontsize=5.5, fontweight='bold', rotation=90)
            curr_y += w

        ax.add_patch(patches.Rectangle((0, a), t, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
        ax.text(t/2, a + 7.5, f"{int(t)}", ha='center', va='center', fontsize=5.5, fontweight='bold')
        
        ax.add_patch(patches.Rectangle((m_len - t, a), t, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
        ax.text(m_len - t/2, a + 7.5, f"{int(t)}", ha='center', va='center', fontsize=5.5, fontweight='bold')

        w_inner_m = calculate_panel_width_breakdown(max(0, m_len - 2 * t - 30))
        curr_x = t + 15
        for w in w_inner_m:
            if curr_x + w <= m_len - t:
                ax.add_patch(patches.Rectangle((curr_x, t), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
                ax.text(curr_x + w/2, t + 7.5, f"{int(w)}", ha='center', va='center', fontsize=5.5, fontweight='bold')
                curr_x += w

        w_inner_side = calculate_panel_width_breakdown(max(0, a - t - 15))
        curr_y = t + 15
        for w in w_inner_side:
            if curr_y + w <= a:
                ax.add_patch(patches.Rectangle((t, curr_y), 15, w, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
                ax.text(t + 7.5, curr_y + w/2, f"{int(w)}", ha='center', va='center', fontsize=5.5, fontweight='bold', rotation=90)
                curr_y += w

        curr_y = t + 15
        for w in w_inner_side:
            if curr_y + w <= a:
                ax.add_patch(patches.Rectangle((m_len - t - 15, curr_y), 15, w, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
                ax.text(m_len - t - 7.5, curr_y + w/2, f"{int(w)}", ha='center', va='center', fontsize=5.5, fontweight='bold', rotation=90)
                curr_y += w

        ax.set_xlim(-25, m_len + 25)
        ax.set_ylim(-25, a + 25)

    else:
        ax.add_patch(patches.Rectangle((0, 0), a, t, facecolor=COLOR_CONCRETE, edgecolor='#2C3E50', linewidth=1.2))
        
        for x_pos, y_pos in [(-15, -15), (a, -15), (a, t), (-15, t)]:
            ax.add_patch(patches.Rectangle((x_pos, y_pos), 15, 15, facecolor=COLOR_CORNER_EX, edgecolor='black', linewidth=0.8))
            ax.text(x_pos+7.5, y_pos+7.5, "EX", ha='center', va='center', fontsize=5.5, fontweight='bold')

        w_a = calculate_panel_width_breakdown(a)
        curr_x = 0
        for w in w_a:
            ax.add_patch(patches.Rectangle((curr_x, -15), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(curr_x + w/2, -7.5, f"{int(w)}", ha='center', va='center', fontsize=6, fontweight='bold')
            ax.add_patch(patches.Rectangle((curr_x, t), w, 15, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(curr_x + w/2, t + 7.5, f"{int(w)}", ha='center', va='center', fontsize=6, fontweight='bold')
            curr_x += w

        for y_side in [0]:
            ax.add_patch(patches.Rectangle((-15, y_side), 15, t, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(-7.5, y_side + t/2, f"{int(t)}", ha='center', va='center', fontsize=5.5, fontweight='bold', rotation=90)
            ax.add_patch(patches.Rectangle((a, y_side), 15, t, facecolor=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, linewidth=0.8))
            ax.text(a + 7.5, y_side + t/2, f"{int(t)}", ha='center', va='center', fontsize=5.5, fontweight='bold', rotation=90)

        prop_positions = [a * 0.33, a * 0.67]
        for px in prop_positions:
            ax.add_patch(patches.Rectangle((px - 2, -40), 4, 25, facecolor=COLOR_WALER, edgecolor='#1E8449', linewidth=0.5, alpha=0.9, zorder=2))
            ax.add_patch(patches.Rectangle((px - 2, t + 15), 4, 25, facecolor=COLOR_WALER, edgecolor='#1E8449', linewidth=0.5, alpha=0.9, zorder=2))

        ax.set_xlim(-25, a + 25)
        ax.set_ylim(-45, t + 45)

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
# 3. ИЗГЛЕД ОТПРЕД (FRONT VIEW)
# ==========================================
def generate_front_view_buf(wall_type, dim_a, dim_b, height_cm, name="Елемент"):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.5, 3.2), dpi=DPI_RESOLUTION)
    
    a = float(dim_a or 100)
    b = float(dim_b or 100)
    h_cm = float(height_cm or 300)
    h_levels = calculate_height_breakdown(h_cm)
    
    w_str = str(wall_type).lower()
    n_str = str(name).lower()
    is_column = "колона" in w_str or "column" in w_str or "колона" in n_str
    is_l_wall = "l" in w_str or "l-образна" in w_str or "l_wall" in w_str or "l-стена" in n_str

    needs_walers = True
    if is_column:
        max_col_dim = max(a, b)
        if max_col_dim <= 35:
            needs_walers = False

    def draw_side_front(ax, side_len, title_label):
        w_panels = calculate_panel_width_breakdown(side_len)
        
        ax.add_patch(patches.Rectangle((-10, 0), 10, h_cm, facecolor=COLOR_CORNER_EX, edgecolor='black', linewidth=0.8, zorder=1))
        ax.add_patch(patches.Rectangle((side_len, 0), 10, h_cm, facecolor=COLOR_CORNER_EX, edgecolor='black', linewidth=0.8, zorder=1))

        waler_positions = []
        if needs_walers:
            first_row_h = h_levels[0] if h_levels else 150
            first_row_type = "120x60_standing" if first_row_h == 120 else "150x60_standing"
            
            walers_info = calculate_walers(wall_type, side_len, side_len, h_cm, first_row_panel_type=first_row_type)
            waler_positions = walers_info.get("height_positions_cm", [])
            for w_y in waler_positions:
                if w_y < h_cm:
                    ax.add_patch(patches.Rectangle((-14, w_y - 4), side_len + 28, 8, 
                                                 facecolor=COLOR_WALER, edgecolor='#1E8449', linewidth=0.6, alpha=0.9, zorder=2))

        curr_y = 0
        for h_val in h_levels:
            curr_x = 0
            for w_val in w_panels:
                rect = patches.Rectangle((curr_x, curr_y), w_val, h_val, 
                                         linewidth=0.8, edgecolor=COLOR_PANEL_BORDER, facecolor=COLOR_PANEL, zorder=1)
                ax.add_patch(rect)
                
                if int(h_val) == 60 and int(w_val) == 60:
                    text_str = "150/60"
                else:
                    text_str = f"{int(h_val)}/{int(w_val)}"

                font_sz = 5.5
                ax.text(curr_x + w_val / 2, curr_y + h_val / 2, text_str,
                        ha='center', va='center', fontsize=font_sz, color='#111111', fontweight='bold', 
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

        ax.set_xlim(-38, side_len + 20)
        ax.set_ylim(-10, h_cm + 15)
        ax.set_aspect('equal', adjustable='datalim')
        ax.axis('off')
        ax.set_title(f"Страна {title_label} ({int(side_len)}x{int(h_cm)} cm)", fontsize=8, fontweight='bold')

    draw_side_front(ax1, a, "A")
    draw_side_front(ax2, b, "B" if is_column or is_l_wall else "А1")

    fig.suptitle("Изглед отпред (Front View)", fontsize=9, fontweight='bold', y=0.98)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.05, dpi=DPI_RESOLUTION)
    plt.close(fig)
    buf.seek(0)
    return buf

# ==========================================
# 4. ИНДИВИДУАЛЕН 3D КОФРАЖЕН ИЗГЛЕД (3D AXONOMETRY)
# ==========================================
def generate_3d_axonometry_buf(wall_type, dim_a, dim_b, height_cm, thickness, name="Елемент"):
    fig = plt.figure(figsize=(3.5, 2.5), dpi=DPI_RESOLUTION)
    ax = fig.add_subplot(111, projection='3d')
    
    a = float(dim_a or 100)
    b = float(dim_b or 100)
    h = float(height_cm or 270)
    t = float(thickness or 30)
    
    w_str = str(wall_type).lower()
    n_str = str(name).lower()
    is_column = "колона" in w_str or "column" in w_str or "колона" in n_str
    is_l_wall = "l" in w_str or "l-образна" in w_str or "l_wall" in w_str or "l-стена" in n_str
    is_u_wall = "u" in w_str or "u-образна" in w_str or "u_wall" in w_str or "п" in w_str or "п-образна" in w_str or "ядро" in w_str or "ядро" in n_str
    h_levels = calculate_height_breakdown(h)

    if is_l_wall:
        w_a = calculate_panel_width_breakdown(a)
        w_b = calculate_panel_width_breakdown(b)

        curr_z = 0
        for h_val in h_levels:
            curr_x = 0
            for w_val in w_a:
                ax.bar3d(curr_x, -12, curr_z, w_val, 12, h_val, color=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, alpha=0.9, linewidth=0.3)
                curr_x += w_val
            curr_z += h_val

        curr_z = 0
        for h_val in h_levels:
            curr_y = 0
            for w_val in w_b:
                ax.bar3d(-12, curr_y, curr_z, 12, w_val, h_val, color=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, alpha=0.9, linewidth=0.3)
                curr_y += w_val
            curr_z += h_val

        for xc, yc in [(-12, -12), (a, -12), (-12, b)]:
            ax.bar3d(xc, yc, 0, 12, 12, h, color=COLOR_CORNER_EX, edgecolor='black', alpha=0.9, linewidth=0.3)

        ax.set_xlim(-30, max(a, b) + 30)
        ax.set_ylim(-30, max(a, b) + 30)

    elif is_u_wall:
        m_len = b if b else a
        w_m = calculate_panel_width_breakdown(m_len)
        w_side = calculate_panel_width_breakdown(a)

        curr_z = 0
        for h_val in h_levels:
            curr_x = 0
            for w_val in w_m:
                ax.bar3d(curr_x, -12, curr_z, w_val, 12, h_val, color=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, alpha=0.9, linewidth=0.3)
                curr_x += w_val
            curr_z += h_val

        curr_z = 0
        for h_val in h_levels:
            curr_y = 0
            for w_val in w_side:
                ax.bar3d(-12, curr_y, curr_z, 12, w_val, h_val, color=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, alpha=0.9, linewidth=0.3)
                curr_y += w_val
            curr_z += h_val

        curr_z = 0
        for h_val in h_levels:
            curr_y = 0
            for w_val in w_side:
                ax.bar3d(m_len - 12, curr_y, curr_z, 12, w_val, h_val, color=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, alpha=0.9, linewidth=0.3)
                curr_y += w_val
            curr_z += h_val

        for xc, yc in [(-12, -12), (m_len - 12, -12), (-12, a), (m_len - 12, a)]:
            ax.bar3d(xc, yc, 0, 12, 12, h, color=COLOR_CORNER_EX, edgecolor='black', alpha=0.9, linewidth=0.3)

        ax.set_xlim(-30, m_len + 30)
        ax.set_ylim(-30, a + 30)

    else:
        dim_y = b if is_column else t
        w_a = calculate_panel_width_breakdown(a)
        w_b = calculate_panel_width_breakdown(b) if is_column else []

        curr_z = 0
        for h_val in h_levels:
            curr_x = 0
            for w_val in w_a:
                ax.bar3d(curr_x, -12, curr_z, w_val, 12, h_val, color=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, alpha=0.9, linewidth=0.3)
                curr_x += w_val
            curr_z += h_val

        curr_z = 0
        for h_val in h_levels:
            curr_x = 0
            for w_val in w_a:
                ax.bar3d(curr_x, dim_y, curr_z, w_val, 12, h_val, color=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, alpha=0.9, linewidth=0.3)
                curr_x += w_val
            curr_z += h_val

        if is_column:
            curr_z = 0
            for h_val in h_levels:
                curr_y = 0
                for w_val in w_b:
                    ax.bar3d(-12, curr_y, curr_z, 12, w_val, h_val, color=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, alpha=0.9, linewidth=0.3)
                    ax.bar3d(a, curr_y, curr_z, 12, w_val, h_val, color=COLOR_PANEL, edgecolor=COLOR_PANEL_BORDER, alpha=0.9, linewidth=0.3)
                    curr_y += w_val
                curr_z += h_val

        for xc, yc in [(-12, -12), (a, -12), (a, dim_y), (-12, dim_y)]:
            ax.bar3d(xc, yc, 0, 12, 12, h, color=COLOR_CORNER_EX, edgecolor='black', alpha=0.9, linewidth=0.3)

        ax.set_xlim(-30, a + 30)
        ax.set_ylim(-30, (b if is_column else dim_y) + 30)

    ax.set_zlim(0, h + 20)
    ax.axis('off')
    ax.view_init(elev=25, azim=-55)
    ax.set_title("3D Изометрия (3D View)", fontsize=8, fontweight='bold', pad=2)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.05, dpi=DPI_RESOLUTION)
    plt.close(fig)
    buf.seek(0)
    return buf

# ==========================================
# 5. СИНХРОНИЗИРАНА СПЕЦИФИКАЦИЯ ЗА ЕЛЕМЕНТА (BOM)
# ==========================================
def calculate_element_bom(wall_type, dim_a, dim_b, height_cm, name="", thickness_cm=30):
    bom = {}
    h_levels = calculate_height_breakdown(height_cm)
    
    w_str = str(wall_type).lower()
    n_str = str(name).lower()
    is_column = "колона" in w_str or "column" in w_str or "колона" in n_str
    is_l_wall = "l" in w_str or "l-образна" in w_str or "l_wall" in w_str or "l-стена" in n_str
    is_u_wall = "u" in w_str or "u-образна" in w_str or "u_wall" in w_str or "п" in w_str or "п-образна" in w_str or "ядро" in w_str or "ядро" in n_str

    t = float(thickness_cm or 30)
    
    panels_to_count = []
    w_a = calculate_panel_width_breakdown(dim_a)
    
    if is_column:
        w_b = calculate_panel_width_breakdown(dim_b if dim_b else dim_a)
        panels_to_count = w_a + w_a + w_b + w_b
    elif is_l_wall:
        w_b = calculate_panel_width_breakdown(dim_b if dim_b else dim_a)
        w_inner_a = calculate_panel_width_breakdown(max(10, dim_a - t))
        w_inner_b = calculate_panel_width_breakdown(max(10, (dim_b if dim_b else dim_a) - t))
        panels_to_count = w_a + w_b + w_inner_a + w_inner_b
    elif is_u_wall:
        m_len = dim_b if dim_b else dim_a
        w_m = calculate_panel_width_breakdown(m_len)
        w_side = calculate_panel_width_breakdown(dim_a)
        w_inner_m = calculate_panel_width_breakdown(max(10, m_len - 2 * t))
        panels_to_count = w_m + w_side + w_side + w_inner_m
    else:
        panels_to_count = w_a + w_a

    for h in h_levels:
        for w in panels_to_count:
            code = format_panel_code(w, h)
            bom[code] = bom.get(code, 0) + 1

    # Всички изчисления на аксесоари и ъгли се извикват изцяло от accessories_calculator.py
    acc_res = calculate_accessories(
        wall_type=wall_type,
        dim_a_cm=dim_a,
        dim_b_cm=dim_b if dim_b else dim_a,
        height_cm=height_cm,
        width_breakdown_a=w_a,
        height_breakdown=h_levels
    )
    
    for item_code, item_qty in acc_res["bom_summary"].items():
        bom[item_code] = bom.get(item_code, 0) + item_qty

    return bom
    
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

    cell_style = ParagraphStyle('CellText', parent=styles['Normal'], fontName=font_name, fontSize=8, leading=10)
    cell_bold_style = ParagraphStyle('CellTextBold', parent=styles['Normal'], fontName=font_bold, fontSize=8, leading=10, textColor=colors.white)

    story = []
    
    client = proj_info.get('client') or 'Няма посочен клиент'
    project = proj_info.get('project') or 'Обект TEKO'
    
    story.append(Paragraph("<b>КОФРАЖНА СИСТЕМА TEKO / TEKO FORMWORK SYSTEM</b>", title_style))
    story.append(Paragraph(f"<b>Обект:</b> {project} | <b>Клиент:</b> {client}", subtitle_style))
    story.append(Spacer(1, 8))

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
        
    t_summary = Table(table_data, colWidths=[30, 260, 100, 100])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('TOPPADDING', (0, 0), (-1, 0), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9F9F9')])
    ]))
    
    story.append(t_summary)
    story.append(PageBreak())

    overview_buf = generate_overall_project_3d_buf(pdf_elements)
    img_overview = RLImage(overview_buf, width=480, height=224)
    story.append(img_overview)
    story.append(Spacer(1, 10))

    for elem in pdf_elements:
        story.append(PageBreak())
        
        e_name = elem.get('name', 'Елемент')
        w_type = elem.get('wall_type', 'Стена')
        l_a = elem.get('length_a_cm', 100)
        l_b = elem.get('length_b_cm', 100)
        h_cm = elem.get('height_cm', 300)
        thick = elem.get('thickness_cm', 30)

        story.append(Paragraph(f"<b>Чертеж и Спецификация: {e_name}</b>", title_style))
        story.append(Paragraph(f"<b>Тип:</b> {w_type} | <b>Размери:</b> {int(l_a)}х{int(l_b)} см | <b>Височина:</b> {int(h_cm)} cm", subtitle_style))
        story.append(Spacer(1, 4))

        top_buf = generate_top_view_buf(w_type, l_a, l_b, thick, name=e_name)
        iso_buf = generate_3d_axonometry_buf(w_type, l_a, l_b, h_cm, thick, name=e_name)
        
        img_top = RLImage(top_buf, width=230, height=165)
        img_iso = RLImage(iso_buf, width=230, height=165)

        t_views = Table([[
            Paragraph("<b>Изглед отгоре (Top View)</b>", cell_style),
            Paragraph("<b>3D Изометрия (3D View)</b>", cell_style)
        ], [
            img_top, img_iso
        ]], colWidths=[240, 240])
        
        t_views.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(t_views)
        story.append(Spacer(1, 4))

        front_buf = generate_front_view_buf(w_type, l_a, l_b, h_cm, name=e_name)
        img_front = RLImage(front_buf, width=475, height=205)
        story.append(img_front)
        story.append(Spacer(1, 6))

        story.append(Paragraph("<b>Необходим артикул за елемента</b>", title_style))
        story.append(Spacer(1, 2))

        elem_bom = calculate_element_bom(w_type, l_a, l_b, h_cm, name=e_name, thickness_cm=thick)
        elem_table_data = [[
            Paragraph("<b>Артикул / Код</b>", cell_bold_style),
            Paragraph("<b>Количество (бр.)</b>", cell_bold_style)
        ]]

        for ec, eq in sorted(elem_bom.items()):
            elem_table_data.append([
                Paragraph(str(ec), cell_style),
                Paragraph(str(eq), cell_style)
            ])

        t_elem = Table(elem_table_data, colWidths=[320, 160])
        t_elem.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
            ('TOPPADDING', (0, 0), (-1, 0), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9F9F9')])
        ]))
        story.append(t_elem)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
