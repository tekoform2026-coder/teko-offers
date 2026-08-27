import streamlit as st
import fitz  # PyMuPDF
import cv2
import numpy as np
from PIL import Image
from google import genai
import json
import pandas as pd
import io
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

st.set_page_config(page_title="TEKO Offers - Кофражни Сметки", layout="wide")

st.title("🏗️ TEKO Offers — Автоматично Изчисление на Кофраж")
st.write("Качете конструктивен чертеж (PDF или снимка), за да получите пълна кофражна оферта.")

# --- ВЗЕМАНЕ НА API KEY СКРИТО ОТ SECRETS ---
api_key = st.secrets.get("GEMINI_API_KEY", "")

# --- ОБРАБОТКА НА ИЗОБРАЖЕНИЕ ---
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

# --- VISION AI ИЗВЛИЧАНЕ ---
def extract_drawing_data(image_pil, api_key):
    client = genai.Client(api_key=api_key)
    
    prompt = """
    Извлечи всички вертикални конструктивни елементи от чертежа, които изискват кофраж (колони, шайби, бетонови стени, подпорни стени, фундаментални бордюри/стъпки).
    Върни САМО чист JSON обект със следната структура:

    {
      "project_name": "Име на проекта",
      "elements": [
        {
          "type": "column" или "shear_wall" или "wall" или "foundation",
          "name": "Маркировка (напр. К1, Ф1, Ш1)",
          "count": бройка,
          "width_cm": ширина_в_см,
          "length_cm": дължина_в_см,
          "height_m": височина_или_дълбочина_на_кофража_в_метри
        }
      ]
    }
    """
    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=[image_pil, prompt],
        config={'response_mime_type': 'application/json'}
    )
    return json.loads(response.text)

# --- ГЕНЕРИРАНЕ НА WORD ДОКУМЕНТ (.DOCX) ---
def create_word_docx(project_name, table_data, total_formwork):
    doc = Document()
    
    # Заглавие
    title_p = doc.add_paragraph()
    title_run = title_p.add_run("ОФЕРТА ЗА КОФРАЖНИ РАБОТИ")
    title_run.bold = True
    title_run.font.size = Pt(18)
    title_run.font.color.rgb = RGBColor(0, 51, 102)
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Информация за обекта
    p_info = doc.add_paragraph()
    p_info.add_run("Обект / Проект: ").bold = True
    p_info.add_run(f"{project_name}\n")
    p_info.add_run("Изготвил: ").bold = True
    p_info.add_run("TEKO Offers (Автоматична системна оферта)")
    
    doc.add_paragraph("")  # Празен ред
    
    # Таблица
    table = doc.add_table(rows=1, cols=7)
    table.style = 'Table Grid'
    
    hdr_cells = table.rows[0].cells
    headers = ["Елемент", "Тип", "Брой", "Сечение (см)", "Обиколка (м)", "Височина (м)", "Кофраж (кв.м)"]
    
    for i, header_text in enumerate(headers):
        hdr_cells[i].text = header_text
        for paragraph in hdr_cells[i].paragraphs:
            for run in paragraph.runs:
                run.bold = True

    for row_data in table_data:
        row_cells = table.add_row().cells
        row_cells[0].text = str(row_data["Елемент"])
        row_cells[1].text = str(row_data["Тип"])
        row_cells[2].text = str(row_data["Брой"])
        row_cells[3].text = str(row_data["Сечение (см)"])
        row_cells[4].text = str(row_data["Обиколка (м)"])
        row_cells[5].text = str(row_data["Височина (м)"])
        row_cells[6].text = str(row_data["Кофражна площ (кв.м)"])

    doc.add_paragraph("")
    
    # Крайна сума
    p_total = doc.add_paragraph()
    run_total = p_total.add_run(f"ОБЩО ВЕРТИКАЛЕН КОФРАЖ: {total_formwork:.2f} кв.м")
    run_total.bold = True
    run_total.font.size = Pt(14)
    run_total.font.color.rgb = RGBColor(0, 102, 204)

    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

# --- ИНТЕРФЕЙС ЗА КАЧВАНЕ ---
uploaded_file = st.file_uploader("Изберете чертеж (PDF или снимка)", type=["pdf", "jpg", "png", "jpeg"])

if uploaded_file:
    if not api_key:
        st.error("⚠️ Грешка: Липсва GEMINI_API_KEY в Streamlit Secrets.")
    else:
        if st.button("🚀 Генерирай Кофражна Оферта", type="primary"):
            with st.spinner("1/2 Обработка на чертежа..."):
                processed_img = process_uploaded_file(uploaded_file)
                st.image(processed_img, caption="Обработен чертеж (AI Vision Input)", use_container_width=True)

            with st.spinner("2/2 Разчитане от AI и пресмятане..."):
                try:
                    data = extract_drawing_data(processed_img, api_key)
                    project_name = data.get('project_name') or 'Конструктивен обект'

                    st.subheader(f"📋 Проект: {project_name}")

                    table_data = []
                    total_formwork = 0.0

                    for el in data.get('elements', []):
                        count = int(el.get('count') or 1)
                        w_m = float(el.get('width_cm') or 0) / 100.0
                        l_m = float(el.get('length_cm') or 0) / 100.0
                        h_m = float(el.get('height_m') or 2.70)

                        perimeter_m = 2 * (w_m + l_m)
                        formwork_m2 = perimeter_m * h_m * count
                        total_formwork += formwork_m2

                        table_data.append({
                            "Елемент": el.get('name') or '-',
                            "Тип": (el.get('type') or 'елемент').upper(),
                            "Брой": count,
                            "Сечение (см)": f"{w_m*100:.0f} x {l_m*100:.0f}",
                            "Обиколка (м)": round(perimeter_m, 2),
                            "Височина (м)": round(h_m, 2),
                            "Кофражна площ (кв.м)": round(formwork_m2, 2)
                        })

                    df = pd.DataFrame(table_data)
                    st.dataframe(df, use_container_width=True)

                    st.metric(label="ОБЩО ВЕРТИКАЛЕН КОФРАЖ ЗА ОФЕРТА", value=f"{total_formwork:.2f} кв.м")

                    # Генериране на Word файл за сваляне
                    word_doc_stream = create_word_docx(project_name, table_data, total_formwork)
                    st.download_button(
                        label="📄 Изтегли офертата в Word (.docx)",
                        data=word_doc_stream,
                        file_name=f"Oferta_Kofrach_{project_name.replace(' ', '_')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                except Exception as e:
                    st.error(f"Възникна грешка при обработката: {e}")
