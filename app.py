import streamlit as st
import fitz  # PyMuPDF
import cv2
import numpy as np
from PIL import Image
from google import genai
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
import gemini_agent2

st.set_page_config(page_title="TEKO Offers - Генератор на Оферти", layout="wide")

st.title("🏗️ TEKO Offers — Интелигентна Кофражна Система")

# --- ВЗЕМАНЕ НА API KEY СКРИТО ОТ SECRETS ---
api_key = st.secrets.get("GEMINI_API_KEY", "")

# Разделяне на приложението на два основни раздела
tab1, tab2 = st.tabs(["📄 Оферти и Площи (Агент 1)", "🧩 Спецификация на Панели (Агент 2)"])

# ============================================================
# РАЗДЕЛ 1: ГЕНЕРАТОР НА ОФЕРТИ В WORD (АГЕНТ 1)
# ============================================================
with tab1:
    st.write("Попълнете данните за клиента, изберете тип оферта и качете чертеж за генериране на Word документ.")

    col1, col2, col3, col4 = st.columns([2, 2, 1.2, 1.2])

    with col1:
        client_name_input = st.text_input("Клиент / Фирма (До:)", placeholder="Въведете име на клиент или фирма", key="t1_client")
    with col2:
        project_name_input = st.text_input("Име на обект (Относно:)", placeholder="Въведете име на обект", key="t1_project")
    with col3:
        offer_type = st.selectbox("Тип оферта", ["Закупуване", "Наем"], key="t1_type")
    with col4:
        default_price = 100.0 if offer_type == "Закупуване" else 15.0
        unit_price = st.number_input("Ед. цена (€/m²)", value=default_price, step=1.0, key="t1_price")

    client_name = client_name_input.strip() if client_name_input.strip() else "—"
    project_name_user = project_name_input.strip() if project_name_input.strip() else "Стоманобетонови елементи"

    # Обработка на изображение
    def process_uploaded_file(uploaded_file):
        file_bytes = uploaded_file.read()
        
        if uploaded_file.name.lower().endswith('.pdf'):
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page = doc[0]
            pix = page.get_pixmap(dpi=150)
            img_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        else:
            img_pil = Image.open(uploaded_file)

        img_np = np.array(img_pil)
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY) if len(img_np.shape) == 3 else img_np
        enhanced = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        
        processed_pil = Image.fromarray(enhanced)
        return processed_pil

    # Vision AI извличане (Агент 1)
    def extract_drawing_data(image_pil, api_key):
        client = genai.Client(api_key=api_key)
        
        prompt = """
        Извлечи всички вертикални конструктивни елементи от чертежа (колони, шайби, бетонови стени, подпорни стени, фундаменти).
        Върни САМО чист JSON обект със следната структура:

        {
          "project_name": "Име на проекта от чертежа",
          "elements": [
            {
              "type": "Колона" или "Стена / Шайба" или "Фундамент",
              "name": "Маркировка",
              "count": бройка,
              "width_cm": ширина_в_см,
              "length_cm": дължина_в_см,
              "height_m": височина_или_дълбочина_в_метри
            }
          ]
        }
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image_pil, prompt],
            config={'response_mime_type': 'application/json'}
        )
        return json.loads(response.text)

    def set_cell_background(cell, fill_hex):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), fill_hex)
        tcPr.append(shd)

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
        r_comp.font.color.rgb = RGBColor(40, 40, 40)
        
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
            
            for c in row_cells:
                for p in c.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(9)

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

    uploaded_file_tab1 = st.file_uploader("Изберете чертеж (PDF или снимка)", type=["pdf", "jpg", "png", "jpeg"], key="t1_file")

    if uploaded_file_tab1:
        if not api_key:
            st.error("⚠️ Грешка: Липсва GEMINI_API_KEY в Streamlit Secrets.")
        else:
            if st.button("🚀 Генерирай Кофражна Оферта", type="primary", key="t1_btn"):
                with st.spinner("1/2 Обработка на чертежа..."):
                    processed_img = process_uploaded_file(uploaded_file_tab1)
                    st.image(processed_img, caption="Обработен чертеж (AI Vision Input)", use_container_width=True)

                with st.spinner("2/2 Извличане на контури и изчисляване..."):
                    try:
                        data = extract_drawing_data(processed_img, api_key)
                        final_project_name = project_name_user if project_name_user != "Стоманобетонови елементи" else data.get('project_name', 'Стоманобетонови елементи')

                        st.subheader(f"📋 Обект: {final_project_name} ({offer_type})")

                        table_data = []
                        total_formwork = 0.0

                        for el in data.get('elements', []):
                            count = int(el.get('count') or 1)
                            w_cm = float(el.get('width_cm') or 0)
                            l_cm = float(el.get('length_cm') or 0)
                            h_m = float(el.get('height_m') or 3.0)

                            w_m = w_cm / 100.0
                            l_m = l_cm / 100.0

                            perimeter_m = 2 * (w_m + l_m)
                            area_m2 = perimeter_m * h_m * count
                            row_total_price = area_m2 * unit_price
                            total_formwork += area_m2

                            el_type = el.get('type') or 'Елемент'
                            if "Стена" in el_type or "Шайба" in el_type:
                                dim_str = f"L={l_m:.1f}m, B={w_cm:.0f}cm, H={h_m:.1f}m"
                            else:
                                dim_str = f"{w_cm:.0f}x{l_cm:.0f} cm, H={h_m:.1f}m"

                            table_data.append({
                                "Елемент": el_type,
                                "Размери": dim_str,
                                "Брой": count,
                                "Площ (m²)": round(area_m2, 2),
                                "Ед. цена (€/m²)": round(unit_price, 2),
                                "Обща сума (€)": round(row_total_price, 2)
                            })

                        df = pd.DataFrame(table_data)
                        st.dataframe(df, use_container_width=True)

                        total_no_vat = total_formwork * unit_price
                        vat_amount = total_no_vat * 0.20
                        grand_total = total_no_vat + vat_amount

                        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                        col_m1.metric("Общо кофраж", f"{total_formwork:.2f} m²")
                        col_m2.metric(f"Сума {offer_type} (без ДДС)", f"{total_no_vat:.2f} €")
                        col_m3.metric("ДДС (20%)", f"{vat_amount:.2f} €")
                        col_m4.metric("ОБЩО С ДДС", f"{grand_total:.2f} €")

                        word_stream = create_teko_word_docx(client_name, final_project_name, offer_type, table_data, total_formwork, unit_price)
                        st.download_button(
                            label="📄 Изтегли фирмена оферта в Word (.docx)",
                            data=word_stream,
                            file_name=f"Oferta_TEKO_{offer_type}_{client_name.replace(' ', '_')}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                    except Exception as e:
                        st.error(f"Грешка при генерирането: {e}")

# ============================================================
# РАЗДЕЛ 2: СПЕЦИФИКАЦИЯ НА ПАНЕЛИ ТЕКО (GEMINI AGENT 2)
# ============================================================
with tab2:
    st.write("Качете чертеж/план, за да може **Gemini Vision Agent 2** да разпознае видовете стени/колони и да генерира точна спецификация на необходимите панели и аксесоари.")

    uploaded_file_tab2 = st.file_uploader("Изберете чертеж за разчитане на панели (PDF или снимка)", type=["pdf", "jpg", "png", "jpeg"], key="t2_file")

    if uploaded_file_tab2:
        if not api_key:
            st.error("⚠️ Грешка: Липсва GEMINI_API_KEY в Streamlit Secrets.")
        else:
            if st.button("🚀 Анализирай с Agent 2 & Изчисли Панели", type="primary", key="t2_btn"):
                with st.spinner("1/2 Обработка на изображението..."):
                    # Използваме същата обработка за подготвяне на изображението
                    processed_img_tab2 = process_uploaded_file(uploaded_file_tab2)
                    st.image(processed_img_tab2, caption="Обработен чертеж (Agent 2 Input)", use_container_width=True)

                with st.spinner("2/2 Gemini Agent 2 разчита конструкцията и изчислява панелите..."):
                    try:
                        # Вторият агент анализира чертежа и връща елементите
                        elements_data = gemini_agent2.analyze_blueprint_with_agent2(processed_img_tab2, api_key)
                        
                        results = []
                        for item in elements_data:
                            t = item.get("type")
                            cnt = int(item.get("count", 1))
                            
                            if t == "column":
                                res = teko_calculator.calculate_column(
                                    float(item["width_m"]), float(item["length_m"]), float(item["height_m"]), cnt
                                )
                                results.append(res)
                            elif t == "wall":
                                res = teko_calculator.calculate_wall(
                                    float(item["length_m"]), float(item["thickness_m"]), float(item["height_m"]), cnt
                                )
                                results.append(res)
                            elif t == "l_wall":
                                res = teko_calculator.calculate_l_wall(
                                    float(item["l1_m"]), float(item["l2_m"]), float(item["thickness_m"]), float(item["height_m"]), cnt
                                )
                                results.append(res)
                            elif t == "u_wall":
                                res = teko_calculator.calculate_u_wall(
                                    float(item["l1_m"]), float(item["l2_m"]), float(item["l3_m"]), float(item["thickness_m"]), float(item["height_m"]), cnt
                                )
                                results.append(res)

                        st.success("Чертежът е разчетен успешно от Gemini Agent 2!")
                        
                        # Агрегиране на панелите и аксесоарите
                        aggregated_panels = {}
                        aggregated_accessories = {}
                        total_area = sum(r["area_m2"] for r in results)

                        st.subheader("📋 Детайлно разпознати елементи")
                        for idx, el in enumerate(results, 1):
                            st.write(f"**{idx}. {el['count']} бр. {el['type']}** ({el['dimensions']}) → **{el['area_m2']} m²**")
                            for panel, qty in el["panels_spec"].items():
                                aggregated_panels[panel] = aggregated_panels.get(panel, 0) + qty
                            for acc, qty in el["accessories"].items():
                                aggregated_accessories[acc] = aggregated_accessories.get(acc, 0) + qty

                        st.divider()
                        
                        col_panels, col_acc = st.columns(2)
                        
                        with col_panels:
                            st.markdown("### 🟩 ОБЩО НЕОБХОДИМИ ПАНЕЛИ")
                            for panel, qty in sorted(aggregated_panels.items()):
                                st.write(f"• **{panel}**: {qty} бр.")
                                
                        with col_acc:
                            st.markdown("### 🔩 ОБЩО НЕОБХОДИМИ АКСЕСОАРИ")
                            for acc, qty in sorted(aggregated_accessories.items()):
                                st.write(f"• **{acc}**: {qty} бр.")

                        st.divider()
                        st.metric("ОБЩА КОФРАЖНА ПЛОЩ", f"{total_area:.2f} m²")

                    except Exception as e:
                        st.error(f"Грешка при разчитане или пресмятане: {e}")
