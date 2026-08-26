import streamlit as st
import os
import tempfile
from pdf_parser import parse_pdf_elements
from offer_generator import generate_word_offer

st.set_page_config(page_title="TEKO - Генератор на Оферти", page_icon="🏗️", layout="centered")

st.title("🏗️ TEKO AI - Генератор на Оферти")
st.write("**ПЛАСПАНЕЛ ООД** | Автоматично генериране на търговски оферти")

st.divider()

# 1. Качване на PDF файл
st.subheader("1. Качване на чертеж / спецификация")
uploaded_file = st.file_uploader("Плъзнете или изберете PDF файл:", type=["pdf"])

st.divider()

# 2. Попълване на данни
st.subheader("2. Данни за офертата")

col1, col2 = st.columns(2)

with col1:
    client_name = st.text_input("Име на клиента / фирмата:", value="", placeholder="Въведете име на фирма / клиент")
    project_name = st.text_input("Име на обекта:", value="", placeholder="Въведете име на обекта")

with col2:
    offer_choice = st.radio("Тип на офертата:", ["Наем", "Продажба"])
    offer_type = "sale" if offer_choice == "Продажба" else "rental"
    
    default_price = 45.00 if offer_type == "sale" else 12.50
    price_per_m2 = st.number_input("Единична цена (EUR/m²):", value=default_price, step=0.50, format="%.2f")

st.divider()

# 3. Бутон за генериране
if st.button("🚀 Генерирай Оферта", type="primary", use_container_width=True):
    if uploaded_file is None:
        st.error("⚠️ Моля, първо качете PDF файл!")
    elif not client_name.strip():
        st.warning("⚠️ Моля, въведете име на клиента / фирмата!")
    elif not project_name.strip():
        st.warning("⚠️ Моля, въведете име на обекта!")
    else:
        with st.spinner("Сканиране на PDF файла и съставяне на офертата..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name

            elements = parse_pdf_elements(tmp_path)
            
            if not elements:
                st.error("Не бяха намерени валидни елементи в качения PDF файл.")
            else:
                safe_project = project_name.strip().replace(" ", "_").replace('"', '').replace("'", "")
                output_filename = f"Оферта_{safe_project}.docx"
                
                generate_word_offer(
                    client_name=client_name.strip(),
                    project_name=project_name.strip(),
                    elements=elements,
                    price_per_m2=price_per_m2,
                    offer_type=offer_type,
                    filename=output_filename
                )

                st.success("✅ Офертата е генерирана успешно!")
                
                with open(output_filename, "rb") as f:
                    st.download_button(
                        label="📥 ИЗТЕГЛИ ГОТОВАТА ОФЕРТА (.DOCX)",
                        data=f,
                        file_name=output_filename,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
                
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)