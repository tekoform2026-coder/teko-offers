import io
import hmac
import fitz  # PyMuPDF
import pandas as pd
from PIL import Image
import streamlit as st
import docx
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from gemini_agent2 import analyze_blueprint
from drawing_generator import generate_pdf_drawings, calculate_element_bom
from accessories_calculator import calculate_accessories
from weights_db import get_item_weight

st.set_page_config(
    page_title="TEKO - Вертикален Кофраж и Оферти",
    page_icon="🏗",
    layout="wide"
)

# === СИСТЕМА ЗА ЗАЩИТА С ПАРОЛА (ВРЕМЕННО ИЗКЛЮЧЕНА) ===
def check_password():
    """Временно пропуска проверката и пуска директно в системата."""
    return True

if not check_password():
    st.stop()
# =======================================================

def set_cell_background(cell, hex_color):
    """Задава цвят на фона на клетка от таблица."""
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def calculate_height_breakdown(height_cm):
    """
    Разбива височината САМО на стандартни TEKO височини: 150, 120, 60 cm.
    Всеки остатък под 60 cm се закръглява към стандартен модул от 60 cm.
    """
    height_cm = round(height_cm)
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
        height_levels.append(60)
        
    return height_levels

# === СТЪПКА 3: Описание на редовете по височина ===
def format_height_breakdown_text(height_m):
    """
    Форматира височината на елемента в ясен текст за използваните нива от панели.
    """
    h_cm = round(float(height_m or 3.0) * 100)
    h_levels = calculate_height_breakdown(h_cm)
    parts = []
    for idx, h_val in enumerate(h_levels, 1):
        if h_val == 60:
            parts.append(f"Ред {idx}: Полегнал (60 cm)")
        else:
            parts.append(f"Ред {idx}: Изправен ({h_val} cm)")
    return " | ".join(parts)

# === СТЪПКА 4: Проверка за нестандартни размери ===
def check_element_dimensions(row):
    """
    Проверява дали въведените размери са кратни на стандартните модули на TEKO (5 cm за ширина, 10 cm за височина).
    """
    warnings = []
    h_val = row.get("height_m")
    h_m = float(h_val) if pd.notna(h_val) and h_val != "" else 3.0
    h_cm = round(h_m * 100)
    elem_type = str(row.get("type", "wall"))
    name = format_element_label(elem_type, str(row.get("name", "Елемент")))

    if h_cm % 10 != 0:
        warnings.append(f"• **{name}**: Височина {h_cm} cm не е кратна на 10 cm (закръгля се към най-близкия модул).")

    if elem_type == "column":
        w_val = row.get("width_m")
        l_val = row.get("length_m")
        w_cm = round((float(w_val) if pd.notna(w_val) and w_val != "" else 0.3) * 100)
        l_cm = round((float(l_val) if pd.notna(l_val) and l_val != "" else 0.5) * 100)
        if w_cm % 5 != 0 or l_cm % 5 != 0:
            warnings.append(f"• **{name}**: Размерите ({w_cm}x{l_cm} cm) не са кратни на 5 cm. Запълва се с компенсатор TC 5.")
    elif elem_type == "wall":
        l_val = row.get("length_m")
        l_cm = round((float(l_val) if pd.notna(l_val) and l_val != "" else 5.0) * 100)
        if l_cm % 5 != 0:
            warnings.append(f"• **{name}**: Дължината {l_cm} cm не е кратна на 5 cm. Запълва се с компенсатор TC 5.")
    elif elem_type == "l_wall":
        l1_val = row.get("l1_m")
        l2_val = row.get("l2_m")
        l1_cm = round((float(l1_val) if pd.notna(l1_val) and l1_val != "" else 2.0) * 100)
        l2_cm = round((float(l2_val) if pd.notna(l2_val) and l2_val != "" else 2.0) * 100)
        if l1_cm % 5 != 0 or l2_cm % 5 != 0:
            warnings.append(f"• **{name}**: Раменете ({l1_cm} cm / {l2_cm} cm) съдържат стойности некратни на 5 cm.")
    elif elem_type == "u_wall":
        l1_val = row.get("l1_m")
        l2_val = row.get("l2_m")
        l3_val = row.get("l3_m")
        l1_cm = round((float(l1_val) if pd.notna(l1_val) and l1_val != "" else 2.0) * 100)
        l2_cm = round((float(l2_val) if pd.notna(l2_val) and l2_val != "" else 2.0) * 100)
        l3_cm = round((float(l3_val) if pd.notna(l3_val) and l3_val != "" else 2.0) * 100)
        if l1_cm % 5 != 0 or l2_cm % 5 != 0 or l3_cm % 5 != 0:
            warnings.append(f"• **{name}**: Раменете ({l1_cm}/{l2_cm}/{l3_cm} cm) съдържат стойности некратни на 5 cm.")

    return warnings

def calculate_panel_width_breakdown(width_cm):
    """
    Разбива ширината САМО с основни TEKO панели (60, 35, 30, 25, 20 cm).
    Компенсаторите (15, 10, 5 cm) не се използват за основното редене по ширина.
    """
    width_cm = round(width_cm)
    panel_widths = [60, 35, 30, 25, 20]
    
    remaining = width_cm
    result_panels = {}
    
    for w in panel_widths:
        count = remaining // w
        if count > 0:
            result_panels[f"TK _{int(w)}"] = int(count)
            remaining -= count * w
            
    if remaining > 0:
        result_panels["TK _20"] = result_panels.get("TK _20", 0) + 1
        
    return result_panels

def get_element_teko_panels(elem_type, row):
    c_val = row.get("count")
    cnt = int(float(c_val) if pd.notna(c_val) and c_val != "" else 1)
    h_val = row.get("height_m")
    h_m = float(h_val) if pd.notna(h_val) and h_val != "" else 3.0
    h_cm = h_m * 100
    h_levels = calculate_height_breakdown(h_cm)
    
    element_panels = {}
    
    def add_face_panels(face_width_cm):
        p_breakdown = calculate_panel_width_breakdown(face_width_cm)
        for h_val in h_levels:
            for p_code, p_cnt in p_breakdown.items():
                w_val = int(p_code.split("_")[1])
                
                if int(h_val) == 60 and w_val == 60:
                    panel_name = "TK 150/60 (полегнал)"
                elif int(h_val) == 60:
                    panel_name = f"TK 60/{w_val}"
                elif "TC" in p_code and w_val <= 15:
                    panel_name = f"TC {int(h_val)}/{w_val}"
                else:
                    panel_name = f"TK {int(h_val)}/{w_val}"
                    
                element_panels[panel_name] = element_panels.get(panel_name, 0) + p_cnt * 2 * cnt

    if elem_type == "column":
        w_val = row.get("width_m")
        l_val = row.get("length_m")
        w_cm = (float(w_val) if pd.notna(w_val) and w_val != "" else 0.3) * 100
        l_cm = (float(l_val) if pd.notna(l_val) and l_val != "" else 0.5) * 100
        add_face_panels(w_cm)
        add_face_panels(l_cm)
    elif elem_type == "wall":
        l_val = row.get("length_m")
        l_cm = (float(l_val) if pd.notna(l_val) and l_val != "" else 5.0) * 100
        add_face_panels(l_cm)
    elif elem_type == "l_wall":
        l1_val = row.get("l1_m")
        l2_val = row.get("l2_m")
        t_val = row.get("thickness_m")
        l1_cm = (float(l1_val) if pd.notna(l1_val) and l1_val != "" else 2.0) * 100
        l2_cm = (float(l2_val) if pd.notna(l2_val) and l2_val != "" else 2.0) * 100
        t_cm = (float(t_val) if pd.notna(t_val) and t_val != "" else 0.25) * 100
        
        corner_w = t_cm + 10.0
        add_face_panels(corner_w)
        
        rem_l1 = max(0, l1_cm - corner_w)
        rem_l2 = max(0, l2_cm - corner_w)
        if rem_l1 > 0:
            add_face_panels(rem_l1)
        if rem_l2 > 0:
            add_face_panels(rem_l2)

    elif elem_type == "u_wall":
        l1_val = row.get("l1_m")
        l2_val = row.get("l2_m")
        l3_val = row.get("l3_m")
        t_val = row.get("thickness_m")
        l1_cm = (float(l1_val) if pd.notna(l1_val) and l1_val != "" else 2.0) * 100
        l2_cm = (float(l2_val) if pd.notna(l2_val) and l2_val != "" else 2.0) * 100
        l3_cm = (float(l3_val) if pd.notna(l3_val) and l3_val != "" else 2.0) * 100
        t_cm = (float(t_val) if pd.notna(t_val) and t_val != "" else 0.25) * 100
        
        corner_w = t_cm + 10.0
        add_face_panels(corner_w)
        add_face_panels(corner_w)
        
        rem_l1 = max(0, l1_cm - corner_w)
        rem_l2 = max(0, l2_cm - 2 * corner_w)
        rem_l3 = max(0, l3_cm - corner_w)
        
        if rem_l1 > 0:
            add_face_panels(rem_l1)
        if rem_l2 > 0:
            add_face_panels(rem_l2)
        if rem_l3 > 0:
            add_face_panels(rem_l3)
        
    return element_panels

def get_element_accessories(elem_type, row):
    c_val = row.get("count")
    cnt = int(float(c_val) if pd.notna(c_val) and c_val != "" else 1)
    h_val = row.get("height_m")
    h_m = float(h_val) if pd.notna(h_val) and h_val != "" else 3.0
    h_cm = h_m * 100
    h_levels = calculate_height_breakdown(h_cm)
    
    if elem_type == "column":
        w_val = row.get("width_m")
        l_val = row.get("length_m")
        w_cm = (float(w_val) if pd.notna(w_val) and w_val != "" else 0.3) * 100
        l_cm = (float(l_val) if pd.notna(l_val) and l_val != "" else 0.5) * 100
        acc = calculate_accessories("column", w_cm, l_cm, h_cm, [w_cm, l_cm], h_levels)
    elif elem_type == "wall":
        l_val = row.get("length_m")
        t_val = row.get("thickness_m")
        l_cm = (float(l_val) if pd.notna(l_val) and l_val != "" else 5.0) * 100
        t_cm = (float(t_val) if pd.notna(t_val) and t_val != "" else 0.25) * 100
        acc = calculate_accessories("wall", l_cm, t_cm, h_cm, [l_cm], h_levels)
    elif elem_type == "l_wall":
        l1_val = row.get("l1_m")
        l2_val = row.get("l2_m")
        t_val = row.get("thickness_m")
        l1_cm = (float(l1_val) if pd.notna(l1_val) and l1_val != "" else 2.0) * 100
        l2_cm = (float(l2_val) if pd.notna(l2_val) and l2_val != "" else 2.0) * 100
        t_cm = (float(t_val) if pd.notna(t_val) and t_val != "" else 0.25) * 100
        acc = calculate_accessories("L-образна стена", l1_cm, l2_cm, h_cm, [l1_cm, l2_cm], h_levels)
    elif elem_type == "u_wall":
        l1_val = row.get("l1_m")
        l2_val = row.get("l2_m")
        l3_val = row.get("l3_m")
        t_val = row.get("thickness_m")
        l1_cm = (float(l1_val) if pd.notna(l1_val) and l1_val != "" else 2.0) * 100
        l2_cm = (float(l2_val) if pd.notna(l2_val) and l2_val != "" else 2.0) * 100
        l3_cm = (float(l3_val) if pd.notna(l3_val) and l3_val != "" else 2.0) * 100
        t_cm = (float(t_val) if pd.notna(t_val) and t_val != "" else 0.25) * 100
        acc = calculate_accessories("U-образна стена", l1_cm + l2_cm + l3_cm, t_cm, h_cm, [l1_cm, l2_cm, l3_cm], h_levels)
    else:
        acc = {"bom_summary": {}}

    res = {}
    for code, qty in acc["bom_summary"].items():
        res[code] = qty * cnt
    return res

def format_element_label(elem_type, name):
    name_str = str(name).strip() if name else ""
    if elem_type == "column":
        return name_str if name_str.lower().startswith("колона") else f"Колона {name_str}".strip()
    elif elem_type == "wall":
        return name_str if name_str.lower().startswith("стена") else f"Стена {name_str}".strip()
    elif elem_type == "l_wall":
        return name_str if (name_str.lower().startswith("l-стена") or name_str.lower().startswith("стена")) else f"L-Стена {name_str}".strip()
    elif elem_type == "u_wall":
        return name_str if (name_str.lower().startswith("u-ядро") or name_str.lower().startswith("ядро")) else f"U-Ядро {name_str}".strip()
    return name_str

def process_uploaded_file(uploaded_file):
    uploaded_file.seek(0)
    if uploaded_file.type == "application/pdf":
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return img
    else:
        return Image.open(uploaded_file)

def generate_word_offer(client_name, project_name, offer_date, offer_type, price_per_m2, detailed_rows, total_area, subtotal, vat_amount, grand_total):
    doc = docx.Document()
    
    for section in doc.sections:
        section.top_margin = Inches(0.7)
        section.bottom_margin = Inches(0.7)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    GREEN_COLOR = RGBColor(46, 125, 50)
    BLUE_COLOR = RGBColor(0, 51, 102)
    BLUE_HEX = "003366"

    is_sale = ("закуп" in offer_type.lower() or "продажба" in offer_type.lower())

    p_logo = doc.add_paragraph()
    p_logo.paragraph_format.space_before = Pt(0)
    p_logo.paragraph_format.space_after = Pt(2)
    r_logo = p_logo.add_run("TEKO")
    r_logo.bold = True
    r_logo.font.size = Pt(26)
    r_logo.font.color.rgb = GREEN_COLOR

    p_comp = doc.add_paragraph()
    p_comp.paragraph_format.space_after = Pt(12)
    p_comp.paragraph_format.line_spacing = 1.15

    r_comp = p_comp.add_run("ПЛАСПАНЕЛ ООД | ЕИК 208141542\n")
    r_comp.bold = True
    r_comp.font.size = Pt(10.5)
    r_comp.font.color.rgb = BLUE_COLOR

    r_addr = p_comp.add_run(
        "2700 Благоевград, ул. „Ал. Стамболийски” №9, ет. 1\n"
        "www.tekoform.com | e-mail: bulgaria@tekoform.com | тел: +359 879 044 188"
    )
    r_addr.font.size = Pt(8.5)
    r_addr.font.color.rgb = RGBColor(90, 90, 90)

    p_title = doc.add_paragraph()
    action_text = "закупуване" if is_sale else "наемане"
    run_title = p_title.add_run(f"ОФЕРТА\nЗа {action_text} на пластмасова кофражна система TEKO")
    run_title.bold = True
    run_title.font.size = Pt(14)
    run_title.font.color.rgb = BLUE_COLOR
    p_title.paragraph_format.space_after = Pt(10)

    p_info = doc.add_paragraph()
    p_info.paragraph_format.line_spacing = 1.25
    p_info.paragraph_format.space_after = Pt(12)
    p_info.add_run("До: ").bold = True
    p_info.add_run(f"{client_name}\n")
    p_info.add_run("Относно: ").bold = True
    p_info.add_run(f"Кофриране на стоманобетонови елементи за обект: „{project_name}“\n")
    p_info.add_run("Дата: ").bold = True
    p_info.add_run(f"{offer_date.strftime('%d.%m.%Y')} г.")

    table = doc.add_table(rows=1, cols=6)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    hdr_cells = table.rows[0].cells
    headers = ["Елемент", "Размери", "Брой", "Площ (m²)", "Ед. цена (€/m²)", "Обща сума (€)"]
    
    for i, header_text in enumerate(headers):
        hdr_cells[i].text = header_text
        set_cell_background(hdr_cells[i], BLUE_HEX)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.font.size = Pt(9.5)

    for row_data in detailed_rows:
        row_cells = table.add_row().cells
        row_cells[0].text = str(row_data["Елемент"])
        row_cells[1].text = str(row_data["Размери"])
        row_cells[2].text = f"{row_data['Брой']} бр."
        row_cells[3].text = f"{row_data['Площ (m²)']:.2f} m²"
        row_cells[4].text = f"{price_per_m2:.2f} €"
        row_cells[5].text = f"{row_data['Обща сума (€)']:.2f} €"
        
        for i, c in enumerate(row_cells):
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i > 0 else WD_ALIGN_PARAGRAPH.LEFT
            for r in p.runs:
                r.font.size = Pt(9)

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    action_word = "покупка" if is_sale else "наем"
    p_summary = doc.add_paragraph()
    p_summary.paragraph_format.line_spacing = 1.25
    p_summary.paragraph_format.space_after = Pt(12)
    
    p_summary.add_run(f"Обща кофражна площ: {total_area:.2f} m²\n").bold = True
    p_summary.add_run(f"Обща стойност за {action_word} (без ДДС): {subtotal:.2f} €\n").bold = True
    p_summary.add_run(f"ДДС (20%): {vat_amount:.2f} €\n")
    
    run_total = p_summary.add_run(f"ОБЩО ЗА ПЛАЩАНЕ: {grand_total:.2f} €")
    run_total.bold = True
    run_total.font.size = Pt(11)
    run_total.font.color.rgb = BLUE_COLOR

    notes_p = doc.add_paragraph()
    notes_p.paragraph_format.space_before = Pt(8)
    notes_p.paragraph_format.space_after = Pt(12)
    notes_p.paragraph_format.line_spacing = 1.15
    
    run_th = notes_p.add_run("Условия на офертата:\n")
    run_th.bold = True
    run_th.font.color.rgb = BLUE_COLOR

    terms = [
        "1. Всички цени са посочени в евро (€) без включен ДДС.",
        "2. Начин на плащане: 100% авансово плащане при потвърждение на поръчката.",
        "3. Срок за доставка: До 5 работни дни след постъпване на плащането.",
        "4. Гаранция: 12 месеца за фабрични дефекти при спазване на инструкциите за работа.",
        "5. Забележка: В цената не са включени анкери, тапи, кофражно масло и пластмасови тръби.",
        "6. Място на вземане: Склад на фирмата (Транспортът е за сметка на Купувача/Наемателя)."
    ]
    for term in terms:
        r = notes_p.add_run(f"{term}\n")
        r.font.size = Pt(8.5)

    p_sign = doc.add_paragraph()
    p_sign.paragraph_format.space_before = Pt(8)
    p_sign.add_run("С уважение,\n").bold = True
    run_sign = p_sign.add_run("Екипът на ПЛАСПАНЕЛ ООД\nwww.tekoform.com")
    run_sign.font.color.rgb = BLUE_COLOR
    run_sign.bold = True

    target_stream = io.BytesIO()
    doc.save(target_stream)
    target_stream.seek(0)
    return target_stream

api_key = st.secrets.get("GEMINI_API_KEY", "")

if "blueprint_data" not in st.session_state:
    st.session_state["blueprint_data"] = None
if "used_model" not in st.session_state:
    st.session_state["used_model"] = None

EMPTY_DF = pd.DataFrame(columns=[
    "type", "name", "count", "width_m", "length_m", "thickness_m", "l1_m", "l2_m", "l3_m", "height_m"
])

if "edited_df" not in st.session_state:
    st.session_state["edited_df"] = EMPTY_DF.copy()

with st.sidebar:
    st.header("⚙️ Настройки")
    if not api_key:
        api_key = st.text_input("Въведете Gemini API Key:", type="password")
    else:
        st.success("🔑 API Ключът е зареден!")

st.title("🏗️ ПЛАСПАНЕЛ ООД - Пластмасова Кофражна Система TEKO")

tab1, tab2, tab3, tab4 = st.tabs([
    "📐 Чертеж и Редактиране", 
    "🧱 Кофражни Елементи и Панели TEKO", 
    "📄 PDF Чертежи",
    "📄 Оферта"
])

with tab1:
    st.header("1. Избор на начин за въвеждане на елементи")
    
    input_mode = st.radio(
        "Изберете режим на работа:",
        ["🤖 Автоматично разчитане от чертежи", "⌨️ Ръчно въвеждане (Таблица)"],
        horizontal=True
    )

    if input_mode == "🤖 Автоматично разчитане от чертежи":
        st.subheader("Качване на чертеж и AI разчитане")
        uploaded_file = st.file_uploader("Изберете чертеж (PDF, PNG, JPG):", type=["pdf", "png", "jpg", "jpeg"])

        if uploaded_file:
            col_img, col_actions = st.columns([1, 1])
            with col_img:
                st.subheader("🖼️ Преглед на файла")
                try:
                    processed_img = process_uploaded_file(uploaded_file)
                    st.image(processed_img, use_container_width=True, caption="Качен чертеж")
                except Exception as e:
                    st.error(f"Грешка при зареждането: {e}")
                    processed_img = None

            with col_actions:
                st.subheader("🤖 AI Разчитане")
                
                selected_model = st.selectbox(
                    "Избери AI модел за разчитане:",
                    options=[
                        "gemini-3.1-pro",
                        "gemini-2.5-pro",
                        "gemini-3.8-flash",
                        "gemini-3.6-flash"
                    ],
                    index=0,
                    help="Изберете кой модел на Gemini да анализира чертежа."
                )

                if not api_key:
                    st.warning("⚠️ Моля, въведете Gemini API Key в страничното меню.")
                else:
                    if st.button("🔍 Разчети чертежа с Vision AI", type="primary", use_container_width=True):
                        if processed_img:
                            with st.spinner("Извличане на вертикални кофражни елементи..."):
                                try:
                                    res = analyze_blueprint(processed_img, api_key, model_choice=selected_model)
                                    if isinstance(res, tuple):
                                        blueprint_data, used_model = res
                                    else:
                                        blueprint_data, used_model = res, selected_model

                                    st.session_state["blueprint_data"] = blueprint_data
                                    st.session_state["used_model"] = used_model
                                    elements_list = blueprint_data.get("elements", [])
                                    
                                    st.session_state["edited_df"] = pd.DataFrame(elements_list)
                                    st.success(f"✅ Готово! Разчетено с: **{used_model}**")
                                except Exception as e:
                                    st.error(f"Грешка при анализа: {e}")
    else:
        st.subheader("⌨️ Ръчно въвеждане и управление в таблицата")
        st.markdown(
            "📝 **Инструкция за попълване в таблицата по-долу:**\n"
            "- Изберете **тип елемент** (`wall` - стена, `column` - колона, `l_wall` - L-стена, `u_wall` - П/U-стена).\n"
            "- За **права стена (`wall`)**: попълнете `length_m` (дължина) и `thickness_m` (дебелина).\n"
            "- За **колона (`column`)**: попълнете `width_m` (ширина) и `length_m` (дължина).\n"
            "- За **L-стена (`l_wall`)**: попълнете `l1_m` (рамо 1), `l2_m` (рамо 2) и `thickness_m` (дебелина).\n"
            "- За **П/U-стена (`u_wall`)**: попълнете `l1_m` (рамо 1), `l2_m` (рамо 2), `l3_m` (рамо 3) и `thickness_m` (дебелина).\n"
            "- Непотребните полета за съответния тип могат да се оставят празни — системата автоматично игнорира празни клетки без грешки!"
        )

    st.divider()
    st.subheader("✏️ Таблица с вертикални кофражни елементи")
    
    st.markdown("""
        <style>
        [data-testid="stDataEditor"] th div {
            font-size: 11.5px !important;
            white-space: normal !important;
            overflow: visible !important;
        }
        </style>
    """, unsafe_allow_html=True)

    with st.form("manual_elements_form"):
        edited_grid = st.data_editor(
            st.session_state["edited_df"],
            num_rows="dynamic",
            column_config={
                "type": st.column_config.SelectboxColumn("Тип елемент", options=["column", "wall", "l_wall", "u_wall"], required=True, default="wall", width="auto"),
                "name": st.column_config.TextColumn("Наименование / Маркировка", width="auto"),
                "count": st.column_config.NumberColumn("Брой", min_value=1, step=1, default=1, width="auto"),
                "width_m": st.column_config.NumberColumn("Ширина (м)", format="%.2f", width="auto"),
                "length_m": st.column_config.NumberColumn("Дължина (м)", format="%.2f", width="auto"),
                "thickness_m": st.column_config.NumberColumn("Дебелина (м)", format="%.2f", width="auto"),
                "l1_m": st.column_config.NumberColumn("Рамо 1 (м)", format="%.2f", width="auto"),
                "l2_m": st.column_config.NumberColumn("Рамо 2 (м)", format="%.2f", width="auto"),
                "l3_m": st.column_config.NumberColumn("Рамо 3 (м)", format="%.2f", width="auto"),
                "height_m": st.column_config.NumberColumn("Височина (м)", format="%.2f", width="auto")
            },
            use_container_width=True,
            key="elements_form_editor"
        )
        
        submit_btn = st.form_submit_button("💾 Запази и Изчисли", type="primary", use_container_width=True)
        if submit_btn:
            st.session_state["edited_df"] = edited_grid
            st.success("✅ Данните са запазени и преизчислени успешно! Можете да проверите резултатите в следващите табове.")

with tab2:
    st.header("2. Спецификация на кофражните елементи и панели TEKO")
    df_calc = st.session_state["edited_df"]
    
    if df_calc.empty or len(df_calc) == 0:
        st.info("ℹ️ Въведете елементи в Таб 1 и натиснете 'Запази и Изчисли'.")
    else:
        detailed_rows = []
        all_warnings = []
        total_a = 0.0
        project_panels_summary = {}
        project_accessories_summary = {}

        for _, row in df_calc.iterrows():
            c_val = row.get("count")
            cnt = int(float(c_val) if pd.notna(c_val) and c_val != "" else 1)
            h_val = row.get("height_m")
            h = float(h_val) if pd.notna(h_val) and h_val != "" else 3.0
            elem_type = str(row.get("type", "wall"))
            name = str(row.get("name", "Елемент"))

            row_warns = check_element_dimensions(row)
            all_warnings.extend(row_warns)

            area = 0.0
            dim_str = ""
            elem_label = format_element_label(elem_type, name)

            if elem_type == "column":
                w_val = row.get("width_m")
                l_val = row.get("length_m")
                w = float(w_val) if pd.notna(w_val) and w_val != "" else 0.3
                l = float(l_val) if pd.notna(l_val) and l_val != "" else 0.5
                area = 2 * (w + l) * h * cnt
                dim_str = f"{int(w*100)}x{int(l*100)} cm, H={h:.1f}m"

            elif elem_type == "wall":
                l_val = row.get("length_m")
                t_val = row.get("thickness_m")
                l = float(l_val) if pd.notna(l_val) and l_val != "" else 5.0
                t = float(t_val) if pd.notna(t_val) and t_val != "" else 0.25
                area = 2 * l * h * cnt
                dim_str = f"L={l:.1f}m, B={int(t*100)}cm, H={h:.1f}m"

            elif elem_type == "l_wall":
                l1_val = row.get("l1_m")
                l2_val = row.get("l2_m")
                t_val = row.get("thickness_m")
                l1 = float(l1_val) if pd.notna(l1_val) and l1_val != "" else 2.0
                l2 = float(l2_val) if pd.notna(l2_val) and l2_val != "" else 2.0
                t = float(t_val) if pd.notna(t_val) and t_val != "" else 0.25
                area = 2 * (l1 + l2) * h * cnt
                dim_str = f"L={l1:.1f}+{l2:.1f}m, B={int(t*100)}cm, H={h:.1f}m"

            elif elem_type == "u_wall":
                l1_val = row.get("l1_m")
                l2_val = row.get("l2_m")
                l3_val = row.get("l3_m")
                t_val = row.get("thickness_m")
                l1 = float(l1_val) if pd.notna(l1_val) and l1_val != "" else 2.0
                l2 = float(l2_val) if pd.notna(l2_val) and l2_val != "" else 2.0
                l3 = float(l3_val) if pd.notna(l3_val) and l3_val != "" else 2.0
                t = float(t_val) if pd.notna(t_val) and t_val != "" else 0.25
                area = 2 * (l1 + l2 + l3) * h * cnt
                dim_str = f"L={l1:.1f}+{l2:.1f}+{l3:.1f}m, B={int(t*100)}cm, H={h:.1f}m"

            total_a += area
            
            h_breakdown_str = format_height_breakdown_text(h)

            panels_dict = get_element_teko_panels(elem_type, row)
            for p_name, p_qty in panels_dict.items():
                project_panels_summary[p_name] = project_panels_summary.get(p_name, 0) + p_qty

            panels_str = ", ".join([f"{k} ({v} бр.)" for k, v in panels_dict.items()])

            acc_dict = get_element_accessories(elem_type, row)
            for acc_name, acc_qty in acc_dict.items():
                project_accessories_summary[acc_name] = project_accessories_summary.get(acc_name, 0) + acc_qty

            detailed_rows.append({
                "Елемент": elem_label,
                "Размери": dim_str,
                "Брой": cnt,
                "Площ (m²)": round(area, 2),
                "Разпределение по височина": h_breakdown_str,
                "Панели TEKO (Вид и брой)": panels_str
            })

        df_detailed = pd.DataFrame(detailed_rows)
        if not df_detailed.empty:
            df_detailed.index = range(1, len(df_detailed) + 1)

        panels_sum_data = []
        total_panels_weight = 0.0
        for k, v in sorted(project_panels_summary.items()):
            unit_w = get_item_weight(k)
            tot_w = unit_w * v
            total_panels_weight += tot_w
            panels_sum_data.append({
                "Код на панела / коф. елемент": k,
                "Общ брой (бр.)": v,
                "Ед. тегло (kg)": round(unit_w, 2),
                "Общо тегло (kg)": round(tot_w, 2)
            })
        df_panels_sum = pd.DataFrame(panels_sum_data)
        if not df_panels_sum.empty:
            df_panels_sum.index = range(1, len(df_panels_sum) + 1)

        acc_sum_data = []
        total_acc_weight = 0.0
        for k, v in sorted(project_accessories_summary.items()):
            unit_w = get_item_weight(k)
            tot_w = unit_w * v
            total_acc_weight += tot_w
            acc_sum_data.append({
                "Аксесоар / Окомплектовка": k,
                "Общ брой (бр.)": v,
                "Ед. тегло (kg)": round(unit_w, 2),
                "Общо тегло (kg)": round(tot_w, 2)
            })
        df_acc_sum = pd.DataFrame(acc_sum_data)
        if not df_acc_sum.empty:
            df_acc_sum.index = range(1, len(df_acc_sum) + 1)

        total_formwork_weight = total_panels_weight + total_acc_weight

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric("📊 ОБЩА КОФРАЖНА ПЛОЩ", f"{total_a:.2f} m²")
        with col_m2:
            st.metric("⚖️ ОБЩО ТЕГЛО НА КОФРАЖА", f"{total_formwork_weight:.2f} kg ({total_formwork_weight/1000.0:.2f} t)")

        if all_warnings:
            with st.expander("⚠️ Предупреждения за нестандартни размери в кофражните елементи", expanded=True):
                for w_msg in all_warnings:
                    st.markdown(w_msg)

        st.subheader("📋 Спецификация на кофражните елементи и съответните панели")
        st.dataframe(df_detailed, use_container_width=True)

        st.divider()
        col_p1, col_p2 = st.columns(2)
        
        with col_p1:
            st.subheader(f"📦 Панели TEKO (Общо: {total_panels_weight:.2f} kg)")
            st.dataframe(df_panels_sum, use_container_width=True)

        with col_p2:
            st.subheader(f"金具 Аксесоари и Ъгли (Общо: {total_acc_weight:.2f} kg)")
            st.dataframe(df_acc_sum, use_container_width=True)

with tab3:
    st.header("3. Генериране на PDF чертежи и спецификации")
    if df_calc.empty or len(df_calc) == 0:
        st.info("ℹ️ Въведете елементи в Таб 1, за да генерирате чертежи.")
    else:
        proj_name_input = st.text_input("Наименование на обекта:", value="Обект ТЕКО")
        client_name_input = st.text_input("Име на клиент / инвеститор:", value="Няма посочен клиент")

        if st.button("📄 Генерирай PDF Чертежи на обект", type="primary"):
            with st.spinner("Генериране на векторни чертежи и PDF документ..."):
                pdf_elements = []
                for _, row in df_calc.iterrows():
                    elem_type = str(row.get("type", "wall"))
                    name = str(row.get("name", "Елемент"))
                    h_val = row.get("height_m")
                    h = float(h_val) if pd.notna(h_val) and h_val != "" else 3.0
                    h_cm = h * 100
                    t_val = row.get("thickness_m")
                    thick = (float(t_val) if pd.notna(t_val) and t_val != "" else 0.25) * 100

                    if elem_type == "column":
                        w_val = row.get("width_m")
                        l_val = row.get("length_m")
                        w = (float(w_val) if pd.notna(w_val) and w_val != "" else 0.3) * 100
                        l = (float(l_val) if pd.notna(l_val) and l_val != "" else 0.5) * 100
                        display_type = "Колона"
                        l_a, l_b = w, l
                    elif elem_type == "wall":
                        l_val = row.get("length_m")
                        l = (float(l_val) if pd.notna(l_val) and l_val != "" else 5.0) * 100
                        display_type = "Права Стена / Шайба"
                        l_a, l_b = l, thick
                    elif elem_type == "l_wall":
                        l1_val = row.get("l1_m")
                        l2_val = row.get("l2_m")
                        l1 = (float(l1_val) if pd.notna(l1_val) and l1_val != "" else 2.0) * 100
                        l2 = (float(l2_val) if pd.notna(l2_val) and l2_val != "" else 2.0) * 100
                        display_type = "L-образна Стена / Шайба"
                        l_a, l_b = l1, l2
                    elif elem_type == "u_wall":
                        l1_val = row.get("l1_m")
                        l2_val = row.get("l2_m")
                        l3_val = row.get("l3_m")
                        l1 = (float(l1_val) if pd.notna(l1_val) and l1_val != "" else 2.0) * 100
                        l2 = (float(l2_val) if pd.notna(l2_val) and l2_val != "" else 2.0) * 100
                        l3 = (float(l3_val) if pd.notna(l3_val) and l3_val != "" else 2.0) * 100
                        display_type = "П-образна Стена / Шайба"
                        l_a, l_b = l2, l1
                    else:
                        display_type = "Стена"
                        l_a, l_b = 100, thick

                    pdf_elements.append({
                        "name": format_element_label(elem_type, name),
                        "wall_type": display_type,
                        "length_a_cm": l_a,
                        "length_b_cm": l_b,
                        "height_cm": h_cm,
                        "thickness_cm": thick
                    })

                project_full_bom = {}
                for p_code, p_qty in project_panels_summary.items():
                    project_full_bom[p_code] = project_full_bom.get(p_code, 0) + p_qty
                for acc_code, acc_qty in project_accessories_summary.items():
                    project_full_bom[acc_code] = project_full_bom.get(acc_code, 0) + acc_qty

                proj_info = {
                    "project": proj_name_input,
                    "client": client_name_input
                }

                pdf_bytes = generate_pdf_drawings(pdf_elements, project_full_bom, proj_info)
                st.success("✅ PDF чертежите бяха генерирани успешно!")
                st.download_button(
                    label="📥 Изтегли пълен PDF с чертежи и спецификации",
                    data=pdf_bytes,
                    file_name="Teko_Drawings_And_Specification.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

with tab4:
    st.header("4. Търговска оферта")
    if df_calc.empty or len(df_calc) == 0:
        st.info("ℹ️ Въведете елементи в Таб 1, за да генерирате оферта.")
    else:
        col_o1, col_o2 = st.columns(2)
        with col_o1:
            offer_client = st.text_input("Клиент / Инвеститор:", value="Строителна Компания ООД")
            offer_project = st.text_input("Име на обект:", value="Жилищна сграда")
            offer_date_val = st.date_input("Дата на офертата:")
        with col_o2:
            offer_type_sel = st.selectbox("Тип на офертата:", ["Наем на кофраж (€/m² за месец)", "Покупка на нов кофраж (€/m²)"])
            default_price = 18.0 if "наем" in offer_type_sel.lower() else 125.0
            price_m2 = st.number_input("Цена на m² (€):", min_value=0.0, value=default_price, step=0.5)

        if st.button("📄 Създай Word оферта", type="primary"):
            subtotal_val = total_a * price_m2
            vat_val = subtotal_val * 0.20
            grand_total_val = subtotal_val + vat_val

            offer_table_rows = []
            for _, row in df_calc.iterrows():
                c_val = row.get("count")
                cnt = int(float(c_val) if pd.notna(c_val) and c_val != "" else 1)
                h_val = row.get("height_m")
                h = float(h_val) if pd.notna(h_val) and h_val != "" else 3.0
                elem_type = str(row.get("type", "wall"))
                name = str(row.get("name", "Елемент"))

                area = 0.0
                dim_str = ""
                if elem_type == "column":
                    w = float(row.get("width_m") or 0.3)
                    l = float(row.get("length_m") or 0.5)
                    area = 2 * (w + l) * h * cnt
                    dim_str = f"{int(w*100)}x{int(l*100)} cm, H={h:.1f}m"
                elif elem_type == "wall":
                    l = float(row.get("length_m") or 5.0)
                    t = float(row.get("thickness_m") or 0.25)
                    area = 2 * l * h * cnt
                    dim_str = f"L={l:.1f}m, B={int(t*100)}cm, H={h:.1f}m"
                elif elem_type == "l_wall":
                    l1 = float(row.get("l1_m") or 2.0)
                    l2 = float(row.get("l2_m") or 2.0)
                    area = 2 * (l1 + l2) * h * cnt
                    dim_str = f"L={l1:.1f}+{l2:.1f}m, H={h:.1f}m"
                elif elem_type == "u_wall":
                    l1 = float(row.get("l1_m") or 2.0)
                    l2 = float(row.get("l2_m") or 2.0)
                    l3 = float(row.get("l3_m") or 2.0)
                    area = 2 * (l1 + l2 + l3) * h * cnt
                    dim_str = f"L={l1:.1f}+{l2:.1f}+{l3:.1f}m, H={h:.1f}m"

                offer_table_rows.append({
                    "Елемент": format_element_label(elem_type, name),
                    "Размери": dim_str,
                    "Брой": cnt,
                    "Площ (m²)": area,
                    "Обща сума (€)": area * price_m2
                })

            word_stream = generate_word_offer(
                offer_client, offer_project, offer_date_val, offer_type_sel,
                price_m2, offer_table_rows, total_a, subtotal_val, vat_val, grand_total_val
            )

            st.success("✅ Търговската оферта беше генерирана успешно в Word формат!")
            st.download_button(
                label="📥 Изтегли оферта (Word .docx)",
                data=word_stream,
                file_name="Teko_Commercial_Offer.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
