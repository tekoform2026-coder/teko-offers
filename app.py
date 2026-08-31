import io
import fitz  # PyMuPDF
import pandas as pd
from PIL import Image
import streamlit as st
from gemini_agent2 import analyze_blueprint

# 1. Настройки на страницата
st.set_page_config(
    page_title="Teko - Системен Вертикален Кофраж и Оферти",
    page_icon="🏗️",
    layout="wide"
)

# 2. Помощна функция за обработка на качения файл (PDF / Изображение)
def process_uploaded_file(uploaded_file):
    uploaded_file.seek(0)
    if uploaded_file.type == "application/pdf":
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return img
    else:
        return Image.open(uploaded_file)

# 3. Извличане на API ключ от Secrets
api_key = st.secrets.get("GEMINI_API_KEY", "")

# 4. Инициализация на Session State
if "blueprint_data" not in st.session_state:
    st.session_state["blueprint_data"] = None
if "used_model" not in st.session_state:
    st.session_state["used_model"] = None
if "edited_df" not in st.session_state:
    st.session_state["edited_df"] = pd.DataFrame()

# 5. Странично меню (Sidebar) - Данни за клиенти и Единични цени за Кофраж
with st.sidebar:
    st.header("⚙️ Настройки и Ценообразуване")
    
    if not api_key:
        api_key = st.text_input("Въведете Gemini API Key:", type="password")
    else:
        st.success("🔑 API Ключът е зареден!")

    st.divider()
    st.subheader("📋 Данни за Клиента и Обекта")
    client_name = st.text_input("Име на клиента / Фирма:", value="Запитване Клиент")
    project_name_input = st.text_input("Име на обект:", value="Обект Жилищна Сграда")
    offer_date = st.date_input("Дата на офертата")

    st.divider()
    st.subheader("💶 Цени Вертикален Кофраж Teko")
    price_formwork = st.number_input("Вертикален кофраж (наем/продажба лв./м²):", min_value=0.0, value=25.0, step=1.0)
    price_labor = st.number_input("Монтаж, демонтаж и труд (лв./м²):", min_value=0.0, value=18.0, step=1.0)
    vat_percent = st.number_input("ДДС (%):", min_value=0.0, value=20.0, step=1.0)

st.title("🏗️ Системен Вертикален Кофраж Teko - Анализ и Оферти")

# 6. Меню с Раздели (Табове)
tab1, tab2, tab3 = st.tabs([
    "📐 Чертеж и Редактиране", 
    "🧱 Кофражни Елементи (м²)", 
    "💰 Генериране на Оферта"
])

# ==========================================
# ТАБ 1: ЧЕРТЕЖ И РЕДАКТИРАНЕ
# ==========================================
with tab1:
    st.header("1. Качване на чертеж и корекция на данните")
    
    uploaded_file = st.file_uploader(
        "Изберете чертеж (PDF, PNG, JPG):", 
        type=["pdf", "png", "jpg", "jpeg"]
    )

    if uploaded_file:
        col_img, col_actions = st.columns([1, 1])

        with col_img:
            st.subheader("🖼️ Преглед на чертежа")
            try:
                processed_img = process_uploaded_file(uploaded_file)
                st.image(processed_img, use_container_width=True, caption="Качен чертеж")
            except Exception as e:
                st.error(f"Грешка при зареждането на изображението: {e}")
                processed_img = None

        with col_actions:
            st.subheader("🤖 AI Разчитане")
            if not api_key:
                st.warning("⚠️ Моля, въведете Gemini API Key в страничното меню.")
            else:
                if st.button("🔍 Разчети вертикалните елементи с AI", type="primary", use_container_width=True):
                    if processed_img:
                        with st.spinner("Анализиране за вертикални елементи (колони, шайби, стени)..."):
                            try:
                                res = analyze_blueprint(processed_img, api_key)
                                if isinstance(res, tuple):
                                    blueprint_data, used_model = res
                                else:
                                    blueprint_data, used_model = res, "Gemini Vision"

                                st.session_state["blueprint_data"] = blueprint_data
                                st.session_state["used_model"] = used_model

                                elements_list = blueprint_data.get("elements", [])
                                st.session_state["edited_df"] = pd.DataFrame(elements_list)
                                st.success(f"✅ Готово! Разчетено с модел: **{used_model}**")
                            except Exception as e:
                                st.error(f"Грешка при анализа: {e}")

    # Интерактивна таблица за преглед и корекция на разчетените елементи
    if not st.session_state["edited_df"].empty:
        st.divider()
        st.subheader("✏️ Ръчна корекция на разчетените вертикални елементи")
        st.caption("Можете да променяте размерите, да изтривате редове или да добавяте нови елементи от долния ред:")

        edited_df = st.data_editor(
            st.session_state["edited_df"],
            num_rows="dynamic",
            column_config={
                "type": st.column_config.SelectboxColumn(
                    "Тип елемент",
                    options=["column", "wall", "l_wall", "u_wall"],
                    required=True
                ),
                "name": st.column_config.TextColumn("Маркировка (К1, W1, Ш1...)"),
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
            key="elements_editor_tab1"
        )
        st.session_state["edited_df"] = edited_df

# ==========================================
# ТАБ 2: КОФРАЖНИ ЕЛЕМЕНТИ (САМО М²)
# ==========================================
with tab2:
    st.header("2. Спецификация на вертикалния кофраж Teko")
    
    df_calc = st.session_state["edited_df"]
    
    if df_calc.empty:
        st.info("ℹ️ Моля, първо качете чертеж и го разчетете в Таб 1.")
    else:
        detailed_rows = []
        total_formwork_area = 0.0
        total_count = 0

        for _, row in df_calc.iterrows():
            cnt = float(row.get("count", 1) or 1)
            h = float(row.get("height_m", 3.0) or 3.0)
            elem_type = str(row.get("type", "wall"))
            name = str(row.get("name", "Елемент"))

            total_count += int(cnt)
            area = 0.0

            if elem_type == "column":
                w = float(row.get("width_m", 0.3) or 0.3)
                l = float(row.get("length_m", 0.5) or 0.5)
                area = 2 * (w + l) * h * cnt
                desc = f"Колона {w:.2f} x {l:.2f} м (H={h:.2f} м)"

            elif elem_type == "wall":
                l = float(row.get("length_m", 5.0) or 5.0)
                t = float(row.get("thickness_m", 0.25) or 0.25)
                area = 2 * l * h * cnt
                desc = f"Права стена / шайба L={l:.2f} м, d={t:.2f} м"

            elif elem_type == "l_wall":
                l1 = float(row.get("l1_m", 2.0) or 2.0)
                l2 = float(row.get("l2_m", 2.0) or 2.0)
                t = float(row.get("thickness_m", 0.25) or 0.25)
                area = 2 * (l1 + l2) * h * cnt
                desc = f"L-образна шайба {l1:.2f}+{l2:.2f} м, d={t:.2f} м"

            elif elem_type == "u_wall":
                l1 = float(row.get("l1_m", 2.0) or 2.0)
                l2 = float(row.get("l2_m", 2.0) or 2.0)
                l3 = float(row.get("l3_m", 2.0) or 2.0)
                t = float(row.get("thickness_m", 0.25) or 0.25)
                area = 2 * (l1 + l2 + l3) * h * cnt
                desc = f"U-образно ядро {l1:.2f}+{l2:.2f}+{l3:.2f} м"

            total_formwork_area += area

            detailed_rows.append({
                "Маркировка": name,
                "Тип елемент": elem_type,
                "Описание": desc,
                "Брой": int(cnt),
                "Височина (м)": h,
                "Площ Вертикален Кофраж (м²)": round(area, 2)
            })

        df_detailed = pd.DataFrame(detailed_rows)

        m1, m2 = st.columns(2)
        m1.metric("📦 Общ брой вертикални елементи", f"{total_count} бр.")
        m2.metric("📊 ОБЩА ПЛОЩ НА ВЕРТИКАЛНИЯ КОФРАЖ", f"{total_formwork_area:.2f} м²")

        st.subheader("📋 Детайлна техническа спецификация")
        st.dataframe(df_detailed, use_container_width=True)

# ==========================================
# ТАБ 3: ГЕНЕРИРАНЕ НА ОФЕРТА
# ==========================================
with tab3:
    st.header("3. Търговска оферта за кофражни системи Teko")

    df_calc = st.session_state["edited_df"]

    if df_calc.empty:
        st.info("ℹ️ Няма въведени елементи за генериране на оферта.")
    else:
        # Сумиране на площта за кофраж
        total_formwork_area = 0.0

        for _, row in df_calc.iterrows():
            cnt = float(row.get("count", 1) or 1)
            h = float(row.get("height_m", 3.0) or 3.0)
            elem_type = str(row.get("type", "wall"))

            if elem_type == "column":
                w, l = float(row.get("width_m", 0.3) or 0.3), float(row.get("length_m", 0.5) or 0.5)
                total_formwork_area += 2 * (w + l) * h * cnt
            elif elem_type == "wall":
                l = float(row.get("length_m", 5.0) or 5.0)
                total_formwork_area += 2 * l * h * cnt
            elif elem_type == "l_wall":
                l1, l2 = float(row.get("l1_m", 2.0) or 2.0), float(row.get("l2_m", 2.0) or 2.0)
                total_formwork_area += 2 * (l1 + l2) * h * cnt
            elif elem_type == "u_wall":
                l1, l2, l3 = float(row.get("l1_m", 2.0) or 2.0), float(row.get("l2_m", 2.0) or 2.0), float(row.get("l3_m", 2.0) or 2.0)
                total_formwork_area += 2 * (l1 + l2 + l3) * h * cnt

        # Финансови изчисления
        cost_formwork = total_formwork_area * price_formwork
        cost_labor = total_formwork_area * price_labor

        subtotal = cost_formwork + cost_labor
        vat_amount = subtotal * (vat_percent / 100.0)
        grand_total = subtotal + vat_amount

        st.subheader(f"📄 Търговска Оферта за: {client_name}")
        st.write(f"**Обект:** {project_name_input} | **Дата:** {offer_date.strftime('%d.%m.%Y')}")

        # Таблица с разбивка на стойностите
        offer_breakdown = pd.DataFrame([
            {
                "Перо": "Системен вертикален кофраж Teko (платна, ъгли, вержове)", 
                "Количество": f"{total_formwork_area:.2f} м²", 
                "Ед. цена": f"{price_formwork:.2f} лв.", 
                "Обща стойност": f"{cost_formwork:.2f} лв."
            },
            {
                "Перо": "Монтаж, демонтаж и технически труд", 
                "Количество": f"{total_formwork_area:.2f} м²", 
                "Ед. цена": f"{price_labor:.2f} лв.", 
                "Обща стойност": f"{cost_labor:.2f} лв."
            },
        ])

        st.table(offer_breakdown)

        # Карти с крайните суми
        o_col1, o_col2, o_col3 = st.columns(3)
        o_col1.metric("Сума без ДДС", f"{subtotal:.2f} лв.")
        o_col2.metric(f"ДДС ({vat_percent:.0f}%)", f"{vat_amount:.2f} лв.")
        o_col3.metric("💰 КРАЙНА СУМА С ДДС", f"{grand_total:.2f} лв.", delta_color="normal")

        st.divider()

        # Експорт на офертата
        st.subheader("📥 Сваляне на офертата")
        
        offer_export_df = pd.DataFrame([
            {"Параметър": "Клиент", "Стойност": client_name},
            {"Параметър": "Обект", "Стойност": project_name_input},
            {"Параметър": "Дата на офертата", "Стойност": offer_date.strftime('%d.%m.%Y')},
            {"Параметър": "Обща площ вертикален кофраж", "Стойност": f"{total_formwork_area:.2f} м²"},
            {"Параметър": "Стойност кофражна система", "Стойност": f"{cost_formwork:.2f} лв."},
            {"Параметър": "Стойност труд и монтаж", "Стойност": f"{cost_labor:.2f} лв."},
            {"Параметър": "Общо без ДДС", "Стойност": f"{subtotal:.2f} лв."},
            {"Параметър": "ДДС", "Стойност": f"{vat_amount:.2f} лв."},
            {"Параметър": "Крайна Сума с ДДС", "Стойност": f"{grand_total:.2f} лв."}
        ])
        
        csv_offer = offer_export_df.to_csv(index=False).encode('utf-8-sig')
        
        st.download_button(
            label="📄 Свали офертата като CSV / Excel",
            data=csv_offer,
            file_name=f"Oferta_Teko_Kofraj_{client_name.replace(' ', '_')}_{offer_date}.csv",
            mime="text/csv",
            type="primary"
        )
