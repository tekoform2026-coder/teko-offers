import io
import fitz  # PyMuPDF
import pandas as pd
from PIL import Image
import streamlit as st
from gemini_agent2 import analyze_blueprint

# 1. Настройки на страницата
st.set_page_config(
    page_title="Teko Blueprint & Offer Generator",
    page_icon="🏗️",
    layout="wide"
)

# 2. Помощна функция за обработка на качения файл (PDF / Изображение)
def process_uploaded_file(uploaded_file):
    uploaded_file.seek(0)
    if uploaded_file.type == "application/pdf":
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        page = doc.load_page(0)  # Взема първата страница от PDF
        pix = page.get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return img
    else:
        return Image.open(uploaded_file)

# 3. Извличане на API ключ от Streamlit Secrets
api_key = st.secrets.get("GEMINI_API_KEY", "")

# 4. Заглавие и страничен панел
st.title("🏗️ Автоматизирано разчитане на чертежи и генериране на оферти")
st.markdown("Качете архитектурен чертеж (PDF или изображение), за да извлечете конструктивните елементи и да ги прегледате преди офертата.")

with st.sidebar:
    st.header("⚙️ Настройки")
    if not api_key:
        api_key = st.text_input("Въведете Gemini API Key:", type="password")
    else:
        st.success("🔑 API Ключът е зареден успешно!")

    st.divider()
    st.info("💡 **Инструкция:**\n1. Качете файл.\n2. Натиснете бутона за разчитане.\n3. Редактирайте данните в таблицата при нужда.\n4. Генерирайте готовата оферта.")

# 5. Инициализация на Session State
if "blueprint_data" not in st.session_state:
    st.session_state["blueprint_data"] = None
if "used_model" not in st.session_state:
    st.session_state["used_model"] = None
if "edited_df" not in st.session_state:
    st.session_state["edited_df"] = None

# 6. Качване на файл
uploaded_file = st.file_uploader(
    "Качете чертеж (PDF, PNG, JPG, JPEG):",
    type=["pdf", "png", "jpg", "jpeg"]
)

if uploaded_file:
    col_img, col_actions = st.columns([1, 1])

    with col_img:
        st.subheader("🖼️ Преглед на чертежа")
        try:
            processed_img = process_uploaded_file(uploaded_file)
            st.image(processed_img, use_container_width=True, caption="Зареден чертеж")
        except Exception as e:
            st.error(f"Грешка при зареждането на изображението: {e}")
            processed_img = None

    with col_actions:
        st.subheader("🤖 Разчитане с AI")
        if not api_key:
            st.warning("⚠️ Моля, въведете Gemini API Key в страничното меню.")
        else:
            if st.button("🔍 Разчети чертежа с Gemini Vision AI", type="primary", use_container_width=True):
                if processed_img:
                    with st.spinner("Анализиране на чертежа с Vision AI..."):
                        try:
                            # Извикване на AI анализа
                            blueprint_data, used_model = analyze_blueprint(processed_img, api_key)
                            
                            st.session_state["blueprint_data"] = blueprint_data
                            st.session_state["used_model"] = used_model
                            
                            # Преобразуване на елементите в Pandas DataFrame за лесно редактиране
                            elements_list = blueprint_data.get("elements", [])
                            st.session_state["edited_df"] = pd.DataFrame(elements_list)

                            st.success(f"✅ Успешно разчитане с модел **{used_model}**!")
                        except Exception as e:
                            st.error(f"Грешка при разчитането: {e}")

st.divider()

# 7. Секция за преглед и РЪЧНО РЕДАКТИРАНЕ на разчетените данни
if st.session_state["blueprint_data"] is not None:
    st.header("📝 Преглед и коригиране на елементите")

    # Редакция на името на проекта
    project_name = st.session_state["blueprint_data"].get("project_name", "Обект без име")
    updated_project_name = st.text_input("Име на проекта / обекта:", value=project_name)
    st.session_state["blueprint_data"]["project_name"] = updated_project_name

    st.subheader("📊 Данни за елементите (Коригирайте при нужда):")
    st.caption("Можете директно да променяте стойностите в клетките, да изтривате редове или да добавяте нови елементи от долния ред.")

    # Интерактивна таблица за редактиране
    df_to_edit = st.session_state["edited_df"]

    edited_df = st.data_editor(
        df_to_edit,
        num_rows="dynamic",  # Позволява добавяне и изтриване на редове
        column_config={
            "type": st.column_config.SelectboxColumn(
                "Тип елемент",
                options=["column", "wall", "l_wall", "u_wall"],
                required=True
            ),
            "name": st.column_config.TextColumn("Маркировка (напр. К1)"),
            "count": st.column_config.NumberColumn("Брой", min_value=1, step=1, default=1),
            "width_m": st.column_config.NumberColumn("Ширина (м)", format="%.2f"),
            "length_m": st.column_config.NumberColumn("Дължина (м)", format="%.2f"),
            "thickness_m": st.column_config.NumberColumn("Дебелина (м)", format="%.2f"),
            "l1_m": st.column_config.NumberColumn("Рамо 1 (м)", format="%.2f"),
            "l2_m": st.column_config.NumberColumn("Рамо 2 (м)", format="%.2f"),
            "l3_m": st.column_config.NumberColumn("Рамо 3 (м)", format="%.2f"),
            "height_m": st.column_config.NumberColumn("Височина (м)", format="%.2f")
        },
        use_container_width=True,
        key="elements_editor"
    )

    # Обновяване на състоянието при промени
    st.session_state["edited_df"] = edited_df

    st.divider()

    # 8. Изчисляване на количествата и генериране на офертата
    st.header("🧮 Резултати и Изчисления")

    if not edited_df.empty:
        # Изчисляване на обеми и кофражни площи за всеки елемент
        total_concrete_m3 = 0.0
        total_formwork_m2 = 0.0
        total_elements_count = 0

        for _, row in edited_df.iterrows():
            cnt = float(row.get("count", 1) or 1)
            h = float(row.get("height_m", 3.0) or 3.0)
            elem_type = str(row.get("type", "wall"))

            total_elements_count += int(cnt)

            if elem_type == "column":
                w = float(row.get("width_m", 0.3) or 0.3)
                l = float(row.get("length_m", 0.5) or 0.5)
                vol = w * l * h * cnt
                formwork = 2 * (w + l) * h * cnt

            elif elem_type == "wall":
                l = float(row.get("length_m", 5.0) or 5.0)
                t = float(row.get("thickness_m", 0.25) or 0.25)
                vol = l * t * h * cnt
                formwork = 2 * l * h * cnt

            elif elem_type == "l_wall":
                l1 = float(row.get("l1_m", 2.0) or 2.0)
                l2 = float(row.get("l2_m", 2.0) or 2.0)
                t = float(row.get("thickness_m", 0.25) or 0.25)
                vol = (l1 + l2) * t * h * cnt
                formwork = 2 * (l1 + l2) * h * cnt

            elif elem_type == "u_wall":
                l1 = float(row.get("l1_m", 2.0) or 2.0)
                l2 = float(row.get("l2_m", 2.0) or 2.0)
                l3 = float(row.get("l3_m", 2.0) or 2.0)
                t = float(row.get("thickness_m", 0.25) or 0.25)
                vol = (l1 + l2 + l3) * t * h * cnt
                formwork = 2 * (l1 + l2 + l3) * h * cnt
            else:
                vol, formwork = 0.0, 0.0

            total_concrete_m3 += vol
            total_formwork_m2 += formwork

        # Карти с обобщени показатели
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Общ брой елементи", f"{total_elements_count} бр.")
        m_col2.metric("Общ обем бетон", f"{total_concrete_m3:.2f} м³")
        m_col3.metric("Обща кофражна площ", f"{total_formwork_m2:.2f} м²")

        # Експорт на данните
        st.subheader("📥 Смъкване на коригираната таблица")
        csv_data = edited_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📄 Изтегли таблицата като CSV",
            data=csv_data,
            file_name=f"Oferta_{updated_project_name.replace(' ', '_')}.csv",
            mime="text/csv"
        )
    else:
        st.info("Няма налични елементи в таблицата. Добавете нов ред ръчно.")
