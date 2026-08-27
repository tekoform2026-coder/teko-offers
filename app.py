import streamlit as st
import fitz  # PyMuPDF
import cv2
import numpy as np
from PIL import Image
from google import genai
import json
import pandas as pd

st.set_page_config(page_title="TEKO Offers - Кофражни Сметки", layout="wide")

st.title("🏗️ TEKO Offers — Автоматично Изчисление на Кофраж")
st.write("Качете конструктивен чертеж (PDF или снимка), за да получите пълна кофражна оферта.")

# --- СТРАНИЧЕН ПАНЕЛ ЗА НАСТРОЙКИ ---
st.sidebar.header("⚙️ Настройки")
# Позволява ползване на Secrets или ръчно въвеждане на API Key
default_api_key = st.secrets.get("GEMINI_API_KEY", "")
api_key = st.sidebar.text_input("Gemini API Key", value=default_api_key, type="password")

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
    Извлечи всички вертикални конструктивни елементи от чертежа, които изискват кофраж (колони, шайби, бетонови стени, подпорни стени, фундаментални бордюри/стълби).
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

# --- ИНТЕРФЕЙС ЗА КАЧВАНЕ ---
uploaded_file = st.file_uploader("Изберете чертеж", type=["pdf", "jpg", "png", "jpeg"])

if uploaded_file:
    if not api_key:
        st.warning("⚠️ Моля, въведете вашия Gemini API Key в страничния панел!")
    else:
        if st.button("🚀 Генерирай Кофражна Оферта", type="primary"):
            with st.spinner("1/2 Обработка на чертежа и подобряване на контраста..."):
                processed_img = process_uploaded_file(uploaded_file)
                st.image(processed_img, caption="Обработен чертеж (AI Vision Input)", use_container_width=True)

            with st.spinner("2/2 Разчитане от AI и пресмятане на кофражните площи..."):
                data = extract_drawing_data(processed_img, api_key)

                st.subheader(f"📋 Проект: {data.get('project_name', 'Обект')}")

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
                        "Елемент": el.get('name', '-'),
                        "Тип": (el.get('type') or 'елемент').upper(),
                        "Брой": count,
                        "Сечение (см)": f"{w_m*100:.0f} x {l_m*100:.0f}",
                        "Обиколка (м)": round(perimeter_m, 2),
                        "Височина (м)": round(h_m, 2),
                        "Кофражна площ (кв.м)": round(formwork_m2, 2)
                    })

                # Таблица с резултати
                df = pd.DataFrame(table_data)
                st.dataframe(df, use_container_width=True)

                # Главна метрика
                st.metric(label="ОБЩО ВЕРТИКАЛЕН КОФРАЖ ЗА ОФЕРТА", value=f"{total_formwork:.2f} кв.м")

                # Бутон за изтегляне на CSV
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Изтегли офертата (CSV)",
                    data=csv,
                    file_name="Kofrach_Oferta.csv",
                    mime="text/csv"
                )
