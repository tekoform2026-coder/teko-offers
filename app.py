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
from drawing_generator import generate_pdf_drawings, generate_top_view_buf, generate_front_view_buf
from excel_export import generate_excel, generate_kss_excel
from accessories_calculator import calculate_accessories
from teko_calculator import solve_height_cm, layout_element, count_panels
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

# === СТЪПКА 3: Описание на редовете по височина ===
def format_height_breakdown_text(height_cm):
    """
    Форматира височината на елемента в ясен текст за използваните нива от панели.
    """
    h_cm = round(float(height_cm or 300))
    h_levels = solve_height_cm(h_cm)
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
    h_cm = round(_row_float(row, "height_cm", 300))
    elem_type = str(row.get("type", "wall"))
    name = format_element_label(elem_type, str(row.get("name", "Елемент")))

    if h_cm % 10 != 0:
        warnings.append(f"• **{name}**: Височина {h_cm} cm не е кратна на 10 cm (закръгля се към най-близкия модул).")

    if elem_type == "column":
        w_cm = round(_row_float(row, "width_cm", 30))
        l_cm = round(_row_float(row, "length_cm", 50))
        if w_cm % 5 != 0 or l_cm % 5 != 0:
            warnings.append(f"• **{name}**: Размерите ({w_cm}x{l_cm} cm) не са кратни на 5 cm. Запълва се с компенсатор TC 5.")
    elif elem_type == "wall":
        l_cm = round(_row_float(row, "length_cm", 500))
        if l_cm % 5 != 0:
            warnings.append(f"• **{name}**: Дължината {l_cm} cm не е кратна на 5 cm. Запълва се с компенсатор TC 5.")
    elif elem_type == "l_wall":
        l1_cm = round(_row_float(row, "l1_cm", 200))
        l2_cm = round(_row_float(row, "l2_cm", 200))
        if l1_cm % 5 != 0 or l2_cm % 5 != 0:
            warnings.append(f"• **{name}**: Раменете ({l1_cm} cm / {l2_cm} cm) съдържат стойности некратни на 5 cm.")
    elif elem_type == "u_wall":
        l1_cm = round(_row_float(row, "l1_cm", 200))
        l2_cm = round(_row_float(row, "l2_cm", 200))
        l3_cm = round(_row_float(row, "l3_cm", 200))
        if l1_cm % 5 != 0 or l2_cm % 5 != 0 or l3_cm % 5 != 0:
            warnings.append(f"• **{name}**: Раменете ({l1_cm}/{l2_cm}/{l3_cm} cm) съдържат стойности некратни на 5 cm.")
    elif elem_type == "t_wall":
        l1_cm = round(_row_float(row, "l1_cm", 200))
        l2_cm = round(_row_float(row, "l2_cm", 200))
        t_cm = round(_row_float(row, "thickness_cm", 25))
        if l1_cm % 5 != 0 or l2_cm % 5 != 0:
            warnings.append(f"• **{name}**: Страните A / B ({l1_cm} cm / {l2_cm} cm) съдържат стойности некратни на 5 cm.")
        # реброто е в средата: от всяка страна на полката трябва да остане място за IN (10 cm) и панел
        if (l1_cm - t_cm) / 2 <= 10 or l2_cm <= 10:
            warnings.append(f"• **{name}**: Страна A ({l1_cm} cm) или B ({l2_cm} cm) е твърде къса за T-стена "
                            f"с дебелина {t_cm} cm - проверете Рамо 1 (страна A) и Рамо 2 (страна B).")

    # Размерите са в см - стойност под 10 най-вероятно е въведена в метри (напр. 2.5 вместо 250)
    small = [f"{col} = {row.get(col):g}" for col in LENGTH_COLUMNS
             if pd.notna(pd.to_numeric(row.get(col), errors="coerce")) and 0 < float(row.get(col)) < 10]
    if small:
        warnings.append(f"• **{name}**: {', '.join(small)} - размерите са в **сантиметри**; "
                        f"въведени ли са в метри? (напр. 2.5 м = 250 см)")

    return warnings

def _row_float(row, key, default):
    val = row.get(key)
    return float(val) if pd.notna(val) and val != "" else default

DEFAULT_HEIGHT_CM = 270

# Размерите в таблицата са в сантиметри
LENGTH_COLUMNS = ["width_cm", "length_cm", "thickness_cm", "l1_cm", "l2_cm", "l3_cm", "height_cm"]

def columns_to_cm(df):
    """Стари колони в метри (width_m, height_m ...) -> същите в сантиметри (width_cm, height_cm ...)."""
    df = df.copy()
    for col_cm in LENGTH_COLUMNS:
        col_m = col_cm[:-3] + "_m"
        if col_m in df.columns:
            meters = pd.to_numeric(df[col_m], errors="coerce") * 100
            df[col_cm] = df[col_cm].fillna(meters) if col_cm in df.columns else meters
            df = df.drop(columns=[col_m])
    return df

def fill_default_height(df, height_cm):
    """Празната „Височина“ се смята със стандартната височина на етажа; въведената остава."""
    df = df.copy()
    if "height_cm" not in df.columns:
        df["height_cm"] = None
    df["height_cm"] = pd.to_numeric(df["height_cm"], errors="coerce").fillna(height_cm)
    return df

def _row_bool(row, key):
    val = row.get(key)
    return bool(val) if pd.notna(val) and val != "" else False

def row_to_layout(elem_type, row):
    """Превежда ред от таблицата към разположение на панелите (teko_calculator.layout_element)."""
    h_cm = _row_float(row, "height_cm", 300)
    t_cm = _row_float(row, "thickness_cm", 25)
    closed = {"closed_end_1": _row_bool(row, "closed_end_1"),
              "closed_end_2": _row_bool(row, "closed_end_2")}

    if elem_type == "column":
        return layout_element("column", h_cm,
                              width_cm=_row_float(row, "width_cm", 30),
                              length_cm=_row_float(row, "length_cm", 50))
    elif elem_type == "wall":
        return layout_element("wall", h_cm, length_cm=_row_float(row, "length_cm", 500),
                              thickness_cm=t_cm, **closed)
    elif elem_type == "l_wall":
        return layout_element("l_wall", h_cm,
                              l1_cm=_row_float(row, "l1_cm", 200),
                              l2_cm=_row_float(row, "l2_cm", 200),
                              thickness_cm=t_cm, **closed)
    elif elem_type == "u_wall":
        return layout_element("u_wall", h_cm,
                              l1_cm=_row_float(row, "l1_cm", 200),
                              l2_cm=_row_float(row, "l2_cm", 200),
                              l3_cm=_row_float(row, "l3_cm", 200),
                              thickness_cm=t_cm, **closed)
    elif elem_type == "t_wall":
        return layout_element("t_wall", h_cm,
                              l1_cm=_row_float(row, "l1_cm", 200),
                              l2_cm=_row_float(row, "l2_cm", 200),
                              thickness_cm=t_cm, closed_end_3=_row_bool(row, "closed_end_3"), **closed)
    return None

def get_element_teko_panels(elem_type, row):
    cnt = int(_row_float(row, "count", 1))
    layout = row_to_layout(elem_type, row)
    if layout is None:
        return {}
    return count_panels(layout, cnt)

def get_element_accessories(elem_type, row):
    cnt = int(_row_float(row, "count", 1))
    layout = row_to_layout(elem_type, row)
    if layout is None:
        return {}

    h_cm = layout["height_cm"]
    h_levels = layout["height_levels"]
    widths_a = layout["faces"][0]["rows"][0]

    if elem_type == "column":
        dims = layout["dims"]
        acc = calculate_accessories("column", dims["a"], dims["b"], h_cm, widths_a, h_levels, layout=layout)
    elif elem_type == "wall":
        dims = layout["dims"]
        acc = calculate_accessories("wall", dims["length"], dims["t"], h_cm, widths_a, h_levels, layout=layout)
    elif elem_type == "l_wall":
        dims = layout["dims"]
        acc = calculate_accessories("L-образна стена", dims["l1"], dims["l2"], h_cm, widths_a, h_levels, layout=layout)
    elif elem_type == "t_wall":
        dims = layout["dims"]
        stem = next(f for f in layout["faces"] if f["name"] == "B")["length_cm"]
        acc = calculate_accessories("T-образна стена", dims["l1"], stem, h_cm, widths_a, h_levels, layout=layout)
    else:
        dims = layout["dims"]
        acc = calculate_accessories("U-образна стена", dims["l1"] + dims["l2"] + dims["l3"], dims["t"], h_cm, widths_a, h_levels, layout=layout)

    res = {}
    for code, qty in acc["bom_summary"].items():
        res[code] = qty * cnt
    return res

def element_dims_and_area(elem_type, row):
    """Надпис с размерите (в см) и кофражната площ (m²) на реда, умножена по броя елементи."""
    cnt = int(_row_float(row, "count", 1))
    h = _row_float(row, "height_cm", 300)
    t = _row_float(row, "thickness_cm", 25)
    if elem_type == "column":
        w, l = _row_float(row, "width_cm", 30), _row_float(row, "length_cm", 50)
        perimeter = 2 * (w + l)
        dim_str = f"{w:g}x{l:g} см, H={h:g} см"
    elif elem_type == "wall":
        l = _row_float(row, "length_cm", 500)
        perimeter = 2 * l
        dim_str = f"L={l:g} см, B={t:g} см, H={h:g} см"
    elif elem_type == "l_wall":
        l1, l2 = _row_float(row, "l1_cm", 200), _row_float(row, "l2_cm", 200)
        perimeter = 2 * (l1 + l2)
        dim_str = f"L={l1:g}+{l2:g} см, B={t:g} см, H={h:g} см"
    elif elem_type == "u_wall":
        l1, l2, l3 = _row_float(row, "l1_cm", 200), _row_float(row, "l2_cm", 200), _row_float(row, "l3_cm", 200)
        perimeter = 2 * (l1 + l2 + l3)
        dim_str = f"L={l1:g}+{l2:g}+{l3:g} см, B={t:g} см, H={h:g} см"
    elif elem_type == "t_wall":
        l1, l2 = _row_float(row, "l1_cm", 200), _row_float(row, "l2_cm", 200)
        perimeter = 2 * (l1 + l2)
        dim_str = f"T: A={l1:g} см, B={l2:g} см, дебелина {t:g} см, H={h:g} см"
    else:
        return "", 0.0
    return dim_str, perimeter * h / 10000.0 * cnt

DISPLAY_TYPES = {
    "column": "Колона",
    "wall": "Права Стена / Шайба",
    "l_wall": "L-образна Стена / Шайба",
    "u_wall": "П-образна Стена / Шайба",
    "t_wall": "T-образна Стена / Шайба",
}

def build_drawing_elements(df):
    """Елементите за чертежите (PDF и Excel): наименование, тип, брой, разположение и сметка."""
    elements = []
    for _, row in df.iterrows():
        elem_type = str(row.get("type", "wall"))
        name = str(row.get("name", "Елемент"))
        layout = row_to_layout(elem_type, row)
        if layout is None:
            continue
        elem_bom = dict(get_element_teko_panels(elem_type, row))
        for acc_code, acc_qty in get_element_accessories(elem_type, row).items():
            elem_bom[acc_code] = elem_bom.get(acc_code, 0) + acc_qty
        elements.append({
            "name": format_element_label(elem_type, name),
            "wall_type": DISPLAY_TYPES[elem_type],
            "count": int(_row_float(row, "count", 1)),
            "layout": layout,
            "bom": elem_bom
        })
    return elements

# === Преглед на елементите под таблицата ===
@st.cache_data(show_spinner=False, max_entries=300)
def preview_top_png(row_items):
    """Изгледът отгоре (PNG) на реда; кешира се по стойностите на реда."""
    row = dict(row_items)
    elem_type = str(row.get("type", "wall"))
    layout = row_to_layout(elem_type, row)
    return generate_top_view_buf(layout, format_element_label(elem_type, row.get("name", ""))).getvalue()

@st.cache_data(show_spinner=False, max_entries=300)
def preview_front_png(row_items):
    """Изгледът отпред (PNG) на реда; кешира се по стойностите на реда."""
    row = dict(row_items)
    elem_type = str(row.get("type", "wall"))
    layout = row_to_layout(elem_type, row)
    return generate_front_view_buf(layout, format_element_label(elem_type, row.get("name", ""))).getvalue()

def preview_counts(elem_type, row):
    """Бройките за реда по групи: панели, ъгли, ригели, вертикализатори, ръкохватки, шпилки."""
    acc = get_element_accessories(elem_type, row)
    def group(word):
        return sum(qty for code, qty in acc.items() if word in code)
    return [("панела", sum(get_element_teko_panels(elem_type, row).values())),
            ("ъгли", group("ъгъл")),
            ("ригели", group("Ригел")),
            ("верт.", group("Вертикализатор")),
            ("ръкохватки", group("Ръкохватка")),
            ("шпилки", group("Шпилка"))]

def render_element_preview(idx, row):
    """Сгъваемо поле за един ред: размери, бройки, изглед отгоре и (с отметка) изглед отпред."""
    elem_type = str(row.get("type", "wall"))
    if elem_type not in DISPLAY_TYPES:
        return
    label = format_element_label(elem_type, row.get("name", ""))
    dim_str, _ = element_dims_and_area(elem_type, row)
    cnt = int(_row_float(row, "count", 1))
    closed = sum(_row_bool(row, k) for k in ("closed_end_1", "closed_end_2", "closed_end_3"))
    title = f"{label} · {DISPLAY_TYPES[elem_type]} — {dim_str}, затворени краища: {closed}, {cnt} бр."
    with st.expander(title):
        for w in check_element_dimensions(row):
            st.warning(w)
        row_items = tuple(row.items())
        try:
            counts = preview_counts(elem_type, row)
            top_png = preview_top_png(row_items)
        except Exception as e:
            st.error(f"Елементът не може да се начертае - проверете размерите ({e}).")
            return
        st.markdown(f"Количества ({cnt} бр.): " + " ".join(f":gray-badge[{qty} {word}]" for word, qty in counts))
        st.image(top_png, caption="Изглед отгоре", width=700)
        if st.checkbox("Покажи изгледа отпред", key=f"preview_front_{idx}"):
            st.image(preview_front_png(row_items), caption="Изглед отпред", width=900)

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
    elif elem_type == "t_wall":
        return name_str if (name_str.lower().startswith("t-стена") or name_str.lower().startswith("стена")) else f"T-Стена {name_str}".strip()
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

try:
    api_key = st.secrets.get("GEMINI_API_KEY", "")
except FileNotFoundError:
    # Няма secrets.toml - ключът се въвежда в страничното меню
    api_key = ""

if "blueprint_data" not in st.session_state:
    st.session_state["blueprint_data"] = None
if "used_model" not in st.session_state:
    st.session_state["used_model"] = None

EMPTY_DF = pd.DataFrame(columns=[
    "type", "name", "count", "width_cm", "length_cm", "thickness_cm", "l1_cm", "l2_cm", "l3_cm", "height_cm", "closed_end_1", "closed_end_2",
    "closed_end_3"
])

if "edited_df" not in st.session_state:
    st.session_state["edited_df"] = EMPTY_DF.copy()
else:
    st.session_state["edited_df"] = columns_to_cm(st.session_state["edited_df"])

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
                                    
                                    df_ai = columns_to_cm(pd.DataFrame(elements_list))
                                    for col in ("closed_end_1", "closed_end_2", "closed_end_3"):
                                        if col not in df_ai.columns:
                                            df_ai[col] = False
                                    st.session_state["edited_df"] = df_ai
                                    st.success(f"✅ Готово! Разчетено с: **{used_model}**")
                                except Exception as e:
                                    st.error(f"Грешка при анализа: {e}")
    else:
        st.subheader("⌨️ Ръчно въвеждане и управление в таблицата")
        st.markdown(
            "📝 **Инструкция за попълване в таблицата по-долу:**\n"
            "- Изберете **тип елемент** (`wall` - стена, `column` - колона, `l_wall` - L-стена, `u_wall` - П/U-стена).\n"
            "- Всички размери (ширина, дължина, дебелина, рамена, височина) са в **сантиметри**.\n"
            "- За **права стена (`wall`)**: попълнете `length_cm` (дължина) и `thickness_cm` (дебелина).\n"
            "- За **колона (`column`)**: попълнете `width_cm` (ширина) и `length_cm` (дължина).\n"
            "- За **L-стена (`l_wall`)**: попълнете `l1_cm` (рамо 1), `l2_cm` (рамо 2) и `thickness_cm` (дебелина).\n"
            "- За **П/U-стена (`u_wall`)**: попълнете `l1_cm` (рамо 1), `l2_cm` (рамо 2), `l3_cm` (рамо 3) и `thickness_cm` (дебелина).\n"
            "- За **T-стена (`t_wall`)**: **Рамо 1 = страна A** (цялата полка), **Рамо 2 = страна B / B1** (реброто, от полката до края му) и `thickness_cm` (дебелина). Рамо 3 не се попълва - реброто е в средата на полката. Край 1 е десният край на полката, край 2 - левият, **Затворен край 3** - краят на реброто (само за T-стена).\n"
            "- **Затворен край 1 / Затворен край 2** (отметки) за стени, L- и П/U-стени: челните краища, затворени с панел колкото дебелината. Край 1 е краят на рамо 1 (при права стена - десният), край 2 - краят на последното рамо (при права стена - левият).\n"
            "- Непотребните полета за съответния тип могат да се оставят празни — системата автоматично игнорира празни клетки без грешки!"
        )

    st.divider()
    st.subheader("📏 Стандартна височина на етажа")
    std_choice = st.radio(
        "Стандартна височина за всички елементи:",
        ["270 см", "300 см", "Друга"],
        index=0,
        horizontal=True,
        key="std_height_choice_cm"
    )
    if std_choice == "Друга":
        std_height = st.number_input("Височина (см):", min_value=60, max_value=1200, value=DEFAULT_HEIGHT_CM,
                                     step=10, key="std_height_other_cm")
    else:
        std_height = int(std_choice.split()[0])
    st.session_state["std_height_cm"] = std_height
    st.caption(f"Елементите с празна „Височина (см)“ в таблицата се смятат с {std_height} см. "
               "Височината, въведена в таблицата, остава с предимство.")
    if st.button(f"↕️ Приложи {std_height} см към всички редове", key="apply_std_height",
                 help="Записва стандартната височина във всички редове на таблицата, включително разчетените "
                      "от чертежа. Незапазените промени в таблицата се губят - първо натиснете „Запази и Изчисли“."):
        df_all = st.session_state["edited_df"].copy()
        if df_all.empty:
            st.info("ℹ️ Таблицата е празна - няма редове за промяна.")
        else:
            df_all["height_cm"] = std_height
            st.session_state["edited_df"] = df_all
            st.session_state.pop("elements_form_editor", None)  # таблицата се показва наново с новите височини
            st.success(f"✅ Височина {std_height} см е записана в {len(df_all)} реда.")

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
                "type": st.column_config.SelectboxColumn("Тип елемент", options=["column", "wall", "l_wall", "u_wall", "t_wall"], required=True, default="wall", width="auto"),
                "name": st.column_config.TextColumn("Наименование / Маркировка", width="auto"),
                "count": st.column_config.NumberColumn("Брой", min_value=1, step=1, default=1, width="auto"),
                "width_cm": st.column_config.NumberColumn("Ширина (см)", format="%g", width="auto"),
                "length_cm": st.column_config.NumberColumn("Дължина (см)", format="%g", width="auto"),
                "thickness_cm": st.column_config.NumberColumn("Дебелина (см)", format="%g", width="auto"),
                "l1_cm": st.column_config.NumberColumn("Рамо 1 (см)", format="%g", width="auto"),
                "l2_cm": st.column_config.NumberColumn("Рамо 2 (см)", format="%g", width="auto"),
                "l3_cm": st.column_config.NumberColumn("Рамо 3 (см)", format="%g", width="auto"),
                "height_cm": st.column_config.NumberColumn("Височина (см)", format="%g", width="auto"),
                "closed_end_1": st.column_config.CheckboxColumn("Затворен край 1", default=False, width="auto"),
                "closed_end_2": st.column_config.CheckboxColumn("Затворен край 2", default=False, width="auto"),
                "closed_end_3": st.column_config.CheckboxColumn("Затворен край 3 (само T-стена)", default=False, width="auto")
            },
            use_container_width=True,
            key="elements_form_editor"
        )
        
        submit_btn = st.form_submit_button("💾 Запази и Изчисли", type="primary", use_container_width=True)
        if submit_btn:
            st.session_state["edited_df"] = edited_grid
            st.session_state.pop("excel_bytes", None)  # старият Excel вече не отговаря на таблицата
            st.success("✅ Данните са запазени и преизчислени успешно! Можете да проверите резултатите в следващите табове.")

    st.subheader("👁 Преглед на елементите")
    st.caption("Прегледът показва записаните данни - обновява се след „Запази и Изчисли“. "
               "Полетата се отварят без презареждане; отметката „Покажи изгледа отпред“ презарежда страницата, "
               "затова първо запишете промените в таблицата.")
    df_preview = fill_default_height(st.session_state["edited_df"],
                                     st.session_state.get("std_height_cm", DEFAULT_HEIGHT_CM))
    if df_preview.empty:
        st.info("ℹ️ Няма записани елементи за преглед.")
    for idx, row in df_preview.iterrows():
        render_element_preview(idx, row)

with tab2:
    st.header("2. Спецификация на кофражните елементи и панели TEKO")
    df_calc = fill_default_height(st.session_state["edited_df"],
                                  st.session_state.get("std_height_cm", DEFAULT_HEIGHT_CM))
    
    if df_calc.empty or len(df_calc) == 0:
        st.info("ℹ️ Въведете елементи в Таб 1 и натиснете 'Запази и Изчисли'.")
    else:
        detailed_rows = []
        all_warnings = []
        total_a = 0.0
        project_panels_summary = {}
        project_accessories_summary = {}

        for _, row in df_calc.iterrows():
            cnt = int(_row_float(row, "count", 1))
            h = _row_float(row, "height_cm", 300)
            elem_type = str(row.get("type", "wall"))
            name = str(row.get("name", "Елемент"))

            row_warns = check_element_dimensions(row)
            all_warnings.extend(row_warns)

            elem_label = format_element_label(elem_type, name)
            dim_str, area = element_dims_and_area(elem_type, row)

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

        st.divider()
        st.subheader("📊 КСС и чертежи в Excel")
        st.caption("Лист „Кол. сметка“ - артикулите в реда на офертата; лист за всеки елемент - изглед отгоре "
                   "и изглед отпред от клетки (1 клетка = 5 см) за редакция; лист с всички панели за копиране.")
        if st.button("📊 Създай Excel (КСС и чертежи)", key="make_excel"):
            with st.spinner("Генериране на Excel..."):
                st.session_state["excel_bytes"] = generate_excel(build_drawing_elements(df_calc)).getvalue()
        if st.session_state.get("excel_bytes"):
            st.download_button(
                label="📥 Изтегли КСС и чертежи (Excel .xlsx)",
                data=st.session_state["excel_bytes"],
                file_name="Teko_KSS_i_Chertezhi.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

with tab3:
    st.header("3. Генериране на PDF чертежи и спецификации")
    if df_calc.empty or len(df_calc) == 0:
        st.info("ℹ️ Въведете елементи в Таб 1, за да генерирате чертежи.")
    else:
        proj_name_input = st.text_input("Наименование на обекта:", value="Обект ТЕКО")
        client_name_input = st.text_input("Име на клиент / инвеститор:", value="Няма посочен клиент")

        if st.button("📄 Генерирай PDF Чертежи на обект", type="primary"):
            with st.spinner("Генериране на векторни чертежи и PDF документ..."):
                pdf_elements = build_drawing_elements(df_calc)

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
                cnt = int(_row_float(row, "count", 1))
                elem_type = str(row.get("type", "wall"))
                name = str(row.get("name", "Елемент"))
                dim_str, area = element_dims_and_area(elem_type, row)

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

        st.divider()
        st.subheader("📊 КСС в Excel")
        st.caption("Количествена сметка за целия обект - артикулите в реда на офертата.")
        if st.button("📊 Създай КСС (Excel)", key="make_kss_excel"):
            kss_bom = dict(project_panels_summary)
            for acc_code, acc_qty in project_accessories_summary.items():
                kss_bom[acc_code] = kss_bom.get(acc_code, 0) + acc_qty
            kss_stream = generate_kss_excel(kss_bom, offer_project, offer_client, offer_date_val)
            st.success("✅ КСС е генерирана в Excel формат!")
            st.download_button(
                label="📥 Изтегли КСС (Excel .xlsx)",
                data=kss_stream,
                file_name="Teko_KSS.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
