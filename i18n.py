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
_ITEM_WORDS = [("Вътрешен ъгъл", "Internal corner"), ("Външен ъгъл", "External corner"), ("Ръкохватка", "Handle"),
               ("Ригел", "Alignment waling"), ("Вертикализатор", "Pull push prop"), ("Шпилка", "Tie rod"),
               ("Гайка", "Nut"),
               ("Компенсатор", "Compensator"), ("(полегнал)", "(horizontal)"), ("вътре ", "inside "), (" см", " cm"),
               ("бр.", "pcs")]


def t_item(text):
    """Име на артикул или размери от сметката на избрания език („Ригел AW 200“ -> „Alignment waling AW 200“)."""
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
    "🔒 Вход в системата TEKO": "🔒 Sign in to TEKO",
    "🔑 Въведете парола за достъп:": "🔑 Enter the access password:",
    "Вход": "Sign in",
    "❌ Грешна парола! Опитайте отново.": "❌ Wrong password! Please try again.",
    "Запомни този компютър ({d} дни)": "Remember this computer ({d} days)",
    "Следващия път влизате направо, без парола. Не отмятайте на чужд компютър. Изход - с бутона „🚪 Изход“ в "
    "страничното меню; при смяна на паролата всички запомнени компютри се изписват сами.":
        "Next time you go straight in, without a password. Do not tick it on someone else's computer. Sign out "
        "with the “🚪 Sign out” button in the sidebar; changing the password signs out all remembered computers.",
    "🚪 Изход": "🚪 Sign out",
    "💶 Цени в Excel: {n} артикула": "💶 Prices in Excel: {n} items",
    " (заредени на {d})": " (loaded on {d})",
    "💶 Няма заредени цени - колоната „Ед. Цена“ в Excel е празна (попълва се на ръка).":
        "💶 No prices loaded - the “Unit price” column in Excel is empty (filled in by hand).",
    "⚠️ Цените не са записани в архива: {error}": "⚠️ The prices were not saved to the archive: {error}",
    "💶 Цени от Excel": "💶 Prices from Excel",
    "Excel с цени („1. Оферта – софтуер.xlsx“ - колони Елемент и Ед. Цена):":
        "Excel with prices (“1. Оферта – софтуер.xlsx” - columns Item and Unit price):",
    "📥 Зареди цените": "📥 Load the prices",
    "Заменя всички цени с тези от файла и ги записва - важат за всички проекти.":
        "Replaces all prices with those from the file and saves them - they apply to all projects.",
    "Във файла няма цени под „Ед. Цена“.": "The file has no prices under “Unit price”.",
    "✅ Заредени {n} цени от Excel. Създайте Excel наново.": "✅ Loaded {n} prices from Excel. Create the Excel again.",
    "Изход от приложението; ако компютърът е запомнен - забравя го.":
        "Sign out of the app; if this computer is remembered, it is forgotten.",
    "ТЕКО Система за кофражно планиране": "TEKO formwork planning system",
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
    "🏗️ 3D план на етажа": "🏗️ 3D Floor Plan",

    # Таб 6 - 3D план на етажа (22.11.2026)
    "6. 3D план на етажа": "6. 3D floor plan",
    "Чертеж (етаж):": "Drawing (floor):",
    "🖼️ Чертежът като фон": "🖼️ The drawing as a background",
    "Друг файл за фон (PDF или картина) - само ако не е разчетеният в таб 1:":
        "Another file for the background (PDF or image) - only if it is not the one read in tab 1:",
    "Фонът е чертежът от таб 1: „{name}“.": "The background is the drawing from tab 1: “{name}”.",
    "Файлът на „{name}“ не е зареден (пази се само докато страницата е отворена) - качете го тук или в таб 1.":
        "The file of “{name}” is not loaded (it is kept only while the page is open) - upload it here or in tab 1.",
    "Чертеж (PDF или картина):": "Drawing (PDF or image):",
    "Страница:": "Page:",
    "Мащаб на чертежа 1:": "Drawing scale 1:",
    "Мащабът, в който е начертан листът (напр. 1:50). Сканиран лист може да е с друг размер - тогава задайте "
    "мащаба по кота.": "The scale of the sheet (e.g. 1:50). A scanned sheet may have a different size - then set "
                       "the scale by a dimension.",
    "Известна кота (см):": "Known dimension (cm):",
    "За „📏 Мащаб по кота“: кликнете двата края на тази кота върху чертежа.":
        "For “📏 Scale by dimension”: click both ends of this dimension on the drawing.",
    "Видимост на фона": "Background visibility",
    "🙈 Скрий фона": "🙈 Hide the background",
    "🖼️ Покажи фона": "🖼️ Show the background",
    "Фонът в PDF-а (бледо, под елементите)": "The background in the PDF (faint, under the elements)",
    "Ако елементите не съвпадат по размер с чертежа, натиснете „📏 Мащаб по кота“ в лентата над плана и кликнете "
    "двата края на известна кота.":
        "If the elements do not match the drawing in size, press “📏 Scale by dimension” in the bar above the plan "
        "and click both ends of a known dimension.",
    "Влачете елементите с мишката до мястото им (приблизително е достатъчно). Клик върху елемент го избира: "
    "кръгчето над него го върти под всякакъв ъгъл (през 5°, със Shift - през 1°), „Ъгъл“ - точен ъгъл, "
    "„↺ 90°“ / „↻ 90°“ (или клавиш R) - на 90°, „⇋ Огледално“ (или M) го обръща. Колелцето приближава, влачене на "
    "празно място мести изгледа. Местата се пазят, докато страницата е отворена (не се записват в архива).":
        "Drag the elements with the mouse to their place (approximately is enough). A click on an element selects "
        "it: the circle above it rotates it to any angle (in 5° steps, with Shift - 1°), “Angle” - an exact angle, "
        "“↺ 90°” / “↻ 90°” (or the R key) - by 90°, “⇋ Mirror” (or M) flips it. The mouse wheel zooms, dragging an "
        "empty spot moves the view. The positions are kept while the page is open (they are not saved in the "
        "archive).",
    "↺ 90°": "↺ 90°",
    "↻ 90°": "↻ 90°",
    "Ъгъл:": "Angle:",
    "⇋ Огледално": "⇋ Mirror",
    "⤢ Целият план": "⤢ Whole plan",
    "📏 Мащаб по кота": "📏 Scale by dimension",
    "Кликнете в единия край на известната кота.": "Click one end of the known dimension.",
    "Кликнете в другия край на котата.": "Click the other end of the dimension.",
    "Влачете елементите; клик върху елемент го избира.": "Drag the elements; a click on an element selects it.",
    "Избран: {name} - кръгчето го върти.": "Selected: {name} - the circle rotates it.",
    "✅ Таблица 1 е обновена и проектът е записан.": "✅ Table 1 is updated and the project is saved.",
    "„➕ Нов елемент“ (вдясно от плана) и „✏️ Размери“ на избрания елемент (или двоен клик върху него) отварят "
    "прозорец с полетата. В лентата: „⧉ Копирай“ (Ctrl+C) и „📋 Постави“ (Ctrl+V - там, където е мишката) - още "
    "един брой, „🗑 Изтрий“ (Delete). Промените отиват направо в таблица 1 и се записват - незаписаните промени в "
    "таблица 1 се губят.":
        "“➕ New element” (to the right of the plan) and “✏️ Dimensions” of the selected element (or a double click "
        "on it) open a window with the fields. In the bar: “⧉ Copy” (Ctrl+C) and “📋 Paste” (Ctrl+V - where the mouse "
        "is) - one more piece, “🗑 Delete” (Delete). The changes go straight into table 1 and are saved - unsaved "
        "changes in table 1 are lost.",
    "✏️ Размери на елемента": "✏️ Element dimensions",
    "✏️ Размери": "✏️ Dimensions",
    "🗑 Изтриване": "🗑 Deleting",
    "Името и размерите на избрания елемент (или двоен клик върху него).":
        "The name and the dimensions of the selected element (or a double click on it).",
    "Избран: {name}": "Selected: {name}",
    "Кликнете елемент в плана, за да го изберете.": "Click an element in the plan to select it.",
    "ℹ️ Няма елементи - добавете ги с „➕ Нов елемент“ вдясно от плана или в таблица 1.":
        "ℹ️ No elements - add them with “➕ New element” to the right of the plan or in table 1.",
    "➕ Нов елемент": "➕ New element",
    "⧉ Копирай": "⧉ Copy",
    "📋 Постави": "📋 Paste",
    "Копиран: {name} - Ctrl+V го поставя там, където е мишката.":
        "Copied: {name} - Ctrl+V pastes it where the mouse is.",
    "Да се изтрие ли „{name}“? Бройката в таблица 1 намалява с 1 (при 1 бр. редът се маха).":
        "Delete “{name}”? The quantity in table 1 goes down by 1 (at 1 pc. the row is removed).",
    "🗑 Да, изтрий": "🗑 Yes, delete",
    "📍 Постави под чертежа": "📍 Place below the drawing",
    "Попълнете: {missing}.": "Fill in: {missing}.",
    "Важи за всички {n} бр. от реда": "Applies to all {n} pcs. of the row",
    "Без отметка - само този брой: той става нов ред в таблицата.":
        "Unticked - only this piece: it becomes a new row in the table.",
    "💾 Запази промените": "💾 Save the changes",
    "Празно = стандартната височина на проекта": "Empty = the standard height of the project",
    "Празна = като стена A": "Empty = as wall A",
    "↺ Подреди наново": "↺ Arrange again",
    "Връща елементите на местата им по чертежа, другите - един до друг под него (преместеното с мишката се губи).":
        "Puts the elements back in their places on the drawing, the others side by side below it (what was moved "
        "with the mouse is lost).",
    "📍 Постави елементите по чертежа": "📍 Place the elements by the drawing",
    "Местата от разчитането с Gemini (приблизително) и от контурите на бетона във векторен PDF (точно). "
    "Елементите, преместени с мишката, остават, където са.":
        "The places from the Gemini reading (approximate) and from the concrete outlines in a vector PDF (exact). "
        "Elements moved with the mouse stay where they are.",
    "📏 Мащабът е определен по елементите на чертежа: 1:{n}.": "📏 The scale was found from the drawing's elements: 1:{n}.",
    "📏 Мащабът е определен по елементите на чертежа.": "📏 The scale was found from the drawing's elements.",
    "📍 По чертежа: {n} от {total} елемента ({pdf} по контура в PDF-а, {gemini} по Gemini - приблизително). "
    "Другите са под чертежа - влачете ги до мястото им.":
        "📍 By the drawing: {n} of {total} elements ({pdf} by the outline in the PDF, {gemini} by Gemini - "
        "approximate). The others are below the drawing - drag them to their place.",
    "📍 Местата на елементите не са намерени в чертежа (няма места от разчитането и контури в PDF-а до имената им) "
    "- влачете ги с мишката.":
        "📍 The places of the elements were not found in the drawing (no places from the reading and no outlines in "
        "the PDF next to their names) - drag them with the mouse.",
    "📄 Генерирай 3D PDF": "📄 Generate 3D PDF",
    "Чертане на 3D плана...": "Drawing the 3D plan...",
    "📥 Изтегли 3D плана (PDF)": "📥 Download the 3D plan (PDF)",

    # Таб 1
    "1. Избор на начин за въвеждане на елементи": "1. How to enter the elements",
    "Изберете режим на работа:": "Choose the working mode:",
    "🤖 Автоматично разчитане от чертежи": "🤖 Automatic reading from drawings",
    "⌨️ Ръчно въвеждане (Таблица)": "⌨️ Manual entry (Table)",
    "Качване на чертеж и AI разчитане": "Upload a drawing and AI reading",
    "Чертеж „{name}“ вече е разчетен в този проект:": "Drawing “{name}” has already been read in this project:",
    "Замени елементите му": "Replace its elements",
    "Добави като нов чертеж": "Add as a new drawing",
    "Елементите ще се добавят като Чертеж {n} под вече разчетените.":
        "The elements will be added as Drawing {n} below the ones already read.",
    "Чертеж „{name}“: {n} елемента - записани в проекта.": "Drawing “{name}”: {n} elements - saved in the project.",
    "📄 Чертеж {i}: {name}": "📄 Drawing {i}: {name}",
    "⚠️ Забележки на AI - Чертеж {i}: {name}": "⚠️ AI notes - Drawing {i}: {name}",
    "📍 Откъде е всеки елемент - Чертеж {i}: {name} ({n})": "📍 Where each element is from - Drawing {i}: {name} ({n})",
    "Изпратен като PDF (с текста в него).": "Sent as a PDF (with its text).",
    "Изпратен като изображения на страниците.": "Sent as page images.",
    "Качен през File API (голям файл) и изтрит след разчитането.":
        "Uploaded via the File API (large file) and deleted after reading.",
    "Как да се разчете чертежът:": "How to read the drawing:",
    "Автоматично": "Automatic",
    "Като текст (PDF)": "As text (PDF)",
    "Като картина": "As an image",
    "Автоматично: плотиран PDF (с текст вътре) - като PDF, кóтите се четат от текста; сканиран или принтиран PDF "
    "(без текст) - като картини на страниците. Изберете на ръка, ако автоматичният избор не е подходящ (напр. "
    "кóтите са линии, а не текст).":
        "Automatic: a plotted PDF (with text inside) is sent as a PDF and the dimensions are read from the text; a "
        "scanned or printed PDF (no text) is sent as page images. Choose manually if the automatic choice does not "
        "fit (e.g. the dimensions are lines, not text).",
    "🔁 Двойна проверка (разчита чертежа два пъти и сравнява)": "🔁 Double check (reads the drawing twice and compares)",
    "Разликите между двете разчитания излизат в забележките на AI - там проверете таблицата. Отнема двойно време и "
    "изразходва двойно от безплатното ограничение на ключа.":
        "The differences between the two readings appear in the AI notes - check the table there. Takes twice as "
        "long and uses twice as much of the key's free quota.",
    "да": "yes",
    "не": "no",
    "Затворен край 3": "Closed end 3",
    "🔁 Двойна проверка: двете разчитания съвпадат.": "🔁 Double check: both readings match.",
    "🔁 Двойната проверка не мина: {error}": "🔁 The double check failed: {error}",
    "🔁 Двойна проверка: {name} е само в първото разчитане (в таблицата е) - проверете го.":
        "🔁 Double check: {name} is only in the first reading (it is in the table) - check it.",
    "🔁 Двойна проверка: {name} е само във второто разчитане (не е в таблицата) - проверете чертежа.":
        "🔁 Double check: {name} is only in the second reading (not in the table) - check the drawing.",
    "🔁 Двойна проверка: {name} - {field}: {first} (в таблицата) / {second} (второ разчитане).":
        "🔁 Double check: {name} - {field}: {first} (in the table) / {second} (second reading).",
    # gemini_agent2.TRUNCATED_NOTE - бележките на Gemini са на езика на екрана, а тази я добавя програмата
    "Отговорът на Gemini е отрязан - чертежът е твърде голям. Разделете го на части или опитайте с по-малко "
    "страници.":
        "The Gemini answer was cut off - the drawing is too large. Split it into parts or try with fewer pages.",
    "📄 Без чертеж (въведени ръчно)": "📄 No drawing (entered manually)",
    "{n} елемента": "{n} elements",
    "Към кой чертеж?": "To which drawing?",
    "Чертеж {i}: {name}": "Drawing {i}: {name}",
    "Без чертеж (въведени ръчно)": "No drawing (entered manually)",
    "➕ Нова таблица…": "➕ New table…",
    "Име на новата таблица": "Name of the new table",
    "напр. Етаж 2 - ръчно": "e.g. Floor 2 - manual",
    "Само при „➕ Нова таблица…“ в „Към кой чертеж?“.": "Only with “➕ New table…” in “To which drawing?”.",
    "Напишете име на новата таблица, което го няма в проекта, и натиснете отново „➕ Добави елемент“.":
        "Type a name for the new table that is not in the project yet and press “➕ Add element” again.",
    "📄 Чертежи в проекта ({n}) - преименуване и изтриване": "📄 Drawings in the project ({n}) - rename and delete",
    "Първо натиснете „💾 Запази и Изчисли“ - незаписаните промени в таблиците се губят.":
        "First press “💾 Save and Calculate” - unsaved changes in the tables are lost.",
    "Чертеж {i} ({n} елемента)": "Drawing {i} ({n} elements)",
    "✏️ Преименувай": "✏️ Rename",
    "Името е празно или вече има такъв чертеж.": "The name is empty or such a drawing already exists.",
    "Отказ": "Cancel",
    "Да се изтрият ли {n} елемента на „{name}“?": "Delete the {n} elements of “{name}”?",
    "🗑 Да, изтрий чертежа": "🗑 Yes, delete the drawing",
    "🗑 Да, изтрий таблицата": "🗑 Yes, delete the table",
    "Без чертеж ({n} елемента)": "No drawing ({n} elements)",
    "🗑 Изтрий": "🗑 Delete",
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
    "П-стена; при Т-стена - полката вляво от реброто (дължината „Стена C“); празна = като стена A "
    "(попълва се само когато е различна)":
        "U-wall; for a T-wall - the flange left of the stem (the “Wall C” length); empty = same as wall A "
        "(fill in only when different)",
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
    "Шахта": "Shaft",
    "Празна = квадратна шахта (B = A)": "Empty = square shaft (B = A)",
    "• **{name}**: При шахта не се ползват {fields} - дебелината е „Дебелина стена A“ за четирите стени, празна Стена B = квадратна шахта.":
        "• **{name}**: {fields} are not used for a shaft - the thickness is “Wall A thickness” for all four walls, an empty Wall B = square shaft.",

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
    "Дебелина стена B": "Wall B thickness",
    "Дебелина стена C": "Wall C thickness",
    "• **{name}**: {label} {value} cm е необичайна (обикновено 10-100 cm) - проверете размера.":
        "• **{name}**: {label} {value} cm is unusual (normally 10-100 cm) - check the dimension.",
    "• **{name}**: Височина {h} cm е необичайна (обикновено 20-1200 cm) - проверете размера.":
        "• **{name}**: Height {h} cm is unusual (normally 20-1200 cm) - check the dimension.",
    "• **{name}**: Дължината ({l} cm) е по-малка от дебелината ({t} cm) - разменени ли са?":
        "• **{name}**: The length ({l} cm) is less than the thickness ({t} cm) - are they swapped?",
    "• **{name}**: {label} ({l} cm) е твърде къса - до ъглите са нужни {k} cm и поне 5 cm панел. Проверете "
    "размерите.":
        "• **{name}**: {label} ({l} cm) is too short - the corners need {k} cm plus at least a 5 cm panel. "
        "Check the dimensions.",

    # Склад - предупреждения
    "⚠️ Не стигат в склада (таб „Складова наличност“):": "⚠️ Not enough in stock (tab “Stock”):",
    "- **{k}**: нужни {q} бр., на склад {a} бр. (не стигат {d} бр.)":
        "- **{k}**: needed {q} pcs, in stock {a} pcs (short by {d} pcs)",
    "⚠️ Няма ги в складовата наличност:": "⚠️ Not in the stock list:",
    "- **{k}**: нужни {q} бр.": "- **{k}**: needed {q} pcs",

    # Редене според складовата наличност
    "📦 Редене според складовата наличност": "📦 Layout by available stock",
    "Панелите се редят по алгоритъма. Когато някой панел не стига в склада (таб „Складова "
    "наличност“), той се заменя с най-малко по-малки налични панели в същия ред, а ако не може - "
    "елементът се пренарежда по височина (напр. 300 = 120 + 120 + 60). Най-големите елементи "
    "вземат от склада първи. Отметката се пази в проекта.":
        "Panels are laid out by the algorithm. When a panel is short in stock (tab “Stock”), it is replaced "
        "with the fewest smaller panels in stock in the same row; if that is not possible, the element is "
        "re-laid by height (e.g. 300 = 120 + 120 + 60). The largest elements take from stock first. "
        "The checkbox is saved with the project.",
    "ℹ️ Редене според складовата наличност: няма въведена наличност - панелите са по алгоритъма.":
        "ℹ️ Layout by available stock: no stock quantities entered - panels follow the algorithm.",
    "- **{e}**: пренареден по височина - {levels} см": "- **{e}**: re-laid by height - {levels} cm",
    "- **{e}**: {old} → {new} ({n} места)": "- **{e}**: {old} → {new} ({n} places)",
    "🔁 Редене според складовата наличност - сменени панели:": "🔁 Layout by available stock - replaced panels:",
    "✅ Редене според складовата наличност: всички панели по алгоритъма са налични.":
        "✅ Layout by available stock: all panels of the algorithm layout are in stock.",

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
        "Sheet “Bill of quantities” - the items in offer order; a sheet for each element - top and front view made of "
        "cells (1 cell = 5 cm) for editing; a sheet with all panels for copying. The file is in the document language "
        "chosen below.",
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
    "предупрежденията в табовете; предишната наличност остава в лист „Наличност - история“. Промяна от друг "
    "компютър - с „🔄 Обнови от архива“.":
        "Names, units and quantities are edited in the table; add a row with “+” below the table, delete it with "
        "the checkbox on the left and the bin. “💾 Save stock” saves to Google (shared by all projects) and "
        "updates the warnings in the tabs; the previous stock is kept in the sheet “Наличност - история”. A change "
        "from another computer - with “🔄 Reload from archive”.",
    "Последна промяна на наличността: **{date}**": "Stock last modified: **{date}**",
    "Наличността още не е записана в архива.": "The stock has not been saved to the archive yet.",
    "🔄 Обнови от архива": "🔄 Reload from archive",
    "Зарежда наличността наново от Google (промените от други компютри) - без F5. Незаписаните промени в "
    "таблицата се губят.":
        "Loads the stock again from Google (changes from other computers) - without F5. Unsaved changes in the "
        "table are lost.",
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
    "Записаната наличност (без незаписаните промени в таблицата) и нужното за проекта, подредени като "
    "„1. Оферта – софтуер.xlsx“.":
        "The saved stock (without unsaved changes in the table) and the project needs, laid out like "
        "“1. Оферта – софтуер.xlsx”.",
    "Excel с наличност („1. Оферта – софтуер.xlsx“ или „1. Наличности.xlsx“ - колони Елемент, Мярка, Наличност в "
    "склада):":
        "Excel with stock (“1. Оферта – софтуер.xlsx” or “1. Наличности.xlsx” - columns Елемент, Мярка, Наличност "
        "в склада):",
    "Наличност в склада": "Stock in warehouse",
    "Нужно за проекта": "Needed for the project",
    "Остават": "Remaining",
    "📥 Зареди от Excel": "📥 Load from Excel",
    "Заменя цялата таблица с тази от файла и я записва.": "Replaces the whole table with the one in the file and saves it.",
    "Файлът не може да се прочете: {error}": "The file cannot be read: {error}",
    "Във файла няма редове под „Елемент“.": "The file has no rows under “Елемент”.",
    "✅ Заредени {n} реда от Excel.": "✅ Loaded {n} rows from Excel.",
}

# Инструкцията за ръчно въвеждане (таб 1)
MANUAL_HELP_BG = (
    "📝 **Инструкция за попълване в таблицата по-долу:**\n"
    "- Изберете **тип елемент**: Колона, Права стена, L-стена, П-стена, T-стена или Шахта.\n"
    "- Всички размери (стени, дебелини, височина) са в **сантиметри**.\n"
    "- За **права стена**: попълнете **Стена A** (дължината) и **Дебелина стена A**.\n"
    "- За **колона**: попълнете **Стена A** и **Дебелина стена A** - колона 50x30: стена A 50 (страна A на чертежа), дебелина 30 (страна B).\n"
    "- За **L-стена**: попълнете **Стена A**, **Стена B** и **Дебелина стена A**.\n"
    "- За **П-стена**: попълнете **Стена A**, **Стена B**, **Стена C** и **Дебелина стена A**.\n"
    "- За **T-стена**: **Стена A** (цялата полка), **Стена B** (реброто, от полката до края му) и **Дебелина стена A**. **Стена C** - мястото на реброто: от левия край на полката до лявото лице на реброто; празно = реброто е в средата на полката. Реброто може да е и до самия край - остава Т-стена. Край 1 е десният край на полката, край 2 - левият, **Затворен край 3** - краят на реброто (само за T-стена).\n"
    "- За **шахта** (затворен правоъгълник от 4 стени): **Стена A** и **Стена B** - външните размери (празна Стена B = квадратна шахта), **Дебелина стена A** - една за четирите стени. Затворени краища няма; вертикализаторите са само отвън.\n"
    "- **Дебелина стена A** е дебелината на целия елемент. **Дебелина стена B / C** (L-, П- и T-стена) се попълва само когато стената е с различна дебелина; празното поле = като стена A (равна на A се изчиства). При T-стена стена A е полката, стена B - реброто, а стена C - полката вляво от реброто (дължината „Стена C“; празна = цялата полка е с дебелина A).\n"
    "- **Затворен край 1 / Затворен край 2** (отметки) за стени, L- и П-стени: челните краища, затворени с панел колкото дебелината. Край 1 е краят на стена A (при права стена - десният), край 2 - краят на последната стена (при права стена - левият). **Всички краища са затворени по подразбиране** - за отворен край махнете отметката.\n"
    "- Непотребните полета за съответния тип могат да се оставят празни — системата автоматично игнорира празни клетки без грешки!"
)
EN[MANUAL_HELP_BG] = (
    "📝 **How to fill in the table below:**\n"
    "- Choose the **element type**: Column, Straight wall, L-wall, U-wall, T-wall or Shaft.\n"
    "- All dimensions (walls, thicknesses, height) are in **centimetres**.\n"
    "- **Straight wall**: fill in **Wall A** (the length) and **Wall A thickness**.\n"
    "- **Column**: fill in **Wall A** and **Wall A thickness** - column 50x30: wall A 50 (side A on the drawing), thickness 30 (side B).\n"
    "- **L-wall**: fill in **Wall A**, **Wall B** and **Wall A thickness**.\n"
    "- **U-wall**: fill in **Wall A**, **Wall B**, **Wall C** and **Wall A thickness**.\n"
    "- **T-wall**: **Wall A** (the whole flange), **Wall B** (the stem, from the flange to its end) and **Wall A thickness**. **Wall C** - the stem position: from the left end of the flange to the left face of the stem; empty = the stem is in the middle of the flange. The stem may be right at the end - it is still a T-wall. End 1 is the right end of the flange, end 2 - the left one, **Closed end 3** - the end of the stem (T-wall only).\n"
    "- **Shaft** (a closed rectangle of 4 walls): **Wall A** and **Wall B** - the outer dimensions (empty Wall B = square shaft), **Wall A thickness** - one for all four walls. There are no closed ends; the push-pull props are outside only.\n"
    "- **Wall A thickness** is the thickness of the whole element. **Wall B / C thickness** (L-, U- and T-wall) is filled in only when that wall has a different thickness; an empty field = same as wall A (equal to A is cleared). For a T-wall, wall A is the flange, wall B is the stem and wall C is the flange left of the stem (the “Wall C” length; empty = the whole flange has the wall A thickness).\n"
    "- **Closed end 1 / Closed end 2** (checkboxes) for walls, L- and U-walls: the ends closed with a panel as wide as the thickness. End 1 is the end of wall A (straight wall - the right one), end 2 - the end of the last wall (straight wall - the left one). **All ends are closed by default** - untick for an open end.\n"
    "- Fields not needed for the type can be left empty — empty cells are ignored without errors!"
)
