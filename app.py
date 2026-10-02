import streamlit as st
import pandas as pd
import numpy as np
import math
import io
import json
import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Импорт за Работа с Word (.docx) и Oxml форматиране
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

# Импорт за Работа с PDF (ReportLab)
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

# ==============================================================================
# 1. ПЪЛНА НОМЕНКЛАТУРА, КАТАЛОГ И СКЛАД (Спесификация.xlsx)
# ==============================================================================
TEKO_CATALOG = {
    # 1.1 Вертикални и полегнали основни кофражни панели (Серия TK 150)
    "TK 150/60": {"name": "Кофражен панел TEKO 150/60", "type": "panel", "w_cm": 60, "h_cm": 150, "weight_kg": 13.50, "stock": 150, "price_buy": 180.00, "price_rent_day": 0.45},
    "TK 150/50": {"name": "Кофражен панел TEKO 150/50", "type": "panel", "w_cm": 50, "h_cm": 150, "weight_kg": 11.80, "stock": 80,  "price_buy": 165.00, "price_rent_day": 0.42},
    "TK 150/45": {"name": "Кофражен панел TEKO 150/45", "type": "panel", "w_cm": 45, "h_cm": 150, "weight_kg": 10.90, "stock": 60,  "price_buy": 155.00, "price_rent_day": 0.39},
    "TK 150/40": {"name": "Кофражен панел TEKO 150/40", "type": "panel", "w_cm": 40, "h_cm": 150, "weight_kg": 10.00, "stock": 60,  "price_buy": 148.00, "price_rent_day": 0.37},
    "TK 150/35": {"name": "Кофражен панел TEKO 150/35", "type": "panel", "w_cm": 35, "h_cm": 150, "weight_kg": 9.20,  "stock": 70,  "price_buy": 140.00, "price_rent_day": 0.35},
    "TK 150/30": {"name": "Кофражен панел TEKO 150/30", "type": "panel", "w_cm": 30, "h_cm": 150, "weight_kg": 8.30,  "stock": 90,  "price_buy": 130.00, "price_rent_day": 0.32},
    "TK 150/25": {"name": "Кофражен панел TEKO 150/25", "type": "panel", "w_cm": 25, "h_cm": 150, "weight_kg": 7.50,  "stock": 50,  "price_buy": 120.00, "price_rent_day": 0.30},
    "TK 150/20": {"name": "Кофражен панел TEKO 150/20", "type": "panel", "w_cm": 20, "h_cm": 150, "weight_kg": 6.60,  "stock": 50,  "price_buy": 110.00, "price_rent_day": 0.28},

    # 1.2 Вертикални кофражни панели (Серия TK 120)
    "TK 120/60": {"name": "Кофражен панел TEKO 120/60", "type": "panel", "w_cm": 60, "h_cm": 120, "weight_kg": 11.00, "stock": 120, "price_buy": 150.00, "price_rent_day": 0.38},
    "TK 120/50": {"name": "Кофражен панел TEKO 120/50", "type": "panel", "w_cm": 50, "h_cm": 120, "weight_kg": 9.60,  "stock": 60,  "price_buy": 138.00, "price_rent_day": 0.35},
    "TK 120/40": {"name": "Кофражен панел TEKO 120/40", "type": "panel", "w_cm": 40, "h_cm": 120, "weight_kg": 8.10,  "stock": 50,  "price_buy": 125.00, "price_rent_day": 0.32},
    "TK 120/30": {"name": "Кофражен панел TEKO 120/30", "type": "panel", "w_cm": 30, "h_cm": 120, "weight_kg": 6.70,  "stock": 60,  "price_buy": 115.00, "price_rent_day": 0.29},
    "TK 120/20": {"name": "Кофражен панел TEKO 120/20", "type": "panel", "w_cm": 20, "h_cm": 120, "weight_kg": 5.30,  "stock": 40,  "price_buy": 100.00, "price_rent_day": 0.25},

    # 1.3 Полегнали доборни панели (Серия TK 60)
    "TK 60/60":  {"name": "Полегнал кофражен панел TEKO 60/60", "type": "panel", "w_cm": 60, "h_cm": 60, "weight_kg": 6.20, "stock": 100, "price_buy": 95.00,  "price_rent_day": 0.24},
    "TK 60/50":  {"name": "Полегнал кофражен панел TEKO 60/50", "type": "panel", "w_cm": 50, "h_cm": 60, "weight_kg": 5.20, "stock": 50,  "price_buy": 88.00,  "price_rent_day": 0.22},
    "TK 60/40":  {"name": "Полегнал кофражен панел TEKO 60/40", "type": "panel", "w_cm": 40, "h_cm": 60, "weight_kg": 4.30, "stock": 50,  "price_buy": 80.00,  "price_rent_day": 0.20},
    "TK 60/30":  {"name": "Полегнал кофражен панел TEKO 60/30", "type": "panel", "w_cm": 30, "h_cm": 60, "weight_kg": 3.80, "stock": 60,  "price_buy": 72.00,  "price_rent_day": 0.18},

    # 1.4 Вътрешни и външни ъглови елементи
    "IN 150/10": {"name": "Вътрешен ъгъл IN 150x10x10", "type": "corner_in", "w_cm": 10, "h_cm": 150, "weight_kg": 4.50, "stock": 40, "price_buy": 85.00, "price_rent_day": 0.22},
    "IN 120/10": {"name": "Вътрешен ъгъл IN 120x10x10", "type": "corner_in", "w_cm": 10, "h_cm": 120, "weight_kg": 3.60, "stock": 40, "price_buy": 75.00, "price_rent_day": 0.19},
    "EX 150":    {"name": "Външен ъгъл EX 150",          "type": "corner_ex", "w_cm": 5,  "h_cm": 150, "weight_kg": 3.10, "stock": 40, "price_buy": 65.00, "price_rent_day": 0.16},
    "EX 120":    {"name": "Външен ъгъл EX 120",          "type": "corner_ex", "w_cm": 5,  "h_cm": 120, "weight_kg": 2.50, "stock": 40, "price_buy": 58.00, "price_rent_day": 0.14},

    # 1.5 Окомплектовка, укрепване и анкериране
    "Ригел 120":        {"name": "Изравнителен ригел L=1.20m",   "type": "waler",   "weight_kg": 5.20, "stock": 250, "price_buy": 48.00, "price_rent_day": 0.12},
    "Вертикализатор":   {"name": "Вертикализираща подпора 2.60m","type": "brace",   "weight_kg": 12.50,"stock": 80,  "price_buy": 115.00,"price_rent_day": 0.35},
    "Ръкохватка/Дръжка": {"name": "Скрепителна дръжка/стяга TEKO","type": "clamp",   "weight_kg": 0.45, "stock": 1000,"price_buy": 12.50, "price_rent_day": 0.04},
    "Шпилка L=1.0m":    {"name": "Анкерна шпилка DW15 L=1.00m", "type": "tie_rod", "weight_kg": 1.25, "stock": 600, "price_buy": 9.80,  "price_rent_day": 0.03},
    "Гайка за шпилка":   {"name": "Анкерна гайка с планка DW15", "type": "nut",     "weight_kg": 0.35, "stock": 1200,"price_buy": 5.40,  "price_rent_day": 0.02}
}

# ==============================================================================
# 2. ДЕТАЙЛНИ ИНЖЕНЕРНИ АЛГОРИТМИ И ЛОГИКА
# ==============================================================================

def calculate_height_breakdown(height_cm, prefer_lying=False):
    """
    Пресмята вертикалната комбинация от редове панели за дадена височина.
    Спазва изискванията за поставяне на легнали панели (60cm) при нестандартни височини.
    """
    standard_heights = [120, 150, 240, 270, 300, 330, 360]
    rows = []
    
    if prefer_lying or height_cm not in standard_heights:
        rem = height_cm
        while rem > 0:
            if rem >= 150:
                rows.append({"h": 150, "orient": "vertical"})
                rem -= 150
            elif rem >= 120:
                rows.append({"h": 120, "orient": "vertical"})
                rem -= 120
            elif rem >= 60:
                rows.append({"h": 60, "orient": "lying"})
                rem -= 60
            else:
                rows.append({"h": 60, "orient": "lying"})
                rem = 0
    else:
        rem = height_cm
        while rem > 0:
            if rem >= 150:
                rows.append({"h": 150, "orient": "vertical"})
                rem -= 150
            elif rem >= 120:
                rows.append({"h": 120, "orient": "vertical"})
                rem -= 120
            else:
                rows.append({"h": 60, "orient": "vertical"})
                rem = 0
                
    return rows

def layout_line_panels(length_cm):
    """
    Подрежда панели по дължината от най-широките кaм най-тесните.
    """
    widths = [60, 50, 45, 40, 35, 30, 25, 20]
    selected = []
    rem = length_cm
    while rem > 0:
        matched = False
        for w in widths:
            if rem >= w:
                selected.append(w)
                rem -= w
                matched = True
                break
        if not matched:
            selected.append(20)
            rem = 0
    return selected

def get_element_teko_panels(elem_type, length_m, height_m, thickness_m=0.25, l2_m=0, l3_m=0, prefer_lying=False):
    """
    Основна изчислителна функция за брой и видове кофражни панели и ъгли.
    Гарантира стриктно огледално застъпване за Лице A и Лице A1.
    """
    h_cm = round(height_m * 100)
    t_cm = round(thickness_m * 100)
    height_rows = calculate_height_breakdown(h_cm, prefer_lying)
    
    panel_counts = {}
    def add_item(code, qty=1):
        panel_counts[code] = panel_counts.get(code, 0) + qty

    for row in height_rows:
        rh = row["h"]
        
        if elem_type in ["wall", "права стена"]:
            l_cm = round(length_m * 100)
            row_widths = layout_line_panels(l_cm)
            for w in row_widths:
                add_item(f"TK {rh}/{w}", 2) # X2 за Лице A и Лице A1 (огледално)
                
        elif elem_type in ["l_wall", "L-стена"]:
            l1_cm = round(length_m * 100)
            l2_cm = round(l2_m * 100)
            
            in_code = f"IN {rh}/10" if rh in [120, 150] else "IN 120/10"
            ex_code = f"EX {rh}" if rh in [120, 150] else "EX 120"
            add_item(in_code, 1)
            add_item(ex_code, 1)
            
            # Компенсиращ панел до EX с ширина = t + 10cm
            ex_adj_w = min(60, t_cm + 10)
            add_item(f"TK {rh}/{ex_adj_w}", 2)
            
            for w in layout_line_panels(max(0, l1_cm - t_cm)):
                add_item(f"TK {rh}/{w}", 2)
            for w in layout_line_panels(max(0, l2_cm - t_cm)):
                add_item(f"TK {rh}/{w}", 2)

        elif elem_type in ["u_wall", "U-стена"]:
            l1_cm = round(length_m * 100)
            l2_cm = round(l2_m * 100)
            l3_cm = round(l3_m * 100)
            
            in_code = f"IN {rh}/10" if rh in [120, 150] else "IN 120/10"
            ex_code = f"EX {rh}" if rh in [120, 150] else "EX 120"
            add_item(in_code, 2)
            add_item(ex_code, 2)
            
            ex_adj_w = min(60, t_cm + 10)
            add_item(f"TK {rh}/{ex_adj_w}", 4)
            
            for w in layout_line_panels(max(0, l1_cm - t_cm)):
                add_item(f"TK {rh}/{w}", 2)
            for w in layout_line_panels(max(0, l2_cm - 2 * t_cm)):
                add_item(f"TK {rh}/{w}", 2)
            for w in layout_line_panels(max(0, l3_cm - t_cm)):
                add_item(f"TK {rh}/{w}", 2)

        elif elem_type in ["column", "колона"]:
            l_cm = round(length_m * 100)
            w_cm = round(l2_m * 100) if l2_m > 0 else l_cm
            for w in layout_line_panels(l_cm):
                add_item(f"TK {rh}/{w}", 2)
            for w in layout_line_panels(w_cm):
                add_item(f"TK {rh}/{w}", 2)

        elif elem_type in ["embedded_column", "вградена колона"]:
            l_cm = round(length_m * 100)
            col_w = round(l2_m * 100) if l2_m > 0 else 40
            ex_code = f"EX {rh}" if rh in [120, 150] else "EX 120"
            add_item(ex_code, 2)
            for w in layout_line_panels(l_cm):
                add_item(f"TK {rh}/{w}", 2)
            for w in layout_line_panels(col_w):
                add_item(f"TK {rh}/{w}", 2)

    return panel_counts, height_rows

def calculate_accessories(elem_type, length_m, height_m, thickness_m=0.25, l2_m=0, l3_m=0, height_rows=None):
    """
    Пресмята автоматично необходимите ригели, подпори, стъги/дръжки, шпилки и гайки.
    """
    h_cm = round(height_m * 100)
    l_cm = round(length_m * 100)
    w_cm = round(l2_m * 100) if l2_m > 0 else 30
    acc = {}
    
    # 1. РИГЕЛИ (Изравнителни)
    if elem_type != "column" and l_cm > 35 and h_cm >= 61:
        first_row_h = height_rows[0]["h"] if height_rows else 150
        is_lying = height_rows[0]["orient"] == "lying" if height_rows else False
        
        max_h = h_cm - 60 # Без ригел в най-горните 0-60 cm
        waler_levels = []
        
        if first_row_h == 120 and not is_lying:
            if 18 <= max_h: waler_levels.append(18)
            curr = 60
            while curr <= max_h:
                waler_levels.append(curr)
                curr += 60
        else:
            curr = 30
            while curr <= max_h:
                waler_levels.append(curr)
                curr += 60
                
        runs = math.ceil(l_cm / 120) * 2 # За двете лица
        acc["Ригел 120"] = len(waler_levels) * runs

    # 2. ВЕРТИКАЛИЗАТОРИ
    if elem_type in ["column", "колона"]:
        acc["Вертикализатор"] = 2 if (l_cm <= 60 and w_cm <= 60) else 4
    elif l_cm > 120:
        braces_per_side = max(2, math.ceil(l_cm / 180))
        acc["Вертикализатор"] = braces_per_side * 2

    # 3. РЪКОХВАТКИ / ДРЪЖКИ
    cols_count = math.ceil(l_cm / 60)
    rows_count = len(height_rows) if height_rows else 1
    
    vertical_joints = max(0, cols_count - 1) * rows_count * 2
    horizontal_joints = max(0, rows_count - 1) * cols_count * 1
    acc["Ръкохватка/Дръжка"] = (vertical_joints + horizontal_joints) * 2

    # 4. ШПИЛКИ И ГАЙКИ
    tie_rods = cols_count * rows_count * 2
    acc["Шпилка L=1.0m"] = tie_rods
    acc["Гайка за шпилка"] = tie_rods * 2

    return acc

# ==============================================================================
# 3. ГРАФИКА И СХЕМИ (Matplotlib)
# ==============================================================================

def draw_element_schema(elem_type, length_m, height_m, l2_m=0, l3_m=0):
    """
    Генерира 2D техническа схема на кофражния разрез.
    """
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    l_cm = round(length_m * 100)
    h_cm = round(height_m * 100)
    
    # Външен контур
    rect = patches.Rectangle((0, 0), l_cm, h_cm, linewidth=2, edgecolor='#1A365D', facecolor='#EBF8FF')
    ax.add_patch(rect)
    
    # Вертикални фуги между панелите
    cols = math.ceil(l_cm / 60)
    for i in range(1, cols):
        ax.axvline(i * 60, color='#3182CE', linestyle='--', alpha=0.7)
        
    # Червени хоризонтални ригели
    if l_cm > 35 and h_cm >= 61:
        ax.axhline(30, color='#E53E3E', linewidth=2.5, linestyle='-', label='Изравнителни ригели')
        if h_cm > 120:
            ax.axhline(90, color='#E53E3E', linewidth=2.5, linestyle='-')
        if h_cm > 180:
            ax.axhline(150, color='#E53E3E', linewidth=2.5, linestyle='-')
            
    # Сини вертикализатори
    if l_cm > 120:
        ax.annotate('Вертикализатор', xy=(30, 20), xytext=(50, 80),
                    arrowprops=dict(facecolor='#2B6CB0', shrink=0.05, width=2, headwidth=7),
                    fontsize=9, color='#1A365D', fontweight='bold')
        ax.annotate('Вертикализатор', xy=(l_cm - 30, 20), xytext=(l_cm - 110, 80),
                    arrowprops=dict(facecolor='#2B6CB0', shrink=0.05, width=2, headwidth=7),
                    fontsize=9, color='#1A365D', fontweight='bold')

    ax.set_xlim(-15, l_cm + 15)
    ax.set_ylim(-15, h_cm + 15)
    ax.set_title(f"Схема на кофража: {elem_type.upper()} ({length_m:.2f}m x {height_m:.2f}m)", fontsize=11, fontweight='bold', color='#1A365D')
    ax.set_xlabel("Дължина (cm)")
    ax.set_ylabel("Височина (cm)")
    ax.grid(True, linestyle=':', alpha=0.5)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

# ==============================================================================
# 4. ФОРМАТИРАНЕ И ГЕНЕРИРАНЕ НА WORD (.DOCX) С OXML ПОМОЩНИЦИ
# ==============================================================================

def set_cell_background(cell, fill_hex):
    """Помощник за задаване на цвят на клетка в Word таблица."""
    tcPr = cell._element.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_table_borders(table, color="CCCCCC", sz="4", val="single"):
    """Помощник за граници на Word таблица."""
    tblPr = table._element.xpath('w:tblPr')
    if tblPr:
        borders = parse_xml(f'''
            <w:tblBorders {nsdecls("w")}>
                <w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
                <w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
                <w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
                <w:insideV w:val="none"/>
                <w:left w:val="none"/>
                <w:right w:val="none"/>
            </w:tblBorders>
        ''')
        tblPr[0].append(borders)

def generate_docx_offer(spec_df, total_weight, project_name="Обект Резиденция", client_name="Строител ООД"):
    """
    Генерира Word оферта с OXML стилизиране.
    """
    doc = Document()
    
    # Настройки на полетата
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)
        
    # Заглавна шапка
    p_header = doc.add_paragraph()
    r_title = p_header.add_run("ТЕХНИЧЕСКА И ТЪРГОВСКА ОФЕРТА")
    r_title.bold = True
    r_title.font.size = Pt(18)
    r_title.font.color.rgb = RGBColor(0x1A, 0x36, 0x5D)
    p_header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    p_sub = doc.add_paragraph()
    r_sub = p_sub.add_run("Модулни кофражни системи TEKO")
    r_sub.font.size = Pt(12)
    r_sub.font.color.rgb = RGBColor(0x4A, 0x55, 0x68)
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph().paragraph_format.space_after = Pt(10)
    
    # Метаданни
    p_meta = doc.add_paragraph()
    p_meta.add_run(f"Проект / Обект: ").bold = True
    p_meta.add_run(f"{project_name}\n")
    p_meta.add_run(f"Възложител / Клиент: ").bold = True
    p_meta.add_run(f"{client_name}\n")
    p_meta.add_run(f"Дата на офертата: ").bold = True
    p_meta.add_run(f"{datetime.date.today().strftime('%d.%m.%Y')} г.")
    
    doc.add_heading("1. Техническо описание на кофражната система", level=1)
    p_desc = doc.add_paragraph(
        "Предложената кофражна система TEKO е оразмерена съгласно геометрията на конструктивните елементи. "
        "Включени са всички необходими вертикални и полегнали панели, вътрешни и външни ъгли, "
        "както и укрепителната окомплектовка от изравнителни ригели, вертикализиращи подпори, стъги и анкерни шпилки."
    )
    p_desc.paragraph_format.line_spacing = 1.15
    
    doc.add_heading("2. Количествена сметка и спецификация", level=1)
    
    # Таблица
    table = doc.add_table(rows=1, cols=6)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table)
    
    hdr_cells = table.rows[0].cells
    headers = ["Код", "Описание", "Брой", "Ед. тегло", "Общо тегло", "Склад"]
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], "1A365D")
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in p.runs:
            r.font.bold = True
            r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            r.font.size = Pt(9.5)

    for idx, row in spec_df.iterrows():
        row_cells = table.add_row().cells
        bg_color = "F7FAFC" if idx % 2 == 0 else "FFFFFF"
        
        row_cells[0].text = str(row["Код / Елемент"])
        row_cells[1].text = str(row["Описание"])
        row_cells[2].text = str(row["Количество (бр.)"])
        row_cells[3].text = f"{row['Ед. тегло (kg)']:.2f} kg"
        row_cells[4].text = f"{row['Общо тегло (kg)']:.2f} kg"
        row_cells[5].text = str(row["Статус склад"])
        
        for c_idx, cell in enumerate(row_cells):
            set_cell_background(cell, bg_color)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.runs[0].font.size = Pt(9)
            if c_idx in [2, 3, 4, 5]:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    doc.add_paragraph().paragraph_format.space_after = Pt(10)
    
    # Обобщение на теглото
    p_tot = doc.add_paragraph()
    r_t1 = p_tot.add_run("ОБЩО ТЕГЛО НА КОФРАЖНАТА СИСТЕМА: ")
    r_t1.bold = True
    r_t1.font.size = Pt(11)
    r_t2 = p_tot.add_run(f"{total_weight:.2f} kg")
    r_t2.bold = True
    r_t2.font.size = Pt(12)
    r_t2.font.color.rgb = RGBColor(0x2B, 0x6C, 0xB0)
    
    doc.add_heading("3. Указания за монтаж и безопасност", level=1)
    doc.add_paragraph("1. Всички вертикални панели се свързват помежду си посредством скрепителни ръкохватки TEKO.")
    doc.add_paragraph("2. Изравнителните ригели се монтират на височинни нива 18cm/60cm или 30cm/90cm според типа панел.")
    doc.add_paragraph("3. Не се поставят ригели в горната зона от 0 до 60 cm под ръба на бетониране.")
    doc.add_paragraph("4. Подпорите (вертикализаторите) се фиксират през максимум 1.80m по хоризонтала.")

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

# ==============================================================================
# 5. ГЕНЕРИРАНЕ НА PDF ДОКУМЕНТ С REPORTLAB
# ==============================================================================

class NumberedCanvas(canvas.Canvas):
    """Номер на страница във формат Page X of Y."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#718096"))
        self.drawString(30, 20, "TEKO Formwork System — Официален кофражен отчет")
        self.drawRightString(565, 20, f"Страница {self._pageNumber} от {page_count}")
        self.restoreState()

def generate_pdf_offer(spec_df, total_weight, project_name="Обект Резиденция"):
    """
    Генерира многостраничен PDF файл.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'PDFTitle', parent=styles['Heading1'],
        fontSize=16, leading=20, textColor=colors.HexColor('#1A365D'),
        alignment=1, spaceAfter=10
    )
    
    story = [
        Paragraph("СПЕЦИФИКАЦИЯ И ОФЕРТА - TEKO FORMWORK", title_style),
        Spacer(1, 10),
        Paragraph(f"<b>Обект:</b> {project_name} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Дата:</b> {datetime.date.today().strftime('%d.%m.%Y')}г.", styles['Normal']),
        Spacer(1, 8),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1A365D'), spaceAfter=15)
    ]
    
    table_data = [["Код", "Описание", "Количество", "Ед. тегло", "Общо тегло", "Склад"]]
    for _, r in spec_df.iterrows():
        table_data.append([
            r["Код / Елемент"],
            r["Описание"][:26],
            str(r["Количество (бр.)"]),
            f"{r['Ед. тегло (kg)']:.1f} kg",
            f"{r['Общо тегло (kg)']:.1f} kg",
            r["Статус склад"]
        ])
        
    t = Table(table_data, colWidths=[75, 160, 65, 70, 80, 85])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1A365D')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F7FAFC')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('FONTSIZE', (0,1), (-1,-1), 8.5)
    ]))
    
    story.append(t)
    story.append(Spacer(1, 15))
    story.append(Paragraph(f"<b>ОБЩО ТЕГЛО НА ЕЛЕМЕНТИТЕ: {total_weight:.2f} kg</b>", styles['Heading2']))
    
    doc.build(story, canvasmaker=NumberedCanvas)
    buf.seek(0)
    return buf

# ==============================================================================
# 6. ИНТЕРФЕЙС И ПОТРЕБИТЕЛСКИ ПАНЕЛ (Streamlit)
# ==============================================================================

st.set_page_config(
    page_title="TEKO Formwork CAD & Calc",
    layout="wide",
    page_icon="🏗️",
    initial_sidebar_state="expanded"
)

# Custom CSS стилове за графичния интерфейс
st.markdown("""
<style>
    .main-header { font-size: 24px; color: #1A365D; font-weight: bold; }
    .stMetric { background-color: #F7FAFC; border: 1px solid #E2E8F0; padding: 10px; border-radius: 8px; }
    .stDataFrame { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

st.title("🏗️ TEKO Formwork — Геометричен & Конструктивен Анализатор")

# Странична лента (Sidebar)
with st.sidebar:
    st.header("⚙️ Параметри на проекта")
    project_name = st.text_input("Име на обекта", "Жилищна сграда — Секция А")
    client_name = st.text_input("Възложител", "Строител ЕООД")
    rental_days = st.number_input("Срок на наем (дни)", min_value=1, value=30)
    discount_pct = st.slider("Отстъпка (%)", 0, 30, 5)
    
    st.divider()
    st.caption("TEKO Systems v3.4 | София, България")

# Инициализация на Session State
if "edited_df" not in st.session_state:
    st.session_state["edited_df"] = pd.DataFrame([
        {"Елемент": "Стена 1", "Тип": "права стена", "Дължина (m)": 4.50, "Височина (m)": 3.00, "Дебелина (m)": 0.25, "L2 (m)": 0.00, "L3 (m)": 0.00, "Брой": 1, "Легнали панели": False},
        {"Елемент": "Стена 2 (L)", "Тип": "L-стена", "Дължина (m)": 3.00, "Височина (m)": 2.80, "Дебелина (m)": 0.25, "L2 (m)": 2.00, "L3 (m)": 0.00, "Брой": 1, "Легнали панели": True},
        {"Елемент": "Колона К1", "Тип": "колона", "Дължина (m)": 0.50, "Височина (m)": 3.00, "Дебелина (m)": 0.50, "L2 (m)": 0.50, "L3 (m)": 0.00, "Брой": 4, "Легнали панели": False}
    ])

# Вкладки (Tabs)
tabs = st.tabs([
    "📋 1. Геометрия & Елементи", 
    "📊 2. Спецификация & Наличности", 
    "📐 3. 2D Схеми на кофража", 
    "📄 4. Официални Оферти (Word/PDF)", 
    "🤖 5. AI NLP Интелигентен Чат"
])

# ------------------------------------------------------------------------------
# TAB 1: ГЕОМЕТРИЯ И ВЪВЕЖДАНЕ
# ------------------------------------------------------------------------------
with tabs[0]:
    st.subheader("Списък на конструктивните елементи за кофраж")
    st.caption("ℹ️ Настройте геометрията на стените и колоните. За L- и U-стени попълнете допълнителните рамена L2 и L3.")
    
    edited_df = st.data_editor(
        st.session_state["edited_df"],
        num_rows="dynamic",
        column_config={
            "Тип": st.column_config.SelectboxColumn(
                "Тип геометрия",
                options=["права стена", "L-стена", "U-стена", "колона", "вградена колона"],
                required=True
            ),
            "Легнали панели": st.column_config.CheckboxColumn("Приоритет легнали панели")
        },
        use_container_width=True
    )
    st.session_state["edited_df"] = edited_df

# ==============================================================================
# ИЗЧИСЛИТЕЛЕН БЛОК
# ==============================================================================
full_spec = {}
total_weight = 0.0
total_buy_price = 0.0
total_rent_per_day = 0.0

for _, row in edited_df.iterrows():
    qty = int(row.get("Брой", 1))
    e_type = str(row.get("Тип", "права стена"))
    l1 = float(row.get("Дължина (m)", 0))
    h = float(row.get("Височина (m)", 0))
    thick = float(row.get("Дебелина (m)", 0.25))
    l2 = float(row.get("L2 (m)", 0))
    l3 = float(row.get("L3 (m)", 0))
    lying = bool(row.get("Легнали панели", False))
    
    # 1. Изчисление на панели и ъгли
    panels, height_rows = get_element_teko_panels(e_type, l1, h, thick, l2, l3, prefer_lying=lying)
    for p_code, count in panels.items():
        full_spec[p_code] = full_spec.get(p_code, 0) + (count * qty)
        
    # 2. Изчисление на окомплектовка (ригели, подпори, стъги, шпилки)
    acc = calculate_accessories(e_type, l1, h, thick, l2, l3, height_rows)
    for a_code, count in acc.items():
        full_spec[a_code] = full_spec.get(a_code, 0) + (count * qty)

# Генериране на обобщена спецификация
spec_rows = []
for item, count in full_spec.items():
    item_info = TEKO_CATALOG.get(item, {"name": item, "weight_kg": 5.0, "stock": 50, "price_buy": 20.0, "price_rent_day": 0.10})
    unit_w = item_info["weight_kg"]
    tot_w = unit_w * count
    total_weight += tot_w
    
    buy_p = item_info["price_buy"] * count
    rent_p = item_info["price_rent_day"] * count
    total_buy_price += buy_p
    total_rent_per_day += rent_p
    
    stock_qty = item_info["stock"]
    status = "✅ Наличен" if stock_qty >= count else f"⚠️ Недостиг ({count - stock_qty} бр.)"
    
    spec_rows.append({
        "Код / Елемент": item,
        "Описание": item_info["name"],
        "Количество (бр.)": count,
        "Ед. тегло (kg)": unit_w,
        "Общо тегло (kg)": round(tot_w, 2),
        "Склад (налично)": stock_qty,
        "Статус склад": status
    })

spec_df = pd.DataFrame(spec_rows)

# ------------------------------------------------------------------------------
# TAB 2: СПЕЦИФИКАЦИЯ И НАЛИЧНОСТИ
# ------------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Количествена спецификация и анализ на наличностите")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Общо тегло", f"{total_weight:.2f} kg")
    m2.metric("Позиции в спецификацията", f"{len(spec_df)} бр.")
    m3.metric("Цена при покупка (без ДДС)", f"{total_buy_price * (1 - discount_pct/100):,.2f} лв.")
    m4.metric(f"Наем за {rental_days} дни", f"{total_rent_per_day * rental_days * (1 - discount_pct/100):,.2f} лв.")
    
    st.dataframe(spec_df, use_container_width=True, height=400)
    
    csv_data = spec_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 Изтегли спецификацията (CSV)", csv_data, "teko_specification.csv", "text/csv")

# ------------------------------------------------------------------------------
# TAB 3: 2D СХЕМИ
# ------------------------------------------------------------------------------
with tabs[2]:
    st.subheader("2D Графични схеми за подреждане на кофража")
    for idx, row in edited_df.iterrows():
        st.markdown(f"##### 🔹 Елемент: **{row['Елемент']}** ({row['Тип']}) — {row['Дължина (m)']}m x {row['Височина (m)']}m")
        img_buf = draw_element_schema(row['Тип'], float(row['Дължина (m)']), float(row['Височина (m)']))
        st.image(img_buf, use_column_width=False)

# ------------------------------------------------------------------------------
# TAB 4: ЕКСПОРТ НА ДОКУМЕНТИ
# ------------------------------------------------------------------------------
with tabs[3]:
    st.subheader("Генериране на официални документи за оферта")
    c_docx, c_pdf = st.columns(2)
    
    with c_docx:
        st.markdown("### 📄 Word Оферта (.docx)")
        st.write("Генерира форматиран Word документ с пълна спецификация, правила за монтаж и OXML таблици.")
        docx_file = generate_docx_offer(spec_df, total_weight, project_name=project_name, client_name=client_name)
        st.download_button(
            "📥 Изтегли Оферта (DOCX)", 
            docx_file, 
            f"Teko_Offer_{project_name}.docx", 
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
    with c_pdf:
        st.markdown("### 📑 PDF Документ (.pdf)")
        st.write("Генерира многостраничен PDF файл с динамично странициране (Page X of Y) за печат.")
        pdf_file = generate_pdf_offer(spec_df, total_weight, project_name=project_name)
        st.download_button(
            "📥 Изтегли Спецификация (PDF)", 
            pdf_file, 
            f"Teko_Spec_{project_name}.pdf", 
            "application/pdf"
        )

# ------------------------------------------------------------------------------
# TAB 5: AI NLP АСИСТЕНТ
# ------------------------------------------------------------------------------
with tabs[4]:
    st.subheader("🤖 AI Асистент за гласови/текстови команди")
    st.write("Въведете инструкция на естествен български език за коригиране на таблицата с елементи:")
    
    user_cmd = st.text_input("Команда (напр. 'Промени височината на Стена 1 на 2.80м и добави легнали панели')", key="nlp_cmd")
    if st.button("Приложи командата"):
        cmd_lower = user_cmd.lower()
        df_copy = st.session_state["edited_df"].copy()
        modified = False
        
        for idx, row in df_copy.iterrows():
            elem_name = str(row["Елемент"]).lower()
            if elem_name in cmd_lower or ("стена 1" in cmd_lower and idx == 0) or ("стена 2" in cmd_lower and idx == 1):
                if "2.8" in cmd_lower or "2.80" in cmd_lower:
                    df_copy.at[idx, "Височина (m)"] = 2.80
                    modified = True
                if "3.0" in cmd_lower or "3.00" in cmd_lower or "3m" in cmd_lower:
                    df_copy.at[idx, "Височина (m)"] = 3.00
                    modified = True
                if "легнали" in cmd_lower:
                    df_copy.at[idx, "Легнали панели"] = True
                    modified = True
                if "изправени" in cmd_lower:
                    df_copy.at[idx, "Легнали панели"] = False
                    modified = True
                    
        if modified:
            st.session_state["edited_df"] = df_copy
            st.success("Успешно актуализиране на геометрията въз основа на командата!")
            st.rerun()
        else:
            st.warning("Командата не прихвана конкретен елемент. Опитайте с: 'Промени височината на Стена 1 на 2.80м'")
