"""
Език на интерфейса: български (по подразбиране) и английски (потребителят, 17.11.2026).

t("текст на български", **стойности) връщa текста на избрания език; ключът е българският текст,
така че непреведен текст се показва на български. Стойностите се вмъкват с {име}.
Документите (PDF, Word оферта, Excel) и данните (имена на елементи, бележки от Gemini) остават на български.
Езикът се избира с флагчетата горе вдясно (language_switch) и се пази в адреса (?lang=en) - остава след F5.
"""
from urllib.parse import quote

import streamlit as st

LANGUAGES = ("bg", "en")
LANG_LABELS = {"bg": "БГ", "en": "EN"}


def lang():
    try:
        return st.session_state.get("lang", "bg")
    except Exception:  # noqa: BLE001 - без Streamlit (тестовете) - български
        return "bg"


def t(text, **values):
    """Текстът на избрания език; стойностите се вмъкват с {име}."""
    if lang() == "en":
        text = EN.get(text, text)
    return text.format(**values) if values else text


# Имената на артикулите от сметката (панели и аксесоари) - само за показване на екрана
_ITEM_WORDS = [("Вътрешен ъгъл", "Inner corner"), ("Външен ъгъл", "Outer corner"), ("Ръкохватка", "Handle"),
               ("Ригел", "Waler"), ("Вертикализатор", "Push-pull prop"), ("Шпилка", "Tie rod"), ("Гайка", "Nut"),
               ("Компенсатор", "Compensator"), ("(полегнал)", "(lying)"), (" см", " cm"), ("бр.", "pcs")]


def t_item(text):
    """Име на артикул или размери от сметката на избрания език („Ригел AW 200“ -> „Waler AW 200“)."""
    text = str(text)
    if lang() == "en":
        for bg, en in _ITEM_WORDS:
            text = text.replace(bg, en)
    return text


def init_language():
    """Езикът от адреса (?lang=en) при първото пускане на сесията."""
    if "lang" not in st.session_state:
        st.session_state["lang"] = st.query_params.get("lang", "bg")
        if st.session_state["lang"] not in LANGUAGES:
            st.session_state["lang"] = "bg"


def _switched():
    chosen = st.session_state.get("lang_switch")
    if chosen is None:  # повторен клик върху избрания език го маха - връща се
        st.session_state["lang_switch"] = lang()
        return
    st.session_state["lang"] = chosen
    st.query_params["lang"] = chosen


def _flag(svg):
    return "url(\"data:image/svg+xml," + quote(svg) + "\")"


FLAG_BG = _flag("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 5 3'><rect width='5' height='3' fill='#fff'/>"
                "<rect y='1' width='5' height='1' fill='#00966E'/><rect y='2' width='5' height='1' fill='#D62612'/></svg>")
FLAG_GB = _flag("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 60 30'><clipPath id='c'>"
                "<path d='M30,15h30v15zv15h-30zh-30v-15zv-15h30z'/></clipPath><path d='M0,0v30h60v-30z' fill='#012169'/>"
                "<path d='M0,0L60,30M60,0L0,30' stroke='#fff' stroke-width='6'/>"
                "<path d='M0,0L60,30M60,0L0,30' clip-path='url(#c)' stroke='#C8102E' stroke-width='4'/>"
                "<path d='M30,0v30M0,15h60' stroke='#fff' stroke-width='10'/>"
                "<path d='M30,0v30M0,15h60' stroke='#C8102E' stroke-width='6'/></svg>")


def language_switch():
    """Флагчетата БГ / EN; изборът презарежда страницата на новия език."""
    st.markdown(f"""
        <style>
        .st-key-lang_switch button p::before {{content: ""; display: inline-block; width: 21px; height: 14px;
            margin-right: 6px; vertical-align: -2px; background-size: cover; border: 1px solid #d0d5dd;}}
        .st-key-lang_switch button:nth-of-type(1) p::before {{background-image: {FLAG_BG};}}
        .st-key-lang_switch button:nth-of-type(2) p::before {{background-image: {FLAG_GB};}}
        .st-key-lang_bar {{margin-bottom: -6px;}}
        </style>
    """, unsafe_allow_html=True)
    if "lang_switch" not in st.session_state:
        st.session_state["lang_switch"] = lang()
    with st.container(key="lang_bar", horizontal=True, horizontal_alignment="right"):
        st.segmented_control("Език / Language", options=LANGUAGES, format_func=LANG_LABELS.get,
                             key="lang_switch", on_change=_switched, label_visibility="collapsed")


EN = {
    # Страница и горна лента
    "TEKO - Вертикален Кофраж и Оферти": "TEKO - Vertical Formwork and Offers",
    "TEKO — Оптимизация на панели": "TEKO — Panel Optimization",
    "AI система за кофражно планиране": "AI system for formwork planning",
    "ТЕКО България ООД": "TEKO Bulgaria Ltd.",
    "⚙️ Настройки": "⚙️ Settings",
    "Въведете Gemini API Key:": "Enter the Gemini API Key:",
    "🔑 API Ключът е зареден!": "🔑 The API key is loaded!",

    # Проекти
    "Проекти": "Projects",
    "Нов проект": "New project",
    "Име на проекта:": "Project name:",
    "Клиент:": "Client:",
    "Дата:": "Date:",
    "Създай и отвори": "Create and open",
    "Архивът в Google не е достъпен ({error}). Проектите се пазят само докато страницата е отворена.":
        "The Google archive is not available ({error}). Projects are kept only while the page is open.",
    "Без архив (няма ключ за Google в secrets): проектите се губят при презареждане.":
        "No archive (no Google key in secrets): projects are lost when the page is reloaded.",
    "Списъкът не може да се зареди от Google: {error}": "The list cannot be loaded from Google: {error}",
    "Презаредете страницата (F5). Проектът е създаден и записан, но не можа да се отвори веднага, защото бутонът "
    "„Създай и отвори“ беше натиснат твърде бързо след въвеждането на името. Следващия път изчакайте 2-3 секунди, "
    "преди да натиснете бутона.":
        "Reload the page (F5). The project was created and saved, but could not be opened right away because "
        "“Create and open” was clicked too soon after typing the name. Next time wait 2-3 seconds before clicking.",
    "ℹ️ Няма проекти. Натиснете „Нов проект“.": "ℹ️ No projects yet. Click “New project”.",
    "Име": "Name",
    "Клиент": "Client",
    "Дата": "Date",
    "Последна промяна": "Last modified",
    "Действия": "Actions",
    "Дублирай": "Duplicate",
    "Потвърди": "Confirm",
    "Проектът се маха от списъка (в архива остава с отметка „Изтрит“).":
        "The project is removed from the list (it stays in the archive marked “deleted”).",
    "Изтрий": "Delete",
    "✏️ Промени": "✏️ Edit",
    "Промяна на името на проекта, клиента (възложителя) и датата.":
        "Change the project name, the client (employer) and the date.",
    "Клиент (възложител):": "Client (employer):",
    "Запази": "Save",
    "← Проекти": "← Projects",
    "Записва таблицата и се връща към списъка с проекти.": "Saves the table and returns to the project list.",

    # Табове
    "📐 Чертеж и Редактиране": "📐 Drawing and Editing",
    "🧱 Кофражни Елементи и Панели TEKO": "🧱 Formwork Elements and TEKO Panels",
    "📄 PDF Чертежи": "📄 PDF Drawings",
    "📄 Оферта": "📄 Offer",
    "📦 Складова наличност": "📦 Stock",

    # Таб 1
    "1. Избор на начин за въвеждане на елементи": "1. How to enter the elements",
    "Изберете режим на работа:": "Choose the working mode:",
    "🤖 Автоматично разчитане от чертежи": "🤖 Automatic reading from drawings",
    "⌨️ Ръчно въвеждане (Таблица)": "⌨️ Manual entry (Table)",
    "Качване на чертеж и AI разчитане": "Upload a drawing and AI reading",
    "Изберете чертеж (PDF, PNG, JPG):": "Choose a drawing (PDF, PNG, JPG):",
    "🖼️ Преглед на файла": "🖼️ File preview",
    "Качен чертеж": "Uploaded drawing",
    " - стр. 1 от {n}; към AI отиват всички {n}": " - page 1 of {n}; all {n} pages are sent to the AI",
    "Грешка при зареждането: {error}": "Loading error: {error}",
    "AI Разчитане": "AI Reading",
    "Избери AI модел за разчитане:": "Choose the AI model:",
    "Изберете кой модел на Gemini да анализира чертежа.": "Choose which Gemini model analyses the drawing.",
    "⚠️ Моля, въведете Gemini API Key в страничното меню.": "⚠️ Please enter the Gemini API Key in the sidebar.",
    "🔍 Разчети чертежа с Vision AI": "🔍 Read the drawing with Vision AI",
    "Извличане на вертикални кофражни елементи...": "Extracting vertical formwork elements...",
    "✅ Готово! Разчетено с: **{model}**": "✅ Done! Read with: **{model}**",
    "Грешка при анализа: {error}": "Analysis error: {error}",
    "⌨️ Ръчно въвеждане и управление в таблицата": "⌨️ Manual entry and table management",
    "📏 Стандартна височина на етажа": "📏 Standard storey height",
    "Стандартна височина за всички елементи:": "Standard height for all elements:",
    "270 см": "270 cm",
    "300 см": "300 cm",
    "Друга": "Other",
    "Височина (см):": "Height (cm):",
    "Елементите с празна „Височина (см)“ в таблицата се смятат с {h} см. Височината, въведена в таблицата, "
    "остава с предимство.":
        "Elements with an empty “Height (cm)” in the table are calculated with {h} cm. A height entered in the "
        "table takes precedence.",
    "↕️ Приложи {h} см към всички редове": "↕️ Apply {h} cm to all rows",
    "Записва стандартната височина във всички редове на таблицата, включително разчетените от чертежа. "
    "Незапазените промени в таблицата се губят - първо натиснете „Запази и Изчисли“.":
        "Writes the standard height into all table rows, including those read from the drawing. Unsaved "
        "changes in the table are lost - click “Save and Calculate” first.",
    "ℹ️ Таблицата е празна - няма редове за промяна.": "ℹ️ The table is empty - there are no rows to change.",
    "✅ Височина {h} см е записана в {n} реда.": "✅ Height {h} cm was written into {n} rows.",
    "✏️ Таблица с вертикални кофражни елементи": "✏️ Vertical formwork elements table",
    "Тип елемент": "Element type",
    "Наименование / Маркировка": "Name / Mark",
    "Брой": "Qty",
    "Стена A (см)": "Wall A (cm)",
    "При права стена и колона - дължината": "For a straight wall and a column - the length",
    "Дебелина стена A (см)": "Wall A thickness (cm)",
    "Стена B (см)": "Wall B (cm)",
    "Дебелина стена B (см)": "Wall B thickness (cm)",
    "L-, П- и Т-стена; празна = като стена A (попълва се само когато е различна)":
        "L-, U- and T-wall; empty = same as wall A (fill in only when different)",
    "Стена C (см)": "Wall C (cm)",
    "При Т-стена: от левия край на полката до лявото лице на реброто; празно = реброто е в средата":
        "For a T-wall: from the left end of the flange to the left face of the stem; empty = the stem is in the middle",
    "Дебелина стена C (см)": "Wall C thickness (cm)",
    "Само за П-стена; празна = като стена A (попълва се само когато е различна)":
        "U-wall only; empty = same as wall A (fill in only when different)",
    "Височина (см)": "Height (cm)",
    "Затворен край 1": "Closed end 1",
    "Затворен край 2": "Closed end 2",
    "Затворен край 3 (само T-стена)": "Closed end 3 (T-wall only)",
    "Какъв елемент да се добави?": "Which element should be added?",
    "Изберете тип елемент": "Choose an element type",
    "➕ Добави елемент": "➕ Add element",
    "Записва таблицата и добавя нов ред от избрания тип (1 бр., затворени краища).":
        "Saves the table and adds a new row of the chosen type (1 pc, closed ends).",
    "💾 Запази и Изчисли": "💾 Save and Calculate",
    "Изберете тип елемент и натиснете отново „➕ Добави елемент“.":
        "Choose an element type and click “➕ Add element” again.",
    "✅ Данните са запазени и преизчислени успешно! Можете да проверите резултатите в следващите табове.":
        "✅ The data was saved and recalculated! You can check the results in the next tabs.",
    "👁 Преглед на елементите": "👁 Element preview",
    "Прегледът показва записаните данни - обновява се след „Запази и Изчисли“. Полетата се отварят без "
    "презареждане; отметката „Покажи изгледа отпред“ презарежда страницата, затова първо запишете промените в "
    "таблицата.":
        "The preview shows the saved data - it is updated after “Save and Calculate”. The panels open without "
        "reloading; the “Show front view” checkbox reloads the page, so save the table changes first.",
    "ℹ️ Няма записани елементи за преглед.": "ℹ️ There are no saved elements to preview.",

    # Типове елементи
    "Колона": "Column",
    "Права стена": "Straight wall",
    "L-стена": "L-wall",
    "П-стена": "U-wall",
    "T-стена": "T-wall",
    "Права Стена": "Straight Wall",
    "L-образна Стена": "L-shaped Wall",
    "П-образна Стена": "U-shaped Wall",
    "T-образна Стена": "T-shaped Wall",

    # Преглед на елемент
    ", затворени краища: {n}": ", closed ends: {n}",
    "бр.": "pcs",
    "панела": "panels",
    "ъгли": "corners",
    "ригели": "walers",
    "верт.": "props",
    "ръкохватки": "handles",
    "шпилки": "tie rods",
    "Елементът не може да се начертае - проверете размерите ({error}).":
        "The element cannot be drawn - check the dimensions ({error}).",
    "Количества ({n} бр.): ": "Quantities ({n} pcs): ",
    "Изглед отгоре": "Top view",
    "Покажи изгледа отпред": "Show the front view",
    "Изглед отпред": "Front view",

    # Редове по височина
    "Ред {i}: Компенсатор TC ({h} cm)": "Row {i}: Compensator TC ({h} cm)",
    "Ред {i}: Полегнал ({h} cm)": "Row {i}: Lying ({h} cm)",
    "Ред {i}: Изправен ({h} cm)": "Row {i}: Upright ({h} cm)",

    # Предупреждения за размерите
    "Стена A": "Wall A",
    "Стена B": "Wall B",
    "Стена C": "Wall C",
    "Дебелина стена A": "Wall A thickness",
    "Височина": "Height",
    "Дължината": "The length",
    "• **{name}**: липсва размер ({missing}) - празен или 0. Попълнете го в таблицата, иначе сметката и чертежът "
    "не са верни.":
        "• **{name}**: missing dimension ({missing}) - empty or 0. Fill it in the table, otherwise the "
        "calculation and the drawing are wrong.",
    "• **{name}**: Височина {h} cm не е кратна на 5 cm (закръгля се нагоре до 5 cm).":
        "• **{name}**: Height {h} cm is not a multiple of 5 cm (rounded up to 5 cm).",
    "• **{name}**: {label} {value} cm не е кратна на 5 cm - панели до {panels} cm + дървена дъска {board} cm "
    "(само на чертежа, не влиза в сметката и площта).":
        "• **{name}**: {label} {value} cm is not a multiple of 5 cm - panels up to {panels} cm + timber board "
        "{board} cm (drawing only, not in the quantities or the area).",
    "• **{name}**: Мястото на реброто (Стена C = {l3} cm) не е кратно на 5 cm.":
        "• **{name}**: The stem position (Wall C = {l3} cm) is not a multiple of 5 cm.",
    "• **{name}**: Реброто на {l3} cm от левия край не оставя място за ъгъл IN (10 cm) и поне 5 cm панел от двете "
    "страни на полката ({l1} cm) - проверете Стена C.":
        "• **{name}**: A stem at {l3} cm from the left end leaves no room for an IN corner (10 cm) and at least a "
        "5 cm panel on both sides of the flange ({l1} cm) - check Wall C.",
    "• **{name}**: Страна A ({l1} cm) или B ({l2} cm) е твърде къса за T-стена с дебелина {t} cm - проверете "
    "Стена A и Стена B.":
        "• **{name}**: Side A ({l1} cm) or B ({l2} cm) is too short for a T-wall {t} cm thick - check Wall A and "
        "Wall B.",
    "• **{name}**: {small} - размерите са в **сантиметри**; въведени ли са в метри? (напр. 2.5 м = 250 см)":
        "• **{name}**: {small} - dimensions are in **centimetres**; were they entered in metres? "
        "(e.g. 2.5 m = 250 cm)",

    # Склад - предупреждения
    "⚠️ Не стигат в склада (таб „Складова наличност“):": "⚠️ Not enough in stock (tab “Stock”):",
    "- **{k}**: нужни {q} бр., на склад {a} бр. (не стигат {d} бр.)":
        "- **{k}**: needed {q} pcs, in stock {a} pcs (short by {d} pcs)",
    "⚠️ Няма ги в складовата наличност:": "⚠️ Not in the stock list:",
    "- **{k}**: нужни {q} бр.": "- **{k}**: needed {q} pcs",

    # Таб 2
    "2. Спецификация на кофражните елементи и панели TEKO": "2. Specification of formwork elements and TEKO panels",
    "ℹ️ Въведете елементи в Таб 1 и натиснете 'Запази и Изчисли'.":
        "ℹ️ Enter elements in Tab 1 and click 'Save and Calculate'.",
    "Елемент": "Element",
    "Размери": "Dimensions",
    "Площ (m²)": "Area (m²)",
    "Разпределение по височина": "Height breakdown",
    "Панели TEKO (Вид и брой)": "TEKO panels (type and qty)",
    "Код на панела / коф. елемент": "Panel / formwork element code",
    "Общ брой (бр.)": "Total qty (pcs)",
    "Ед. тегло (kg)": "Unit weight (kg)",
    "Общо тегло (kg)": "Total weight (kg)",
    "Аксесоар / Окомплектовка": "Accessory / Fittings",
    "📊 ОБЩА КОФРАЖНА ПЛОЩ": "📊 TOTAL FORMWORK AREA",
    "⚖️ ОБЩО ТЕГЛО НА КОФРАЖА": "⚖️ TOTAL FORMWORK WEIGHT",
    "⚠️ Предупреждения за нестандартни размери в кофражните елементи":
        "⚠️ Warnings for non-standard dimensions of the formwork elements",
    "📋 Спецификация на кофражните елементи и съответните панели": "📋 Formwork elements and their panels",
    "📦 Панели TEKO (Общо: {w} kg)": "📦 TEKO panels (Total: {w} kg)",
    "Аксесоари и Ъгли (Общо: {w} kg)": "Accessories and Corners (Total: {w} kg)",
    "📊 КСС и чертежи в Excel": "📊 Bill of quantities and drawings in Excel",
    "Лист „Кол. сметка“ - артикулите в реда на офертата; лист за всеки елемент - изглед отгоре и изглед отпред от "
    "клетки (1 клетка = 5 см) за редакция; лист с всички панели за копиране.":
        "Sheet “Кол. сметка” - the items in offer order; a sheet for each element - top and front view made of "
        "cells (1 cell = 5 cm) for editing; a sheet with all panels for copying. The file is in Bulgarian.",
    "📊 Създай Excel (КСС и чертежи)": "📊 Create Excel (BoQ and drawings)",
    "Генериране на Excel...": "Generating Excel...",
    "📥 Изтегли КСС и чертежи (Excel .xlsx)": "📥 Download BoQ and drawings (Excel .xlsx)",

    "Език на документа:": "Document language:",
    "Езикът, на който се генерира файлът (екранът не се сменя).":
        "The language the file is generated in (the screen does not change).",

    # Таб 3
    "3. Генериране на PDF чертежи и спецификации": "3. PDF drawings and specifications",
    "ℹ️ Въведете елементи в Таб 1, за да генерирате чертежи.": "ℹ️ Enter elements in Tab 1 to generate drawings.",
    # различен от „Име на обект:“ в таб 4 - еднакъв надпис и стойност дават грешка в Streamlit
    "Наименование на обекта:": "Project / site name:",
    "Име на клиент / инвеститор:": "Client / investor name:",
    "📄 Генерирай PDF Чертежи на обект": "📄 Generate the site PDF drawings",
    "Генериране на векторни чертежи и PDF документ...": "Generating vector drawings and the PDF document...",
    "✅ PDF чертежите бяха генерирани успешно!": "✅ The PDF drawings were generated successfully!",
    "📥 Изтегли пълен PDF с чертежи и спецификации": "📥 Download the full PDF with drawings and specifications",

    # Таб 4
    "4. Търговска оферта": "4. Commercial offer",
    "ℹ️ Въведете елементи в Таб 1, за да генерирате оферта.": "ℹ️ Enter elements in Tab 1 to generate an offer.",
    "Клиент / Инвеститор:": "Client / Investor:",
    "Име на обект:": "Site name:",
    "Дата на офертата:": "Offer date:",
    "Тип на офертата:": "Offer type:",
    "Наем на кофраж (€/m² за месец)": "Formwork rental (€/m² per month)",
    "Покупка на нов кофраж (€/m²)": "Purchase of new formwork (€/m²)",
    "Цена на m² (€):": "Price per m² (€):",
    "📄 Създай Word оферта": "📄 Create Word offer",
    "✅ Търговската оферта беше генерирана успешно в Word формат!":
        "✅ The commercial offer was generated in Word format!",
    "📥 Изтегли оферта (Word .docx)": "📥 Download offer (Word .docx)",

    # Таб 5
    "5. Складова наличност": "5. Stock",
    "Архивът в Google не е достъпен ({error}). Наличността се пази само докато страницата е отворена.":
        "The Google archive is not available ({error}). The stock is kept only while the page is open.",
    "Имената, мярката и наличността се редактират в таблицата; ред се добавя с „+“ под таблицата, изтрива се с "
    "отметка вляво и кошчето. „💾 Запази наличността“ записва в Google (общо за всички проекти) и обновява "
    "предупрежденията в табовете. Промяна от друг компютър се вижда след F5.":
        "Names, units and quantities are edited in the table; add a row with “+” below the table, delete it with "
        "the checkbox on the left and the bin. “💾 Save stock” saves to Google (shared by all projects) and "
        "updates the warnings in the tabs. A change from another computer is shown after F5.",
    " Последна промяна: {date}.": " Last modified: {date}.",
    "Имената, мярката и наличността се редактират в таблицата; ред се добавя с „+“ под таблицата, изтрива се с "
    "отметка вляво и кошчето. „💾 Запази наличността“ обновява предупрежденията в табовете. Без архив (няма ключ "
    "за Google в secrets) наличността се губи при презареждане.":
        "Names, units and quantities are edited in the table; add a row with “+” below the table, delete it with "
        "the checkbox on the left and the bin. “💾 Save stock” updates the warnings in the tabs. Without an "
        "archive (no Google key in secrets) the stock is lost when the page is reloaded.",
    "Мярка": "Unit",
    "Остава": "In stock",
    "💾 Запази наличността": "💾 Save stock",
    "📤 Изтегли като Excel": "📤 Download as Excel",
    "Записаната наличност (без незаписаните промени в таблицата), подредена като „1. Наличности.xlsx“.":
        "The saved stock (without unsaved changes in the table), laid out like “1. Наличности.xlsx”.",
    "Excel с наличност (подреден като „1. Наличности.xlsx“ - колони Елемент, Мярка, Остава):":
        "Excel with stock (laid out like “1. Наличности.xlsx” - columns Елемент, Мярка, Остава):",
    "📥 Зареди от Excel": "📥 Load from Excel",
    "Заменя цялата таблица с тази от файла и я записва.": "Replaces the whole table with the one in the file and saves it.",
    "Файлът не може да се прочете: {error}": "The file cannot be read: {error}",
    "Във файла няма редове под „Елемент“.": "The file has no rows under “Елемент”.",
    "✅ Заредени {n} реда от Excel.": "✅ Loaded {n} rows from Excel.",
}

# Инструкцията за ръчно въвеждане (таб 1)
MANUAL_HELP_BG = (
    "📝 **Инструкция за попълване в таблицата по-долу:**\n"
    "- Изберете **тип елемент**: Колона, Права стена, L-стена, П-стена или T-стена.\n"
    "- Всички размери (стени, дебелини, височина) са в **сантиметри**.\n"
    "- За **права стена**: попълнете **Стена A** (дължината) и **Дебелина стена A**.\n"
    "- За **колона**: попълнете **Стена A** и **Дебелина стена A** - колона 50x30: стена A 50 (страна A на чертежа), дебелина 30 (страна B).\n"
    "- За **L-стена**: попълнете **Стена A**, **Стена B** и **Дебелина стена A**.\n"
    "- За **П-стена**: попълнете **Стена A**, **Стена B**, **Стена C** и **Дебелина стена A**.\n"
    "- За **T-стена**: **Стена A** (цялата полка), **Стена B** (реброто, от полката до края му) и **Дебелина стена A**. **Стена C** - мястото на реброто: от левия край на полката до лявото лице на реброто; празно = реброто е в средата на полката. Реброто може да е и до самия край - остава Т-стена. Край 1 е десният край на полката, край 2 - левият, **Затворен край 3** - краят на реброто (само за T-стена).\n"
    "- **Дебелина стена A** е дебелината на целия елемент. **Дебелина стена B / C** (L-, П- и T-стена) се попълва само когато стената е с различна дебелина; празното поле = като стена A (равна на A се изчиства). При T-стена стена A е полката, стена B - реброто.\n"
    "- **Затворен край 1 / Затворен край 2** (отметки) за стени, L- и П-стени: челните краища, затворени с панел колкото дебелината. Край 1 е краят на стена A (при права стена - десният), край 2 - краят на последната стена (при права стена - левият). **Всички краища са затворени по подразбиране** - за отворен край махнете отметката.\n"
    "- Непотребните полета за съответния тип могат да се оставят празни — системата автоматично игнорира празни клетки без грешки!"
)
EN[MANUAL_HELP_BG] = (
    "📝 **How to fill in the table below:**\n"
    "- Choose the **element type**: Column, Straight wall, L-wall, U-wall or T-wall.\n"
    "- All dimensions (walls, thicknesses, height) are in **centimetres**.\n"
    "- **Straight wall**: fill in **Wall A** (the length) and **Wall A thickness**.\n"
    "- **Column**: fill in **Wall A** and **Wall A thickness** - column 50x30: wall A 50 (side A on the drawing), thickness 30 (side B).\n"
    "- **L-wall**: fill in **Wall A**, **Wall B** and **Wall A thickness**.\n"
    "- **U-wall**: fill in **Wall A**, **Wall B**, **Wall C** and **Wall A thickness**.\n"
    "- **T-wall**: **Wall A** (the whole flange), **Wall B** (the stem, from the flange to its end) and **Wall A thickness**. **Wall C** - the stem position: from the left end of the flange to the left face of the stem; empty = the stem is in the middle of the flange. The stem may be right at the end - it is still a T-wall. End 1 is the right end of the flange, end 2 - the left one, **Closed end 3** - the end of the stem (T-wall only).\n"
    "- **Wall A thickness** is the thickness of the whole element. **Wall B / C thickness** (L-, U- and T-wall) is filled in only when that wall has a different thickness; an empty field = same as wall A (equal to A is cleared). For a T-wall, wall A is the flange and wall B is the stem.\n"
    "- **Closed end 1 / Closed end 2** (checkboxes) for walls, L- and U-walls: the ends closed with a panel as wide as the thickness. End 1 is the end of wall A (straight wall - the right one), end 2 - the end of the last wall (straight wall - the left one). **All ends are closed by default** - untick for an open end.\n"
    "- Fields not needed for the type can be left empty — empty cells are ignored without errors!"
)
