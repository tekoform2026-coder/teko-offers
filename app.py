import streamlit as st
import fitz  # PyMuPDF
import cv2
import numpy as np
from PIL import Image
import json
import pandas as pd
import io
from datetime import datetime
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# Внос на изчислителните и AI модули
import teko_calculator
from gemini_agent2 import analyze_blueprint

st.set_page_config(page_title="TEKO Offers & Panels", layout="wide")

st.title("🏗️ TEKO Offers & Panel Generator")

api_key = st.secrets.get("GEMINI_API_KEY", "")

# Функция за обработка и подобряване на снимка/PDF
def process_uploaded_file(uploaded_file):
    file_bytes = uploaded_file.read()
    if uploaded_file.name.lower().endswith('.pdf'):
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        page = doc[0]
        pix = page.get_pixmap(dpi=150)
        img_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    else:
        img_pil = Image.open(io.BytesIO(file_bytes))

    img_np = np.array(img_pil)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY) if len(img_np.shape) == 3 else img_np
    enhanced = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    return Image.fromarray(enhanced)

# Помощна функция за фон на клетка в Word
def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill_hex)
    tcPr.append(shd)

# Генерация на Word документ за оферта
def create_teko_word_docx(client_name, project_name, offer_type, table_data, total_formwork, unit_price):
    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(0.6)
        section.bottom_margin = Inches(0.6)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    p_header = doc.add_paragraph()
    p_header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    
    r_logo = p_header.add_run("TEKO\n")
    r_logo.bold = True
    r_logo.font.size = Pt(22)
    r_logo.font.color.rgb = RGBColor(0, 168, 89)
    
    r_comp = p_header.add_run("ПЛАСПАНЕЛ ООД | ЕИК 208141542\n")
    r_comp.bold = True
    r_comp.font.size = Pt(10.5)
    
    r_sub = p_header.add_run("2700 Благоевград, ул. „Ал. Стамболийски” №9, ет. 1\nwww.tekoform.com | e-mail: bulgaria@tekoform.com | тел: +359 879 044 188\n")
    r_sub.font.size = Pt(8.5)
    r_sub.font.color.rgb = RGBColor(100, 100, 100)

    doc.add_paragraph("")

    p_title = doc.add_paragraph()
    r_title = p_title.add_run("ОФЕРТА\n")
    r_title.bold = True
    r_title.font.size = Pt(16)
    r_title.font.color.rgb = RGBColor(0, 81, 158)
    
    action_word = "закупуване" if offer_type == "Закупуване" else "наемане"
    r_subtitle = p_title.add_run(f"За {action_word} на пластмасова кофражна система TEKO\n")
    r_subtitle.bold = True
    r_subtitle.font.size = Pt(12)
    r_subtitle.font.color.rgb = RGBColor(0, 81, 158)

    p_meta = doc.add_paragraph()
    p_meta.add_run("До: ").bold = True
    p_meta.add_run(f"{client_name}\n")
    p_meta.add_run("Относно: ").bold = True
    p_meta.add_run(f"Кофриране на стоманобетонови елементи за обект: „{project_name}“\n")
    p_meta.add_run("Дата: ").bold = True
    p_meta.add_run(f"{datetime.now().strftime('%d.%m.%Y г.')}\n")

    table = doc.add_table(rows=1, cols=6)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'
    
    hdr_cells = table.rows[0].cells
    headers = ["Елемент", "Размери", "Брой", "Площ (m²)", "Ед. цена (€/m²)", "Обща сума (€)"]
    
    for i, header_text in enumerate(headers):
        hdr_cells[i].text = header_text
        set_cell_background(hdr_cells[i], "00519E")
        for paragraph in hdr_cells[i].paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(9.5)
                run.font.color.rgb = RGBColor(255, 255, 255)

    for row in table_data:
        row_cells = table.add_row().cells
        row_cells[0].text = str(row["Елемент"])
        row_cells[1].text = str(row["Размери"])
        row_cells[2].text = f"{row['Брой']} бр."
        row_cells[3].text = f"{row['Площ (m²)']:.2f} m²"
        row_cells[4].text = f"{row['Ед. цена (€/m²)']:.2f} €"
        row_cells[5].text = f"{row['Обща сума (€)']:.2f} €"

    doc.add_paragraph("")

    total_no_vat = total_formwork * unit_price
    vat_amount = total_no_vat * 0.20
    grand_total = total_no_vat + vat_amount

    label_type = "покупка" if offer_type == "Закупуване" else "наем"

    p_totals = doc.add_paragraph()
    p_totals.add_run("Обща кофражна площ: ").bold = True
    p_totals.add_run(f"{total_formwork:.2f} m²\n")
    p_totals.add_run(f"Обща стойност за {label_type} (без ДДС): ").bold = True
    p_totals.add_run(f"{total_no_vat:.2f} €\n")
    p_totals.add_run("ДДС (20%): ").bold = True
    p_totals.add_run(f"{vat_amount:.2f} €\n")
    
    r_grand = p_totals.add_run(f"ОБЩО ЗА ПЛАЩАНЕ: {grand_total:.2f} €")
    r_grand.bold = True
    r_grand.font.size = Pt(12)
    r_grand.font.color.rgb = RGBColor(0, 81, 158)

    doc.add_paragraph("")

    p_terms = doc.add_paragraph()
    p_terms.add_run("Условия на офертата:\n").bold = True
    terms_list = [
        "1. Всички цени са посочени в евро (€) без включен ДДС.",
        "2. Начин на плащане: 100% авансово плащане при потвърждение на поръчката.",
        "3. Срок за доставка: До 5 работни дни след постъпване на плащането.",
        "4. Гаранция: 12 месеца за фабрични дефекти при спазване на инструкциите за работа.",
        "5. Забележка: В цената не са включени анкери, тапи, кофражно масло и пластмасови тръби.",
        "6. Място на вземане: Склад на фирмата (Транспортът е за сметка на Купувача/Наемателя)."
    ]
    for term in terms_list:
        p_terms.add_run(f"{term}\n")

    p_footer = doc.add_paragraph()
    p_footer.add_run("\nС уважение,\n").bold = True
    p_footer.add_run("Екипът на ПЛАСПАНЕЛ ООД\nwww.tekoform.com")

    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio


# ============================================================
# ГЛАВЕН ВХОД: КАЧВАНЕ НА ЧЕРТЕЖ И РАЗЧИТАНЕ (1 ПЪТ ОТ AI)
# ============================================================
st.subheader("📂 1. Качете чертеж и задвижете Vision Агента")

uploaded_file = st.file_uploader("Изберете чертеж (PDF или снимка)", type=["pdf", "jpg", "png", "jpeg"])

if uploaded_file:
    if not api_key:
        st.error("⚠️ Грешка: Липсва GEMINI_API_KEY в Streamlit Secrets.")
    else:
        if st.button("🔍 Разчети чертежа с Gemini Vision AI", type="primary"):
            with st.spinner("Анализиране на чертежа с Vision AI (gemini-1.5-flash)..."):
                try:
                    processed_img = process_uploaded_file(uploaded_file)
                    st.session_state["processed_img"] = processed_img
                    
                    # 🤖 ЕДИНСТВЕНОТО ИЗВИКВАНЕ НА AI
                    blueprint_data = analyze_blueprint(processed_img, api_key)
                    st.session_state["blueprint_data"] = blueprint_data
                    st.success("✅ Чертежът е разчетен успешно! Данните са готови за оферта и панели.")
                except Exception as e:
                    st.error(f"Грешка при разчитането на чертежа: {e}")

# ============================================================
# РАЗДЕЛЯНЕ В ТАБОВЕ СЛЕД РАЗЧИТАНЕ
# ============================================================
if "blueprint_data" in st.session_state:
    data = st.session_state["blueprint_data"]
    elements = data.get("elements", [])
    project_from_ai = data.get("project_name", "Стоманобетонови елементи")

    st.divider()
    st.subheader(f"📍 Обект от чертежа: {project_from_ai}")

    tab1, tab2 = st.tabs(["📄 Оферти и Площи (Таб 1)", "🧩 Спецификация на Панели (Таб 2)"])

    # ----------------------------------------------------
    # ТАБ 1: ОФЕРТА В WORD
    # ----------------------------------------------------
    with tab1:
        st.write("Попълнете данните за клиента и генерирайте оферта:")
        col1, col2, col3, col4 = st.columns([2, 2, 1.2, 1.2])

        with col1:
            client_name_input = st.text_input("Клиент / Фирма (До:)", placeholder="Въведете име на клиент", key="t1_client")
        with col2:
            project_name_input = st.text_input("Име на обект", value=project_from_ai, key="t1_project")
        with col3:
            offer_type = st.selectbox("Тип оферта", ["Закупуване", "Наем"], key="t1_type")
        with col4:
            default_price = 100.0 if offer_type == "Закупуване" else 15.0
            unit_price = st.number_input("Ед. цена (€/m²)", value=default_price, step=1.0, key="t1_price")

        client_name = client_name_input.strip() if client_name_input.strip() else "—"
        project_name = project_name_input.strip() if project_name_input.strip() else project_from_ai

        table_data = []
        total_formwork = 0.0

        # Python бързо смята площта за всеки елемент
        for el in elements:
            t = el.get("type", "wall")
            cnt = int(el.get("count") or 1)
            name = el.get("name") or t.upper()

            w_m = float(el.get("width_m") or 0.3)
            l_m = float(el.get("length_m") or 1.0)
            th_m = float(el.get("thickness_m") or 0.25)
            h_m = float(el.get("height_m") or 3.0)
            l1_m = float(el.get("l1_m") or 1.0)
            l2_m = float(el.get("l2_m") or 1.0)
            l3_m = float(el.get("l3_m") or 1.0)

            if t == "column":
                perim = 2 * (w_m + l_m)
                area = perim * h_m * cnt
                dim_str = f"{w_m*100:.0f}x{l_m*100:.0f} cm, H={h_m:.1f}m"
                el_label = f"Колона {name}"
            elif t == "wall":
                perim = 2 * l_m
                area = perim * h_m * cnt
                dim_str = f"L={l_m:.1f}m, B={th_m*100:.0f}cm, H={h_m:.1f}m"
                el_label = f"Стена {name}"
            elif t == "l_wall":
                perim = 2 * (l1_m + l2_m)
                area = perim * h_m * cnt
                dim_str = f"L1={l1_m:.1f}m, L2={l2_m:.1f}m, H={h_m:.1f}m"
                el_label = f"L-Стена {name}"
            elif t == "u_wall":
                perim = 2 * (l1_m + l2_m + l3_m)
                area = perim * h_m * cnt
                dim_str = f"L1={l1_m:.1f}m, L2={l2_m:.1f}m, L3={l3_m:.1f}m, H={h_m:.1f}m"
                el_label = f"U-Стена {name}"
            else:
                perim = 2 * (w_m + l_m)
                area = perim * h_m * cnt
                dim_str = f"{w_m*100:.0f}x{l_m*100:.0f} cm, H={h_m:.1f}m"
                el_label = f"Елемент {name}"

            total_formwork += area
            row_total = area * unit_price

            table_data.append({
                "Елемент": el_label,
                "Размери": dim_str,
                "Брой": cnt,
                "Площ (m²)": round(area, 2),
                "Ед. цена (€/m²)": round(unit_price, 2),
                "Обща сума (€)": round(row_total, 2)
            })

        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True)

        total_no_vat = total_formwork * unit_price
        vat_amount = total_no_vat * 0.20
        grand_total = total_no_vat + vat_amount

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Общо кофраж", f"{total_formwork:.2f} m²")
        c2.metric(f"Сума {offer_type} (без ДДС)", f"{total_no_vat:.2f} €")
        c3.metric("ДДС (20%)", f"{vat_amount:.2f} €")
        c4.metric("ОБЩО С ДДС", f"{grand_total:.2f} €")

        word_file = create_teko_word_docx(client_name, project_name, offer_type, table_data, total_formwork, unit_price)
        st.download_button(
            label="📄 Изтегли офертата в Word (.docx)",
            data=word_file,
            file_name=f"Oferta_TEKO_{offer_type}_{client_name.replace(' ', '_')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    # ----------------------------------------------------
    # ТАБ 2: СПЕЦИФИКАЦИЯ НА ПАНЕЛИ ТЕКО
    # ----------------------------------------------------
    with tab2:
        st.write("Автоматично изчислени панели и аксесоари чрез Python математически алгоритми:")

        results = []
        for el in elements:
            t = el.get("type", "wall")
            cnt = int(el.get("count") or 1)
            
            w_m = float(el.get("width_m") or 0.3)
            l_m = float(el.get("length_m") or 1.0)
            th_m = float(el.get("thickness_m") or 0.25)
            h_m = float(el.get("height_m") or 3.0)
            l1_m = float(el.get("l1_m") or 1.0)
            l2_m = float(el.get("l2_m") or 1.0)
            l3_m = float(el.get("l3_m") or 1.0)

            if t == "column":
                res = teko_calculator.calculate_column(w_m, l_m, h_m, cnt)
            elif t == "wall":
                res = teko_calculator.calculate_wall(l_m, th_m, h_m, cnt)
            elif t == "l_wall":
                res = teko_calculator.calculate_l_wall(l1_m, l2_m, th_m, h_m, cnt)
            elif t == "u_wall":
                res = teko_calculator.calculate_u_wall(l1_m, l2_m, l3_m, th_m, h_m, cnt)
            else:
                res = teko_calculator.calculate_column(w_m, l_m, h_m, cnt)

            results.append(res)

        aggregated_panels = {}
        aggregated_accessories = {}
        total_area = sum(r["area_m2"] for r in results)

        st.subheader("📋 Детайли по елементи")
        for idx, el in enumerate(results, 1):
            st.write(f"**{idx}. {el['count']} бр. {el['type']}** ({el['dimensions']}) → **{el['area_m2']} m²**")
            for p, q in el["panels_spec"].items():
                aggregated_panels[p] = aggregated_panels.get(p, 0) + q
            for a, q in el["accessories"].items():
                aggregated_accessories[a] = aggregated_accessories.get(a, 0) + q

        st.divider()

        col_p, col_a = st.columns(2)
        with col_p:
            st.markdown("### 🟩 ОБЩО НЕОБХОДИМИ ПАНЕЛИ")
            for p, q in sorted(aggregated_panels.items()):
                st.write(f"• **{p}**: {q} бр.")

        with col_a:
            st.markdown("### 🔩 ОБЩО НЕОБХОДИМИ АКСЕСОАРИ")
            for a, q in sorted(aggregated_accessories.items()):
                st.write(f"• **{a}**: {q} бр.")

        st.divider()
        st.metric("ОБЩА КОФРАЖНА ПЛОЩ", f"{total_area:.2f} m²")
