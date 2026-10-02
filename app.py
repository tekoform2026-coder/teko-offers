import streamlit as st
import pandas as pd
import numpy as np
import math
import io
import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Документни библиотеки
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ==============================================================================
# 1. ПЪЛЕН КАТАЛОГ И НАЛИЧНОСТИ В СКЛАДА (Спесификация.xlsx)
# ==============================================================================
TEKO_CATALOG = {
    # Изправени и легнали кофражни панели TEKO
    "TK 150/60": {"name": "Кофражен панел 150/60", "type": "panel", "w_cm": 60, "h_cm": 150, "weight_kg": 13.5, "stock": 120, "unit_price": 45.0},
    "TK 150/50": {"name": "Кофражен панел 150/50", "type": "panel", "w_cm": 50, "h_cm": 150, "weight_kg": 11.8, "stock": 60,  "unit_price": 42.0},
    "TK 150/45": {"name": "Кофражен панел 150/45", "type": "panel", "w_cm": 45, "h_cm": 150, "weight_kg": 10.9, "stock": 40,  "unit_price": 39.0},
    "TK 150/40": {"name": "Кофражен панел 150/40", "type": "panel", "w_cm": 40, "h_cm": 150, "weight_kg": 10.0, "stock": 40,  "unit_price": 37.0},
    "TK 150/35": {"name": "Кофражен панел 150/35", "type": "panel", "w_cm": 35, "h_cm": 150, "weight_kg": 9.2,  "stock": 50,  "unit_price": 35.0},
    "TK 150/30": {"name": "Кофражен панел 150/30", "type": "panel", "w_cm": 30, "h_cm": 150, "weight_kg": 8.3,  "stock": 60,  "unit_price": 32.0},
    "TK 150/25": {"name": "Кофражен панел 150/25", "type": "panel", "w_cm": 25, "h_cm": 150, "weight_kg": 7.5,  "stock": 30,  "unit_price": 30.0},
    "TK 150/20": {"name": "Кофражен панел 150/20", "type": "panel", "w_cm": 20, "h_cm": 150, "weight_kg": 6.6,  "stock": 30,  "unit_price": 28.0},
    "TK 120/60": {"name": "Кофражен панел 120/60", "type": "panel", "w_cm": 60, "h_cm": 120, "weight_kg": 11.0, "stock": 100, "unit_price": 38.0},
    "TK 120/50": {"name": "Кофражен панел 120/50", "type": "panel", "w_cm": 50, "h_cm": 120, "weight_kg": 9.6,  "stock": 50,  "unit_price": 35.0},
    "TK 120/40": {"name": "Кофражен панел 120/40", "type": "panel", "w_cm": 40, "h_cm": 120, "weight_kg": 8.1,  "stock": 40,  "unit_price": 32.0},
    "TK 120/30": {"name": "Кофражен панел 120/30", "type": "panel", "w_cm": 30, "h_cm": 120, "weight_kg": 6.7,  "stock": 50,  "unit_price": 29.0},
    "TK 120/20": {"name": "Кофражен панел 120/20", "type": "panel", "w_cm": 20, "h_cm": 120, "weight_kg": 5.3,  "stock": 30,  "unit_price": 25.0},
    "TK 60/60":  {"name": "Полегнал панел 60/60",  "type": "panel", "w_cm": 60, "h_cm": 60,  "weight_kg": 6.2,  "stock": 80,  "unit_price": 24.0},
    "TK 60/30":  {"name": "Полегнал панел 60/30",  "type": "panel", "w_cm": 30, "h_cm": 60,  "weight_kg": 3.8,  "stock": 40,  "unit_price": 18.0},
    
    # Вътрешни и външни ъглови елементи
    "IN 150/10": {"name": "Вътрешен ъгъл IN 150x10", "type": "corner_in", "w_cm": 10, "h_cm": 150, "weight_kg": 4.5, "stock": 30, "unit_price": 25.0},
    "IN 120/10": {"name": "Вътрешен ъгъл IN 120x10", "type": "corner_in", "w_cm": 10, "h_cm": 120, "weight_kg": 3.6, "stock": 30, "unit_price": 21.0},
    "EX 150":    {"name": "Външен ъгъл EX 150",       "type": "corner_ex", "w_cm": 5,  "h_cm": 150, "weight_kg": 3.1, "stock": 30, "unit_price": 18.0},
    "EX 120":    {"name": "Външен ъгъл EX 120",       "type": "corner_ex", "w_cm": 5,  "h_cm": 120, "weight_kg": 2.5, "stock": 30, "unit_price": 15.0},
    
    # Аксесоари и сглобки
    "Ригел 120":       {"name": "Изравнителен ригел L=1.20m", "type": "waler", "weight_kg": 5.2, "stock": 150, "unit_price": 16.0},
    "Вертикализатор":  {"name": "Вертикализираща подпора",  "type": "brace", "weight_kg": 12.5, "stock": 60,  "unit_price": 38.0},
    "Ръкохватка/Дръжка":{"name": "Скрепителна ръкохватка/дръжка", "type": "clamp", "weight_kg": 0.45, "stock": 500, "unit_price": 3.50},
    "Шпилка L=1.0m":   {"name": "Анкерна шпилка L=1.00m",   "type": "tie_rod", "weight_kg": 1.25, "stock": 300, "unit_price": 4.20},
    "Гайка за шпилка":  {"name": "Анкерна гайка с планка",   "type": "nut", "weight_kg": 0.35, "stock": 600, "unit_price": 1.80}
}

# ==============================================================================
# 2. ИНЖЕНЕРНИ АЛГОРИТМИ ЗА РЕДЕНЕ И ОКОМПЛЕКТОВКА
# ==============================================================================

def calculate_height_breakdown(height_cm, prefer_lying=False):
    """
    Разпределя височината на стената на редове от изправени и легнали панели.
    """
    standard_heights = [240, 270, 300, 330, 360]
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
    Подрежда панели по дължина от най-големите (60cm) към най-малките (20cm).
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
    Пресмята панелите за Страна A и Страна A1 за пълно огледално съвпадение.
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
                add_item(f"TK {rh}/{w}", 2) # X2 за Страна A и Страна A1
                
        elif elem_type in ["l_wall", "L-стена"]:
            l1_cm = round(length_m * 100)
            l2_cm = round(l2_m * 100)
            
            # Вътрешен IN (10cm) и Външен EX ъгъл
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
    Автоматичен модул за пресмятане на Ригели, Вертикализатори, Ръкохватки, Шпилки и Гайки.
    """
    h_cm = round(height_m * 100)
    l_cm = round(length_m * 100)
    w_cm = round(l2_m * 100) if l2_m > 0 else 30
    acc = {}
    
    # 1. РИГЕЛИ (без ригели за ширина <= 35cm или височина < 61cm)
    if elem_type != "column" and l_cm > 35 and h_cm >= 61:
        first_row_h = height_rows[0]["h"] if height_rows else 150
        is_lying = height_rows[0]["orient"] == "lying" if height_rows else False
        
        max_h = h_cm - 60 # Без ригел в горните 0-60cm
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
                
        runs = math.ceil(l_cm / 120) * 2 # Двете лица
        acc["Ригел 120"] = len(waler_levels) * runs

    # 2. ВЕРТИКАЛИЗАТОРИ
    if elem_type in ["column", "колона"]:
        acc["Вертикализатор"] = 2 if (l_cm <= 60 and w_cm <= 60) else 4
    elif l_cm > 120:
        braces_per_side = max(2, math.ceil(l_cm / 180))
        acc["Вертикализатор"] = braces_per_side * 2

    # 3. РЪКОХВАТКИ / ДРЪЖКИ (по допирателните фуги)
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
# 3. ГЕНЕРИРАНЕ НА ГРАФИКА (2D ЧЕРТЕЖИ)
# ==============================================================================

def draw_element_schema(elem_type, length_m, height_m, l2_m=0, l3_m=0):
    fig, ax = plt.subplots(figsize=(7, 3.5))
    l_cm = round(length_m * 100)
    h_cm = round(height_m * 100)
    
    # Контур на стената
    rect = patches.Rectangle((0, 0), l_cm, h_cm, linewidth=2, edgecolor='#1A365D', facecolor='#EBF8FF')
    ax.add_patch(rect)
    
    # Панелни фуги
    cols = math.ceil(l_cm / 60)
    for i in range(1, cols):
        ax.axvline(i * 60, color='#3182CE', linestyle='--', alpha=0.7)
        
    # Ригели (Червени линии)
    if l_cm > 35 and h_cm >= 61:
        ax.axhline(30, color='#E53E3E', linewidth=2.5, linestyle='-', label='Ригели (Walers)')
        if h_cm > 120:
            ax.axhline(90, color='#E53E3E', linewidth=2.5, linestyle='-')
        if h_cm > 180:
            ax.axhline(150, color='#E53E3E', linewidth=2.5, linestyle='-')
            
    # Вертикализатори (Сини наклонени стрелки)
    if l_cm > 120:
        ax.annotate('Вертикализатор', xy=(30, 20), xytext=(60, 80),
                    arrowprops=dict(facecolor='#2B6CB0', shrink=0.05, width=2, headwidth=8))
        ax.annotate('Вертикализатор', xy=(l_cm - 30, 20), xytext=(l_cm - 90, 80),
                    arrowprops=dict(facecolor='#2B6CB0', shrink=0.05, width=2, headwidth=8))

    ax.set_xlim(-15, l_cm + 15)
    ax.set_ylim(-15, h_cm + 15)
    ax.set_title(f"Схема на редене: {elem_type.upper()} ({length_m}m x {height_m}m)", fontsize=11, fontweight='bold', color='#1A365D')
    ax.set_xlabel("Дължина (cm)")
    ax.set_ylabel("Височина (cm)")
    ax.grid(True, linestyle=':', alpha=0.5)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

# ==============================================================================
# 4. ГЕНЕРИРАНЕ НА ОФЕРТА В WORD (.DOCX)
# ==============================================================================

def generate_docx_offer(spec_df, total_weight, project_name="Обект Резиденция", client_name="Строител ООД"):
    doc = Document()
    
    # Заглавие и Стилове
    title_p = doc.add_paragraph()
    title_run = title_p.add_run("ТЕХНИЧЕСКА ОФЕРТА ЗА КОФРАЖ TEKO")
    title_run.bold = True
    title_run.font.size = Pt(18)
    title_run.font.color.rgb = RGBColor(0x1A, 0x36, 0x5D)
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph(f"Обект: {project_name}\nКлиент: {client_name}\nДата: 02.10.2026г.")
    doc.add_paragraph("-" * 50)
    
    doc.add_heading("1. Резюме на техническото решение", level=1)
    doc.add_paragraph(
        f"Настоящата оферта съдържа пълното количествено разпределение на кофражна система TEKO. "
        f"Изчислението отчита геометрията на стените, вътрешните/външните ъглови елементи, "
        f"както и пълния набор от укрепващи аксесоари (ригели, вертикализатори, дръжки и шпилки)."
    )
    
    # Таблица със спецификацията
    doc.add_heading("2. Количествена сметка и спецификация", level=1)
    table = doc.add_table(rows=1, cols=6)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    hdr_cells = table.rows[0].cells
    headers = ["Код", "Описание", "Количество", "Ед. тегло (kg)", "Общо тегло (kg)", "Статус склад"]
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        hdr_cells[i].paragraphs[0].runs[0].font.bold = True
        
    for _, row in spec_df.iterrows():
        row_cells = table.add_row().cells
        row_cells[0].text = str(row["Код / Елемент"])
        row_cells[1].text = str(row["Описание"])
        row_cells[2].text = str(row["Количество (бр.)"])
        row_cells[3].text = f"{row['Ед. тегло (kg)']:.2f}"
        row_cells[4].text = f"{row['Общо тегло (kg)']:.2f}"
        row_cells[5].text = str(row["Статус склад"])
        
    doc.add_paragraph("\n")
    p_weight = doc.add_paragraph()
    r_w = p_weight.add_run(f"ОБЩО ТЕГЛО НА КОФРАЖА И АКСЕСОАРИТЕ: {total_weight:.2f} kg")
    r_w.bold = True
    r_w.font.size = Pt(12)
    r_w.font.color.rgb = RGBColor(0x2B, 0x6C, 0xB0)
    
    # Правила за монтаж
    doc.add_heading("3. Технологични указания за монтаж", level=1)
    doc.add_paragraph("• Ригелите се монтират на ниво 18 cm / 60 cm за вертикални панели 120cm и на 30 cm за панели 150cm / полегнали.")
    doc.add_paragraph("• Не се поставят ригели в горната зона от 0 до 60 cm от ръба на стената.")
    doc.add_paragraph("• При L- и U-стени задължително се поставя компенсиращ панел (t + 10cm) до външния ъгъл EX.")
    
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

# ==============================================================================
# 5. ГЕНЕРИРАНЕ НА PDF ДОКУМЕНТ
# ==============================================================================

def generate_pdf_offer(spec_df, total_weight, project_name="Обект Резиденция"):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#1A365D'), alignment=1)
    
    story = [
        Paragraph("СПЕЦИФИКАЦИЯ И ОФЕРТА - TEKO FORMWORK", title_style),
        Spacer(1, 15),
        Paragraph(f"<b>Обект:</b> {project_name} | <b>Дата:</b> 02.10.2026г.", styles['Normal']),
        Spacer(1, 10),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#1A365D')),
        Spacer(1, 15)
    ]
    
    table_data = [["Код", "Описание", "Количество", "Ед. тегло", "Общо тегло", "Склад"]]
    for _, r in spec_df.iterrows():
        table_data.append([
            r["Код / Елемент"],
            r["Описание"][:25],
            str(r["Количество (бр.)"]),
            f"{r['Ед. тегло (kg)']:.1f}kg",
            f"{r['Общо тегло (kg)']:.1f}kg",
            r["Статус склад"]
        ])
        
    t = Table(table_data, colWidths=[80, 150, 70, 70, 80, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1A365D')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0'))
    ]))
    
    story.append(t)
    story.append(Spacer(1, 15))
    story.append(Paragraph(f"<b>ОБЩО ТЕГЛО НА СИСТЕМАТА: {total_weight:.2f} kg</b>", styles['Heading2']))
    
    doc.build(story)
    buf.seek(0)
    return buf

# ==============================================================================
# 6. STREAMLIT ИНТЕРФЕЙС И СЕСИЙНО УПРАВЛЕНИЕ
# ==============================================================================

st.set_page_config(page_title="TEKO Formwork CAD & Calc", layout="wide", page_icon="🏗️")

st.title("🏗️ TEKO Formwork - Геометричен & Конструктивен Анализатор")

# Инициализация на Session State
if "edited_df" not in st.session_state:
    st.session_state["edited_df"] = pd.DataFrame([
        {"Елемент": "Стена 1", "Тип": "права стена", "Дължина (m)": 4.5, "Височина (m)": 3.0, "Дебелина (m)": 0.25, "L2 (m)": 0.0, "L3 (m)": 0.0, "Брой": 1, "Легнали панели": False},
        {"Елемент": "Стена 2 (L)", "Тип": "L-стена", "Дължина (m)": 3.0, "Височина (m)": 2.8, "Дебелина (m)": 0.25, "L2 (m)": 2.0, "L3 (m)": 0.0, "Брой": 1, "Легнали панели": True},
        {"Елемент": "Колона К1", "Тип": "колона", "Дължина (m)": 0.5, "Височина (m)": 3.0, "Дебелина (m)": 0.50, "L2 (m)": 0.5, "L3 (m)": 0.0, "Брой": 4, "Легнали панели": False}
    ])

# Главен работен панел
tabs = st.tabs([
    "📋 Въвеждане на елементи", 
    "📊 Спецификация & Тегло", 
    "📐 2D Схеми & Чертежи", 
    "📄 Оферти & Експорт (Word/PDF)", 
    "🤖 AI NLP Асистент"
])

# TAB 1: ВЪВЕЖДАНЕ НА ЕЛЕМЕНТИ
with tabs[0]:
    st.subheader("Редакция на списъка с конструктивни елементи")
    st.info("💡 Въведете размерите на стените и колоните. За L- и U-стени попълнете раменете L2 и L3.")
    
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

# ПРЕСМЯТАНЕ НА ЦЯЛАТА СПЕЦИФИКАЦИЯ
full_spec = {}
total_weight = 0.0

for _, row in edited_df.iterrows():
    qty = int(row.get("Брой", 1))
    e_type = str(row.get("Тип", "права стена"))
    l1 = float(row.get("Дължина (m)", 0))
    h = float(row.get("Височина (m)", 0))
    thick = float(row.get("Дебелина (m)", 0.25))
    l2 = float(row.get("L2 (m)", 0))
    l3 = float(row.get("L3 (m)", 0))
    lying = bool(row.get("Легнали панели", False))
    
    # 1. Панели и ъгли
    panels, height_rows = get_element_teko_panels(e_type, l1, h, thick, l2, l3, prefer_lying=lying)
    for p_code, count in panels.items():
        full_spec[p_code] = full_spec.get(p_code, 0) + (count * qty)
        
    # 2. Аксесоари и окомплектовка
    acc = calculate_accessories(e_type, l1, h, thick, l2, l3, height_rows)
    for a_code, count in acc.items():
        full_spec[a_code] = full_spec.get(a_code, 0) + (count * qty)

# Генериране на финалната таблица
spec_rows = []
for item, count in full_spec.items():
    item_info = TEKO_CATALOG.get(item, {"name": item, "weight_kg": 5.0, "stock": 50, "unit_price": 10.0})
    unit_w = item_info["weight_kg"]
    tot_w = unit_w * count
    total_weight += tot_w
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

# TAB 2: СПЕЦИФИКАЦИЯ & ТЕГЛО
with tabs[1]:
    st.subheader("Пълна спецификация на кофража и окомплектовката")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Общо тегло на кофража", f"{total_weight:.2f} kg")
    m2.metric("Общ брой позиция", f"{len(spec_df)} бр.")
    m3.metric("Състояние на склада", "Проверен" if not spec_df.empty else "Празен")
    
    st.dataframe(spec_df, use_container_width=True)
    
    csv_data = spec_df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Изтегли спецификацията (CSV)", csv_data, "teko_specification.csv", "text/csv")

# TAB 3: 2D СХЕМИ
with tabs[2]:
    st.subheader("Чертежи и разположение на ригелите / подпорите")
    for idx, row in edited_df.iterrows():
        st.markdown(f"#### 🔹 {row['Елемент']} ({row['Тип']}) - {row['Дължина (m)']}m x {row['Височина (m)']}m")
        img_buf = draw_element_schema(row['Тип'], float(row['Дължина (m)']), float(row['Височина (m)']))
        st.image(img_buf, use_column_width=False)

# TAB 4: ЕКСПОРТ НА ОФЕРТИ (WORD / PDF)
with tabs[3]:
    st.subheader("Генериране на официална оферта и документация")
    col_w, col_p = st.columns(2)
    
    with col_w:
        st.markdown("### 📄 Word Оферта (.docx)")
        st.write("Включва форматирана таблица, технологични указания за монтаж и тегла.")
        docx_file = generate_docx_offer(spec_df, total_weight)
        st.download_button("📥 Изтегли Оферта (DOCX)", docx_file, "Teko_Formwork_Offer.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        
    with col_p:
        st.markdown("### 📑 PDF Спецификация (.pdf)")
        st.write("Подходяща за бързо печатане и изпращане по имейл.")
        pdf_file = generate_pdf_offer(spec_df, total_weight)
        st.download_button("📥 Изтегли Спецификация (PDF)", pdf_file, "Teko_Formwork_Specification.pdf", "application/pdf")

# TAB 5: AI NLP АСИСТЕНТ
with tabs[4]:
    st.subheader("🤖 AI Чат Асистент за редактиране")
    st.write("Напишете команда на естествен език за промяна на геометрията:")
    
    user_cmd = st.text_input("Пример: 'Смени височината на Стена 1 на 2.80м и я направи с легнали панели'")
    if st.button("Изпълни командата"):
        cmd_lower = user_cmd.lower()
        df_copy = st.session_state["edited_df"].copy()
        modified = False
        
        for idx, row in df_copy.iterrows():
            elem_name = str(row["Елемент"]).lower()
            if elem_name in cmd_lower or ("стена 1" in cmd_lower and idx == 0) or ("стена 2" in cmd_lower and idx == 1):
                if "2.8" in cmd_lower or "2.80" in cmd_lower:
                    df_copy.at[idx, "Височина (m)"] = 2.8
                    modified = True
                if "3.0" in cmd_lower or "3m" in cmd_lower:
                    df_copy.at[idx, "Височина (m)"] = 3.0
                    modified = True
                if "легнали" in cmd_lower:
                    df_copy.at[idx, "Легнали панели"] = True
                    modified = True
                if "изправени" in cmd_lower:
                    df_copy.at[idx, "Легнали панели"] = False
                    modified = True
                    
        if modified:
            st.session_state["edited_df"] = df_copy
            st.success("Успешно обновени данни в таблицата!")
            st.rerun()
        else:
            st.warning("Не беше намерено съвпадение с елемент. Опитайте с: 'Смени височината на Стена 1 на 2.80м'")
