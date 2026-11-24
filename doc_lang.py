"""
Език на генерираните файлове - PDF чертежи, Word оферта, Excel (КСС и чертежи, складова наличност)
(потребителят, 17.11.2026). Езикът се избира от падащо меню до бутона на всеки файл; по подразбиране - български.

    with document_language("de"):
        pdf = generate_pdf_drawings(...)

dt("текст на български", **стойности) - текстът на езика на документа (ключът е българският текст; без превод -
българският). dt_item() - имената на артикулите от сметката („Ръкохватка H8“ -> „Griff H8“), dt_face() - имената
на страните („A1 ляво“). Езикът е в ContextVar - всяка сесия (нишка) на Streamlit има свой.
Кипърски = гръцки (в Кипър документите са на стандартен гръцки). Ирландски (Gaeilge) няма - в Ирландия
документите са на английски (потребителят, 19.11.2026). Сръбският е на кирилица.
Термините на артикулите - както в сайта на TEKO, където ги има (en, el, ro), иначе - както в строителните каталози.
"""
import contextvars
import re
from contextlib import contextmanager

DOC_LANGUAGES = {
    "bg": "Български", "en": "English", "de": "Deutsch", "fr": "Français", "es": "Español", "el": "Ελληνικά",
    "hr": "Hrvatski", "ro": "Română", "pl": "Polski", "uk": "Українська", "ru": "Русский",
    "sr": "Српски", "tr": "Türkçe",
}
# Флагчетата в падащите менюта (на Windows - с шрифта „Twemoji Country Flags“, виж FLAG_FONT_CSS в app.py)
DOC_FLAGS = {"bg": "🇧🇬", "en": "🇬🇧", "de": "🇩🇪", "fr": "🇫🇷", "es": "🇪🇸", "el": "🇬🇷", "hr": "🇭🇷", "ro": "🇷🇴",
             "pl": "🇵🇱", "uk": "🇺🇦", "ru": "🇷🇺", "sr": "🇷🇸", "tr": "🇹🇷"}
# редът на преводите в TR и TERMS
_ORDER = ("en", "de", "fr", "es", "el", "hr", "ro", "pl", "uk", "ru", "sr", "tr")

_current = contextvars.ContextVar("document_language", default="bg")


@contextmanager
def document_language(lang):
    """Всичко, генерирано вътре в блока, е на езика lang (непознат - български)."""
    token = _current.set(lang if lang in DOC_LANGUAGES else "bg")
    try:
        yield
    finally:
        _current.reset(token)


def doc_lang():
    return _current.get()


def dt(text, **values):
    """Текстът на езика на документа; стойностите се вмъкват с {име}."""
    lang = _current.get()
    if lang != "bg" and text in TR:
        text = TR[text][_ORDER.index(lang)]
    return text.format(**values) if values else text


def dt_cm(unit):
    """Мерната единица от параметъра unit (" см", " cm", "") на езика на документа."""
    return " " + dt("см") if unit.strip() == "см" else unit


def dt_item(text):
    """Име на артикул от сметката на езика на документа: „Подравняващ ригел AW 100 поцинковани“ -> ..."""
    text = str(text)
    lang = _current.get()
    if lang == "bg":
        return text
    i = _ORDER.index(lang)
    # на един проход - преведената дума не се превежда пак („ригель“ съдържа „ригел“)
    text = _TERMS_RE.sub(lambda m: TERMS[int(m.lastgroup[1:])][1][i], text)
    text = text.replace("EС240", "EC240")   # в КСС кодът е с кирилско „С“
    return " ".join(text.split())


def dt_face(name):
    """Име на страна („A1 ляво“, „A1 дясно“, „Край 1“) на езика на документа."""
    return " ".join(dt(w) if w in ("ляво", "дясно", "Край") else w for w in str(name).split())


# Думите в имената на артикулите (по реда на проверка): en, de, fr, es, el, hr, ro, pl, uk, ru, sr, tr
TERMS = [
    # el - „Οδηγός στερέωσης“ (AW), „Μεταλλικός σύνδεσμος ξυλοτύπου“ (TC), „Υποστήριγμα στοιχείων“ (PP) - както в
    # сайта на TEKO Гърция; ro - „Contrafișă reglabilă“ - TEKO Румъния; en / ro „Compensator“ - както при TEKO;
    # hr ригел „Stezna vodilica“ - като Doka Хърватия, tr подравняващ ригел „Kuşak“, pl „Podpora pionująca“,
    # es „Riel alineador“ (потребителят, 24.11.2026 - след проверката с търсене в изображения)
    (r"Подравняващ\s+ригел", ("Alignment waling", "Richtriegel", "Filière d'alignement", "Riel de alineación",
                              "Οδηγός στερέωσης", "Stezna vodilica", "Șină de rigidizare", "Rygiel wyrównujący",
                              "Вирівнювальний ригель", "Выравнивающий ригель", "Ригла за поравнање",
                              "Kuşak")),
    (r"Ригел", ("Alignment waling", "Riegel", "Filière", "Riel alineador", "Οδηγός στερέωσης", "Stezna vodilica",
                "Șină de rigidizare", "Rygiel", "Ригель", "Ригель", "Ригла", "Kuşak")),
    (r"поцинкован[иа]?", ("galvanized", "verzinkt", "galvanisée", "galvanizado", "γαλβανισμένος", "pocinčani",
                          "zincată", "ocynkowany", "оцинкований", "оцинкованный", "поцинкована",
                          "galvanizli")),
    (r"Външен\s+скосен\s+ъгъл", ("External chamfered corner", "Abgeschrägte Außenecke", "Angle extérieur chanfreiné",
                                 "Esquina exterior achaflanada", "Εξωτερική γωνία με φάλτσο", "Skošeni vanjski kut",
                                 "Colț exterior teșit", "Narożnik zewnętrzny ścięty", "Скошений зовнішній кут",
                                 "Скошенный внешний угол", "Закошени спољашњи угао", "Pahlı dış köşe")),
    (r"Вътрешен\s+ъгъл", ("Internal corner", "Innenecke", "Angle intérieur", "Esquina interior", "Εσωτερική γωνία",
                          "Unutarnji kut", "Colț interior", "Narożnik wewnętrzny", "Внутрішній кут",
                          "Внутренний угол", "Унутрашњи угао", "İç köşe")),
    (r"Външен\s+ъгъл", ("External corner", "Außenecke", "Angle extérieur", "Esquina exterior", "Εξωτερική γωνία",
                        "Vanjski kut", "Colț exterior", "Narożnik zewnętrzny", "Зовнішній кут", "Внешний угол",
                        "Спољашњи угао", "Dış köşe")),
    # не „Kompansatör“ / „compensateur“ ... - там това е разширителна връзка (маншон) на тръбопровод
    (r"Компенсатор", ("Compensator", "Ausgleichselement", "Pièce de compensation", "Pieza de compensación",
                      "Μεταλλικός σύνδεσμος ξυλοτύπου", "Kompenzacijski element", "Compensator",
                      "Element kompensacyjny", "Компенсатор", "Компенсатор", "Компензациони елемент",
                      "Dolgu elemanı")),
    (r"Панел", ("Panel", "Schalungselement", "Panneau", "Panel", "Πάνελ", "Panel", "Panou", "Panel", "Панель",
                "Панель", "Панел", "Panel")),
    (r"Ръкохватка", ("Handle", "Griff", "Poignée", "Maneta", "Λαβή", "Ručka", "Mâner", "Uchwyt", "Ручка (замок)",
                     "Ручка (замок)", "Ручка", "Tutamak")),
    (r"Вертикализатор", ("Pull push prop", "Richtstütze", "Étai tire-pousse", "Puntal estabilizador",
                         "Υποστήριγμα στοιχείων", "Podupirač", "Contrafișă reglabilă", "Podpora pionująca", "Підкіс",
                         "Подкос", "Подупирач", "Ayarlı payanda")),
    (r"Шпилка", ("Tie rod", "Ankerstab", "Tige d'ancrage", "Barra de anclaje", "Ντίζα", "Sidrena šipka",
                 "Bară tirant", "Ściąg", "Стяжка", "Стяжка", "Затега", "Tij")),
    (r"Гайка", ("Nut", "Ankermutter", "Écrou", "Tuerca", "Περικόχλιο", "Matica", "Piuliță cofraj", "Nakrętka", "Гайка", "Гайка",
                "Навртка", "Somun")),
    (r"Фиксираща\s+планка", ("Fixing plate", "Fixierplatte", "Plaque de fixation", "Placa de fijación",
                              "Πλάκα στερέωσης", "Pričvrsna pločica", "Placă de fixare", "Płytka mocująca",
                              "Фіксувальна планка", "Фиксирующая планка", "Причврсна плочица",
                              "Sabitleme plakası")),
    (r"Съединител\s+за\s+ригел", ("Waling connector", "Riegelverbinder", "Connecteur de filière",
                                    "Conector de riel", "Σύνδεσμος οδηγού στερέωσης", "Spojnica stezne vodilice",
                                    "Conector pentru șina de rigidizare", "Łącznik rygla", "З'єднувач ригеля", "Соединитель ригеля",
                                    "Спојница ригле", "Kuşak bağlantısı")),
    (r"Тапа", ("Plug", "Stopfen", "Bouchon", "Tapón", "Τάπα", "Čep", "Dop", "Zaślepka", "Заглушка", "Заглушка",
               "Чеп", "Tapa")),
    (r"\(полегнал\)", ("(horizontal)", "(liegend)", "(couché)", "(horizontal)", "(οριζόντιο)", "(položen)",
                       "(orizontal)", "(leżący)", "(лежачий)", "(лежачий)", "(положен)", "(yatay)")),
]

# Текстове в документите: български -> (en, de, fr, es, el, hr, ro, pl, uk, ru, sr, tr)
TR = {
    # Мерни единици и думи
    "см": ("cm", "cm", "cm", "cm", "cm", "cm", "cm", "cm", "см", "см", "см", "cm"),
    "бр.": ("pcs", "Stk.", "pcs", "uds.", "τεμ.", "kom.", "buc.", "szt.", "шт.", "шт.", "ком.", "adet"),
    "бр": ("pcs", "Stk", "pcs", "uds", "τεμ", "kom", "buc", "szt", "шт", "шт", "ком", "adet"),
    "дебелина": ("thickness", "Dicke", "épaisseur", "espesor", "πάχος", "debljina", "grosime", "grubość", "товщина",
                 "толщина", "дебљина", "kalınlık"),
    "стена": ("wall", "Wand", "voile", "muro", "τοίχος", "zid", "perete", "ściana", "стіна", "стена", "зид",
              "duvar"),
    "дължина": ("length", "Länge", "longueur", "longitud", "μήκος", "duljina", "lungime", "długość", "довжина",
                "длина", "дужина", "uzunluk"),
    "височина": ("height", "Höhe", "hauteur", "altura", "ύψος", "visina", "înălțime", "wysokość", "висота", "высота",
                 "висина", "yükseklik"),
    "ляво": ("left", "links", "gauche", "izquierda", "αριστερά", "lijevo", "stânga", "lewa", "ліворуч", "слева",
             "лево", "sol"),
    "дясно": ("right", "rechts", "droite", "derecha", "δεξιά", "desno", "dreapta", "prawa", "праворуч", "справа",
              "десно", "sağ"),
    "Край": ("End", "Ende", "Extrémité", "Extremo", "Άκρο", "Kraj", "Capăt", "Koniec", "Торець", "Торец", "Крај", "Uç"),
    "ребро на {l3}{unit} от левия край": (
        "stem at {l3}{unit} from the left end", "Steg bei {l3}{unit} vom linken Ende",
        "âme à {l3}{unit} de l'extrémité gauche", "alma a {l3}{unit} del extremo izquierdo",
        "νεύρο στα {l3}{unit} από το αριστερό άκρο", "rebro na {l3}{unit} od lijevog kraja",
        "nervură la {l3}{unit} de capătul stâng", "żebro {l3}{unit} od lewego końca",
        "ребро на {l3}{unit} від лівого краю", "ребро на {l3}{unit} от левого края",
        "ребро на {l3}{unit} од левог краја", "gövde, sol uçtan {l3}{unit} mesafede"),
    "край {ends}": ("end {ends}", "Ende {ends}", "extrémité {ends}", "extremo {ends}", "άκρο {ends}", "kraj {ends}",
                    "capăt {ends}", "koniec {ends}", "торець {ends}", "торец {ends}", "крај {ends}",
                    "uç {ends}"),
    " и ": (" and ", " und ", " et ", " y ", " και ", " i ", " și ", " i ", " і ", " и ", " и ", " ve "),
    "няма": ("none", "keine", "aucune", "ninguno", "κανένα", "nema", "niciunul", "brak", "немає", "нет", "нема", "yok"),

    # Типове елементи (PDF - „Тип:“)
    "Колона": ("Column", "Stütze", "Poteau", "Pilar", "Υποστύλωμα", "Stup", "Stâlp", "Słup", "Колона", "Колонна",
               "Стуб", "Kolon"),
    "Права Стена": ("Straight wall", "Gerade Wand", "Voile droit", "Muro recto", "Ευθύς τοίχος", "Ravni zid",
                    "Perete drept", "Ściana prosta", "Пряма стіна", "Прямая стена", "Прави зид",
                    "Düz duvar"),
    "L-образна Стена": ("L-shaped wall", "L-förmige Wand", "Voile en L", "Muro en L", "Τοίχος σχήματος L",
                        "Zid L-oblika", "Perete în formă de L", "Ściana w kształcie L", "L-подібна стіна",
                        "L-образная стена", "Зид L-облика", "L şeklinde duvar"),
    "П-образна Стена": ("U-shaped wall", "U-förmige Wand", "Voile en U", "Muro en U", "Τοίχος σχήματος Π",
                        "Zid U-oblika", "Perete în formă de U", "Ściana w kształcie U", "П-подібна стіна",
                        "П-образная стена", "Зид П-облика", "U şeklinde duvar"),
    "T-образна Стена": ("T-shaped wall", "T-förmige Wand", "Voile en T", "Muro en T", "Τοίχος σχήματος Τ",
                        "Zid T-oblika", "Perete în formă de T", "Ściana w kształcie T", "Т-подібна стіна",
                        "Т-образная стена", "Зид Т-облика", "T şeklinde duvar"),
    # Началото на името на елемента (празно наименование)
    "Стена": ("Wall", "Wand", "Voile", "Muro", "Τοίχος", "Zid", "Perete", "Ściana", "Стіна", "Стена", "Зид",
              "Duvar"),
    "L-стена": ("L-wall", "L-Wand", "Voile en L", "Muro en L", "Τοίχος L", "L-zid", "Perete L", "Ściana L", "L-стіна",
                "L-стена", "L-зид", "L-duvar"),
    "П-стена": ("U-wall", "U-Wand", "Voile en U", "Muro en U", "Τοίχος Π", "U-zid", "Perete U", "Ściana U", "П-стіна",
                "П-стена", "П-зид", "U-duvar"),
    "T-стена": ("T-wall", "T-Wand", "Voile en T", "Muro en T", "Τοίχος Τ", "T-zid", "Perete T", "Ściana T", "Т-стіна",
                "Т-стена", "Т-зид", "T-duvar"),
    # Типовете с малка буква (Excel, заглавие на изгледа отгоре на колона)
    "колона": ("column", "Stütze", "poteau", "pilar", "υποστύλωμα", "stup", "stâlp", "słup", "колона", "колонна",
               "стуб", "kolon"),
    "права стена": ("straight wall", "gerade Wand", "voile droit", "muro recto", "ευθύς τοίχος", "ravni zid",
                    "perete drept", "ściana prosta", "пряма стіна", "прямая стена", "прави зид",
                    "düz duvar"),

    # Чертежи (PDF, картините)
    "ДЪСКА {w} см": ("BOARD {w} cm", "BRETT {w} cm", "PLANCHE {w} cm", "TABLA {w} cm", "ΣΑΝΙΔΑ {w} cm",
                     "DASKA {w} cm", "SCÂNDURĂ {w} cm", "DESKA {w} cm", "ДОШКА {w} см", "ДОСКА {w} см",
                     "ДАСКА {w} см", "TAHTA {w} cm"),
    "Страна": ("Side", "Seite", "Côté", "Lado", "Πλευρά", "Strana", "Latura", "Strona", "Сторона", "Сторона", "Страна", "Yüz"),
    "Изглед отпред (Front View)": ("Front view", "Vorderansicht", "Vue de face", "Vista frontal", "Πρόσοψη",
                                   "Pogled sprijeda", "Vedere frontală", "Widok z przodu", "Вигляд спереду",
                                   "Вид спереди", "Поглед спреда", "Ön görünüş"),
    "3D Общ кофражен план на обект (Project Overview)": (
        "3D formwork overview of the project", "3D-Schalungsübersicht des Projekts",
        "Vue d'ensemble 3D du coffrage", "Vista general 3D del encofrado", "Τρισδιάστατη επισκόπηση ξυλοτύπων έργου",
        "3D pregled oplate objekta", "Vedere de ansamblu 3D a cofrajului", "Widok 3D szalunków obiektu",
        "3D загальний план опалубки об'єкта", "3D общий план опалубки объекта",
        "3D општи план оплате објекта", "3D proje kalıp genel görünümü"),
    "КОФРАЖНА СИСТЕМА TEKO / TEKO FORMWORK SYSTEM": (
        "TEKO FORMWORK SYSTEM", "TEKO SCHALUNGSSYSTEM", "SYSTÈME DE COFFRAGE TEKO", "SISTEMA DE ENCOFRADO TEKO",
        "ΣΥΣΤΗΜΑ ΞΥΛΟΤΥΠΩΝ TEKO", "TEKO SUSTAV OPLATE", "SISTEM DE COFRAJ TEKO", "SYSTEM SZALUNKOWY TEKO",
        "ОПАЛУБНА СИСТЕМА TEKO", "ОПАЛУБОЧНАЯ СИСТЕМА TEKO", "СИСТЕМ ОПЛАТЕ TEKO",
        "TEKO KALIP SİSTEMİ"),
    "Обект:": ("Site:", "Bauvorhaben:", "Chantier :", "Obra:", "Έργο:", "Objekt:", "Obiectiv:", "Obiekt:", "Об'єкт:",
               "Объект:", "Објекат:", "Proje:"),
    "Клиент:": ("Client:", "Kunde:", "Client :", "Cliente:", "Πελάτης:", "Klijent:", "Client:", "Klient:", "Клієнт:",
                "Клиент:", "Клијент:", "Müşteri:"),
    "Няма посочен клиент": ("No client specified", "Kein Kunde angegeben", "Aucun client indiqué",
                            "Cliente no indicado", "Δεν ορίστηκε πελάτης", "Klijent nije naveden",
                            "Niciun client specificat", "Nie podano klienta", "Клієнта не вказано", "Клиент не указан",
                            "Клијент није наведен", "Müşteri belirtilmedi"),
    "Обект TEKO": ("TEKO site", "TEKO-Bauvorhaben", "Chantier TEKO", "Obra TEKO", "Έργο TEKO", "Objekt TEKO",
                   "Obiectiv TEKO", "Obiekt TEKO", "Об'єкт TEKO", "Объект TEKO", "Објекат TEKO",
                   "TEKO projesi"),
    "Обобщена количествена сметка (Project BOM)": (
        "Project bill of quantities", "Massenauszug des Projekts", "Métré récapitulatif du projet",
        "Resumen de cantidades del proyecto", "Συνοπτική προμέτρηση έργου", "Zbirni iskaz količina",
        "Antemăsurătoare centralizatoare", "Zbiorcze zestawienie ilości", "Зведена відомість кількостей",
        "Сводная ведомость количеств", "Збирни предмер количина",
        "Proje metraj özeti"),
    "Артикул / Код": ("Item / Code", "Artikel / Code", "Article / Code", "Artículo / Código", "Είδος / Κωδικός",
                      "Artikl / Šifra", "Articol / Cod", "Pozycja / Kod", "Артикул / Код", "Артикул / Код",
                      "Артикал / Шифра", "Ürün / Kod"),
    "Система": ("System", "System", "Système", "Sistema", "Σύστημα", "Sustav", "Sistem", "System", "Система",
                "Система", "Систем", "Sistem"),
    "Количество": ("Quantity", "Menge", "Quantité", "Cantidad", "Ποσότητα", "Količina", "Cantitate", "Ilość",
                   "Кількість", "Количество", "Количина", "Miktar"),
    "Чертеж и Спецификация: {name}": (
        "Drawing and specification: {name}", "Zeichnung und Spezifikation: {name}", "Plan et spécification : {name}",
        "Plano y especificación: {name}", "Σχέδιο και προδιαγραφή: {name}", "Nacrt i specifikacija: {name}",
        "Desen și specificație: {name}", "Rysunek i specyfikacja: {name}", "Креслення та специфікація: {name}",
        "Чертёж и спецификация: {name}", "Цртеж и спецификација: {name}",
        "Çizim ve malzeme listesi: {name}"),
    "Тип:": ("Type:", "Typ:", "Type :", "Tipo:", "Τύπος:", "Tip:", "Tip:", "Typ:", "Тип:", "Тип:", "Тип:",
             "Tip:"),
    "Размери:": ("Dimensions:", "Abmessungen:", "Dimensions :", "Dimensiones:", "Διαστάσεις:", "Dimenzije:",
                 "Dimensiuni:", "Wymiary:", "Розміри:", "Размеры:", "Димензије:", "Boyutlar:"),
    "Височина:": ("Height:", "Höhe:", "Hauteur :", "Altura:", "Ύψος:", "Visina:", "Înălțime:", "Wysokość:", "Висота:",
                  "Высота:", "Висина:", "Yükseklik:"),
    "Затворени краища:": ("Closed ends:", "Geschlossene Enden:", "Extrémités fermées :", "Extremos cerrados:",
                          "Κλειστά άκρα:", "Zatvoreni krajevi:", "Capete închise:", "Zamknięte końce:",
                          "Закриті торці:", "Закрытые торцы:", "Затворени крајеви:",
                          "Kapalı uçlar:"),
    "Брой:": ("Qty:", "Anzahl:", "Nombre :", "Cantidad:", "Αριθμός:", "Broj:", "Număr:", "Liczba:", "Кількість:",
              "Количество:", "Број:", "Adet:"),
    "TOP VIEW / ИЗГЛЕД ОТГОРЕ": ("TOP VIEW", "DRAUFSICHT", "VUE DE DESSUS", "VISTA SUPERIOR", "ΚΑΤΟΨΗ",
                                 "POGLED ODOZGO", "VEDERE DE SUS", "WIDOK Z GÓRY", "ВИГЛЯД ЗВЕРХУ", "ВИД СВЕРХУ",
                                 "ПОГЛЕД ОДОЗГО", "ÜSTTEN GÖRÜNÜŞ"),
    "3D VIEW / 3D ИЗГЛЕД": ("3D VIEW", "3D-ANSICHT", "VUE 3D", "VISTA 3D", "ΤΡΙΣΔΙΑΣΤΑΤΗ ΟΨΗ", "3D POGLED",
                            "VEDERE 3D", "WIDOK 3D", "3D ВИГЛЯД", "3D ВИД", "3D ПОГЛЕД", "3D GÖRÜNÜŞ"),
    "Необходим артикул за елемента": (
        "Items required for the element", "Benötigte Artikel für das Element", "Articles nécessaires pour l'élément",
        "Artículos necesarios para el elemento", "Απαιτούμενα είδη για το στοιχείο", "Potrebni artikli za element",
        "Articole necesare pentru element", "Pozycje potrzebne dla elementu", "Необхідні артикули для елемента",
        "Необходимые артикулы для элемента", "Потребни артикли за елемент",
        "Eleman için gerekli ürünler"),
    "За 1 бр.": ("Per 1 pc", "Für 1 Stk.", "Pour 1 pc", "Por 1 ud.", "Ανά 1 τεμ.", "Za 1 kom.", "Pentru 1 buc.",
                 "Na 1 szt.", "На 1 шт.", "На 1 шт.", "За 1 ком.", "1 adet için"),
    "Общо за {n} бр.": ("Total for {n} pcs", "Gesamt für {n} Stk.", "Total pour {n} pcs", "Total para {n} uds.",
                        "Σύνολο για {n} τεμ.", "Ukupno za {n} kom.", "Total pentru {n} buc.", "Razem na {n} szt.",
                        "Разом на {n} шт.", "Всего на {n} шт.", "Укупно за {n} ком.",
                        "{n} adet için toplam"),

    # Excel
    "Кол. сметка": ("Bill of quantities", "Massenauszug", "Métré", "Mediciones", "Προμέτρηση", "Troškovnik",
                    "Antemăsurătoare", "Przedmiar", "Відомість обсягів", "Ведомость объёмов", "Предмер", "Metraj"),
    "Елемент {i}": ("Element {i}", "Element {i}", "Élément {i}", "Elemento {i}", "Στοιχείο {i}", "Element {i}",
                    "Element {i}", "Element {i}", "Елемент {i}", "Элемент {i}", "Елемент {i}",
                    "Eleman {i}"),
    "Елементи Теко България": ("TEKO Bulgaria elements", "TEKO Bulgaria Elemente", "Éléments TEKO Bulgaria",
                               "Elementos TEKO Bulgaria", "Στοιχεία TEKO Bulgaria", "Elementi TEKO Bulgaria",
                               "Elemente TEKO Bulgaria", "Elementy TEKO Bulgaria", "Елементи TEKO Bulgaria",
                               "Элементы TEKO Bulgaria", "Елементи TEKO Bulgaria",
                               "TEKO Bulgaria elemanları"),
    "Елемент": ("Item", "Artikel", "Article", "Artículo", "Είδος", "Artikl", "Articol", "Pozycja", "Елемент",
                "Элемент", "Елемент", "Ürün"),
    "Мярка": ("Unit", "Einheit", "Unité", "Unidad", "Μονάδα", "Jedinica", "U.M.", "Jednostka", "Од. вим.",
              "Ед. изм.", "Јединица", "Birim"),
    "Кол.": ("Qty", "Menge", "Qté", "Cant.", "Ποσ.", "Kol.", "Cant.", "Ilość", "К-сть", "Кол-во", "Кол.",
             "Miktar"),
    "Остава": ("In stock", "Bestand", "En stock", "Existencias", "Απόθεμα", "Na zalihi", "Stoc", "Stan", "Залишок",
               "Остаток", "На стању", "Stok"),
    "Складова наличност": ("Stock", "Lagerbestand", "Stock", "Existencias", "Απόθεμα αποθήκης", "Stanje skladišta",
                           "Stoc", "Stan magazynowy", "Складські залишки", "Складские остатки", "Стање залиха",
                           "Depo stoku"),
    "Ед. Цена": ("Unit price", "Einzelpreis", "Prix unitaire", "Precio unitario", "Τιμή μονάδας", "Jedinična cijena",
                 "Preț unitar", "Cena jedn.", "Ціна за од.", "Цена за ед.", "Јединична цена",
                 "Birim fiyat"),
    "Стойност": ("Value", "Betrag", "Montant", "Importe", "Αξία", "Iznos", "Valoare", "Wartość", "Вартість",
                 "Стоимость", "Износ", "Tutar"),
    "Ед. Цена с отстъпка": ("Unit price with discount", "Einzelpreis mit Rabatt", "Prix unitaire remisé",
                            "Precio unitario con descuento", "Τιμή μονάδας με έκπτωση", "Jed. cijena s popustom",
                            "Preț unitar cu reducere", "Cena jedn. z rabatem", "Ціна за од. зі знижкою",
                            "Цена за ед. со скидкой", "Јед. цена са попустом",
                            "İndirimli birim fiyat"),
    "Стойност с отстъпка": ("Value with discount", "Betrag mit Rabatt", "Montant remisé", "Importe con descuento",
                            "Αξία με έκπτωση", "Iznos s popustom", "Valoare cu reducere", "Wartość z rabatem",
                            "Вартість зі знижкою", "Стоимость со скидкой", "Износ са попустом",
                            "İndirimli tutar"),
    "Dimensions,  [cm]": ("Dimensions, [cm]", "Abmessungen, [cm]", "Dimensions, [cm]", "Dimensiones, [cm]",
                          "Διαστάσεις, [cm]", "Dimenzije, [cm]", "Dimensiuni, [cm]", "Wymiary, [cm]", "Розміри, [см]",
                          "Размеры, [см]", "Димензије, [см]", "Boyutlar, [cm]"),
    # площта, която покрива панелът - „площ на кофража“ (не „покрита / застроена площ“, „покрив“, „облицовка“)
    "Покривна площ,  [m2]": ("Formwork area, [m2]", "Schalfläche, [m2]", "Surface coffrante, [m2]",
                             "Superficie de encofrado, [m2]", "Επιφάνεια ξυλοτύπου, [m2]", "Površina oplate, [m2]",
                             "Suprafață cofrată, [m2]", "Powierzchnia szalunku, [m2]", "Площа опалубки, [м2]",
                             "Площадь опалубки, [м2]", "Површина оплате, [м2]",
                             "Kalıp alanı, [m2]"),
    "Тегло, [кг]": ("Weight, [kg]", "Gewicht, [kg]", "Poids, [kg]", "Peso, [kg]", "Βάρος, [kg]", "Težina, [kg]",
                    "Greutate, [kg]", "Waga, [kg]", "Вага, [кг]", "Вес, [кг]", "Тежина, [кг]",
                    "Ağırlık, [kg]"),
    "Тегло общо, [кг]": ("Total weight, [kg]", "Gesamtgewicht, [kg]", "Poids total, [kg]", "Peso total, [kg]",
                         "Συνολικό βάρος, [kg]", "Ukupna težina, [kg]", "Greutate totală, [kg]",
                         "Waga całkowita, [kg]", "Загальна вага, [кг]", "Общий вес, [кг]", "Укупна тежина, [кг]", "Toplam ağırlık, [kg]"),
    "Кол,  [m2]": ("Qty, [m2]", "Menge, [m2]", "Qté, [m2]", "Cant., [m2]", "Ποσ., [m2]", "Kol., [m2]",
                   "Cant., [m2]", "Ilość, [m2]", "К-сть, [м2]", "Кол-во, [м2]", "Кол., [м2]",
                   "Miktar, [m2]"),
    "Наличност в склада": ("Stock in warehouse", "Lagerbestand", "Stock en entrepôt", "Existencias en almacén",
                           "Απόθεμα αποθήκης", "Na skladištu", "Stoc în depozit", "Stan magazynowy",
                           "Наявність на складі", "Наличие на складе", "На складишту",
                           "Depodaki stok"),
    "Нужно за проекта": ("Needed for the project", "Bedarf für das Projekt", "Nécessaire au projet",
                         "Necesario para el proyecto", "Απαιτούμενα για το έργο", "Potrebno za projekt",
                         "Necesar pentru proiect", "Potrzebne do projektu", "Потрібно для проєкту",
                         "Нужно для проекта", "Потребно за пројекат",
                         "Proje için gerekli"),
    "Остават": ("Remaining", "Verbleibend", "Restant", "Restante", "Υπόλοιπο", "Preostalo", "Rămân", "Pozostaje",
                "Залишається", "Остаётся", "Преостаје", "Kalan"),
    "ОБЩО": ("TOTAL", "GESAMT", "TOTAL", "TOTAL", "ΣΥΝΟΛΟ", "UKUPNO", "TOTAL", "RAZEM", "РАЗОМ", "ИТОГО", "УКУПНО", "TOPLAM"),
    "ОТСТЪПКА %": ("DISCOUNT %", "RABATT %", "REMISE %", "DESCUENTO %", "ΕΚΠΤΩΣΗ %", "POPUST %", "REDUCERE %",
                   "RABAT %", "ЗНИЖКА %", "СКИДКА %", "ПОПУСТ %", "İNDİRİM %"),
    "ОТСТЪПКА СТОЙНОСТ": ("DISCOUNT AMOUNT", "RABATTBETRAG", "MONTANT DE LA REMISE", "IMPORTE DEL DESCUENTO",
                          "ΠΟΣΟ ΕΚΠΤΩΣΗΣ", "IZNOS POPUSTA", "VALOARE REDUCERE", "KWOTA RABATU", "СУМА ЗНИЖКИ",
                          "СУММА СКИДКИ", "ИЗНОС ПОПУСТА", "İNDİRİM TUTARI"),
    "ОБЩО БЕЗ ДДС": ("TOTAL EXCL. VAT", "GESAMT OHNE MWST.", "TOTAL HT", "TOTAL SIN IVA", "ΣΥΝΟΛΟ ΧΩΡΙΣ ΦΠΑ",
                     "UKUPNO BEZ PDV-a", "TOTAL FĂRĂ TVA", "RAZEM BEZ VAT", "РАЗОМ БЕЗ ПДВ", "ИТОГО БЕЗ НДС",
                     "УКУПНО БЕЗ ПДВ", "KDV HARİÇ TOPLAM"),
    "Брой елементи:": ("Number of elements:", "Anzahl Elemente:", "Nombre d'éléments :", "Número de elementos:",
                       "Αριθμός στοιχείων:", "Broj elemenata:", "Număr de elemente:", "Liczba elementów:",
                       "Кількість елементів:", "Количество элементов:", "Број елемената:",
                       "Eleman sayısı:"),
    "Кол. за 1 бр.": ("Qty per 1 pc", "Menge für 1 Stk.", "Qté pour 1 pc", "Cant. por 1 ud.", "Ποσ. ανά 1 τεμ.",
                      "Kol. za 1 kom.", "Cant. pentru 1 buc.", "Ilość na 1 szt.", "К-сть на 1 шт.",
                      "Кол-во на 1 шт.", "Кол. за 1 ком.", "1 adet için miktar"),
    "Кол. общо": ("Total qty", "Menge gesamt", "Qté totale", "Cant. total", "Συνολική ποσ.", "Ukupna kol.",
                  "Cant. totală", "Ilość razem", "К-сть разом", "Кол-во всего", "Укупна кол.",
                  "Toplam miktar"),
    "Изглед отгоре": ("Top view", "Draufsicht", "Vue de dessus", "Vista superior", "Κάτοψη", "Pogled odozgo",
                      "Vedere de sus", "Widok z góry", "Вигляд зверху", "Вид сверху", "Поглед одозго", "Üstten görünüş"),
    "Изглед": ("View", "Ansicht", "Vue", "Vista", "Όψη", "Pogled", "Vedere", "Widok", "Вигляд", "Вид", "Поглед", "Görünüş"),
    "Елементи (1 клетка = 5 см) - копирайте блок и го поставете в чертежа": (
        "Elements (1 cell = 5 cm) - copy a block and paste it into the drawing",
        "Elemente (1 Zelle = 5 cm) - Block kopieren und in die Zeichnung einfügen",
        "Éléments (1 cellule = 5 cm) - copiez un bloc et collez-le dans le plan",
        "Elementos (1 celda = 5 cm) - copie un bloque y péguelo en el plano",
        "Στοιχεία (1 κελί = 5 cm) - αντιγράψτε ένα μπλοκ και επικολλήστε το στο σχέδιο",
        "Elementi (1 ćelija = 5 cm) - kopirajte blok i zalijepite ga u nacrt",
        "Elemente (1 celulă = 5 cm) - copiați un bloc și lipiți-l în desen",
        "Elementy (1 komórka = 5 cm) - skopiuj blok i wklej go do rysunku",
        "Елементи (1 клітинка = 5 см) - скопіюйте блок і вставте його в креслення",
        "Элементы (1 ячейка = 5 см) - скопируйте блок и вставьте его в чертёж",
        "Елементи (1 ћелија = 5 см) - копирајте блок и налепите га у цртеж",
        "Elemanlar (1 hücre = 5 cm) - bir bloğu kopyalayıp çizime yapıştırın"),
    "Изправени панели": ("Upright panels", "Stehende Schalungselemente", "Panneaux debout", "Paneles verticales", "Όρθια πάνελ",
                         "Uspravni paneli", "Panouri verticale", "Panele pionowe", "Вертикальні панелі",
                         "Вертикальные панели", "Усправни панели", "Dikey paneller"),
    "Легнали панели (изглед отгоре вляво, изглед отпред вдясно)": (
        "Horizontal panels (top view left, front view right)",
        "Liegende Schalungselemente (Draufsicht links, Vorderansicht rechts)",
        "Panneaux couchés (vue de dessus à gauche, vue de face à droite)",
        "Paneles horizontales (vista superior a la izquierda, vista frontal a la derecha)",
        "Οριζόντια πάνελ (κάτοψη αριστερά, πρόσοψη δεξιά)",
        "Položeni paneli (pogled odozgo lijevo, pogled sprijeda desno)",
        "Panouri orizontale (vedere de sus în stânga, vedere frontală în dreapta)",
        "Panele leżące (widok z góry po lewej, widok z przodu po prawej)",
        "Горизонтальні панелі (вигляд зверху ліворуч, вигляд спереду праворуч)",
        "Горизонтальные панели (вид сверху слева, вид спереди справа)",
        "Положени панели (поглед одозго лево, поглед спреда десно)",
        "Yatay paneller (üstten görünüş solda, ön görünüş sağda)"),

    # Word оферта
    "ТЕКО България ООД | ЕИК 208141542\n": (
        "TEKO Bulgaria Ltd. | Reg. No. 208141542\n", "TEKO Bulgaria Ltd. | Reg.-Nr. 208141542\n",
        "TEKO Bulgaria Ltd. | N° d'immatriculation 208141542\n", "TEKO Bulgaria Ltd. | N.º de registro 208141542\n",
        "TEKO Bulgaria Ltd. | Αρ. μητρώου 208141542\n", "TEKO Bulgaria Ltd. | Matični br. 208141542\n",
        "TEKO Bulgaria Ltd. | Nr. înregistrare 208141542\n", "TEKO Bulgaria Ltd. | Nr rej. 208141542\n",
        "TEKO Bulgaria Ltd. | Реєстр. № 208141542\n", "TEKO Bulgaria Ltd. | Рег. № 208141542\n",
        "TEKO Bulgaria Ltd. | Матични бр. 208141542\n",
        "TEKO Bulgaria Ltd. | Sicil No. 208141542\n"),
    "2700 Благоевград, ул. „Ал. Стамболийски” №9, ет. 1\n"
    "www.tekoform.com | e-mail: bulgaria@tekoform.com | тел: +359 879 044 188": tuple(
        address + "\nwww.tekoform.com | e-mail: bulgaria@tekoform.com | " + phone + " +359 879 044 188"
        for address, phone in (
            ("9 Al. Stamboliyski St., fl. 1, 2700 Blagoevgrad, Bulgaria", "tel.:"),
            ("Al.-Stamboliyski-Str. 9, 1. OG, 2700 Blagoewgrad, Bulgarien", "Tel.:"),
            ("9, rue Al. Stamboliyski, 1er étage, 2700 Blagoevgrad, Bulgarie", "tél. :"),
            ("C/ Al. Stamboliyski 9, planta 1, 2700 Blagoevgrad, Bulgaria", "tel.:"),
            ("Οδός Αλ. Σταμπολίισκι 9, 1ος όροφος, 2700 Μπλαγκόεβγκραντ, Βουλγαρία", "τηλ.:"),
            ("ul. Al. Stamboliyski 9, 1. kat, 2700 Blagoevgrad, Bugarska", "tel.:"),
            ("str. Al. Stamboliyski nr. 9, et. 1, 2700 Blagoevgrad, Bulgaria", "tel.:"),
            ("ul. Al. Stamboliyski 9, 1 piętro, 2700 Błagojewgrad, Bułgaria", "tel.:"),
            ("вул. Ал. Стамболійського, 9, пов. 1, 2700 Благоєвград, Болгарія", "тел.:"),
            ("ул. Ал. Стамболийского, 9, эт. 1, 2700 Благоевград, Болгария", "тел.:"),
            ("ул. Ал. Стамболијски 9, 1. спрат, 2700 Благоевград, Бугарска", "тел.:"),
            ("Al. Stamboliyski Cad. No: 9, Kat 1, 2700 Blagoevgrad, Bulgaristan", "tel.:"))),
    "ОФЕРТА\nЗа наемане на пластмасова кофражна система TEKO": (
        "QUOTATION\nFor the rental of the TEKO plastic formwork system",
        "ANGEBOT\nFür die Miete des TEKO-Kunststoffschalungssystems",
        "DEVIS\nPour la location du système de coffrage plastique TEKO",
        "OFERTA\nPara el alquiler del sistema de encofrado plástico TEKO",
        "ΠΡΟΣΦΟΡΑ\nΓια την ενοικίαση του πλαστικού συστήματος ξυλοτύπων TEKO",
        "PONUDA\nZa najam plastičnog sustava oplate TEKO",
        "OFERTĂ\nPentru închirierea sistemului de cofraj din plastic TEKO",
        "OFERTA\nNa wynajem plastikowego systemu szalunkowego TEKO",
        "КОМЕРЦІЙНА ПРОПОЗИЦІЯ\nНа оренду пластикової опалубної системи TEKO",
        "КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ\nНа аренду пластиковой опалубочной системы TEKO",
        "ПОНУДА\nЗа закуп пластичног система оплате TEKO",
        "TEKLİF\nTEKO plastik kalıp sisteminin kiralanması için"),
    "ОФЕРТА\nЗа закупуване на пластмасова кофражна система TEKO": (
        "QUOTATION\nFor the purchase of the TEKO plastic formwork system",
        "ANGEBOT\nFür den Kauf des TEKO-Kunststoffschalungssystems",
        "DEVIS\nPour l'achat du système de coffrage plastique TEKO",
        "OFERTA\nPara la compra del sistema de encofrado plástico TEKO",
        "ΠΡΟΣΦΟΡΑ\nΓια την αγορά του πλαστικού συστήματος ξυλοτύπων TEKO",
        "PONUDA\nZa kupnju plastičnog sustava oplate TEKO",
        "OFERTĂ\nPentru achiziționarea sistemului de cofraj din plastic TEKO",
        "OFERTA\nNa zakup plastikowego systemu szalunkowego TEKO",
        "КОМЕРЦІЙНА ПРОПОЗИЦІЯ\nНа придбання пластикової опалубної системи TEKO",
        "КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ\nНа покупку пластиковой опалубочной системы TEKO",
        "ПОНУДА\nЗа куповину пластичног система оплате TEKO",
        "TEKLİF\nTEKO plastik kalıp sisteminin satın alınması için"),
    "До: ": ("To: ", "An: ", "À : ", "Para: ", "Προς: ", "Za: ", "Către: ", "Do: ", "Кому: ", "Кому: ", "За: ", "Kime: "),
    "Относно: ": ("Subject: ", "Betreff: ", "Objet : ", "Asunto: ", "Θέμα: ", "Predmet: ", "Subiect: ", "Dotyczy: ",
                  "Щодо: ", "Тема: ", "Предмет: ", "Konu: "),
    "Кофриране на стоманобетонови елементи за обект: „{project}“\n": (
        "Formwork for reinforced concrete elements for the site: “{project}”\n",
        "Schalung von Stahlbetonbauteilen für das Bauvorhaben: „{project}“\n",
        "Coffrage d'éléments en béton armé pour le chantier : « {project} »\n",
        "Encofrado de elementos de hormigón armado para la obra: «{project}»\n",
        "Ξυλότυπος στοιχείων οπλισμένου σκυροδέματος για το έργο: «{project}»\n",
        "Oplata armiranobetonskih elemenata za objekt: „{project}”\n",
        "Cofrarea elementelor din beton armat pentru obiectivul: „{project}”\n",
        "Szalowanie elementów żelbetowych dla obiektu: „{project}”\n",
        "Опалублення залізобетонних елементів для об'єкта: «{project}»\n",
        "Опалубка железобетонных элементов для объекта: «{project}»\n",
        "Оплата армиранобетонских елемената за објекат: „{project}”\n",
        "Betonarme elemanların kalıplanması, proje: “{project}”\n"),
    # 3D план на етажа (таб 6, 22.11.2026)
    "3D план на етажа": ("3D floor plan", "3D-Geschossplan", "Plan 3D de l'étage", "Plano 3D de la planta",
                         "Τρισδιάστατη κάτοψη ορόφου", "3D tlocrt etaže", "Plan 3D al etajului", "Rzut 3D kondygnacji",
                         "3D план поверху", "3D план этажа", "3D основа спрата", "3B kat planı"),
    "Чертеж: {name}": ("Drawing: {name}", "Zeichnung: {name}", "Plan : {name}", "Plano: {name}", "Σχέδιο: {name}",
                       "Nacrt: {name}", "Plan: {name}", "Rysunek: {name}", "Креслення: {name}", "Чертёж: {name}",
                       "Цртеж: {name}", "Çizim: {name}"),
    "Дата: ": ("Date: ", "Datum: ", "Date : ", "Fecha: ", "Ημερομηνία: ", "Datum: ", "Data: ", "Data: ", "Дата: ",
               "Дата: ", "Датум: ", "Tarih: "),
    " г.": ("", "", "", "", "", "", "", "", " р.", " г.", " г.", ""),
    "Размери": ("Dimensions", "Abmessungen", "Dimensions", "Dimensiones", "Διαστάσεις", "Dimenzije", "Dimensiuni",
                "Wymiary", "Розміри", "Размеры", "Димензије", "Boyutlar"),
    "Брой": ("Qty", "Anzahl", "Nombre", "Cantidad", "Αριθμός", "Broj", "Număr", "Liczba", "Кількість",
             "Количество", "Број", "Adet"),
    "Площ (m²)": ("Area (m²)", "Fläche (m²)", "Surface (m²)", "Superficie (m²)", "Επιφάνεια (m²)", "Površina (m²)",
                  "Suprafață (m²)", "Powierzchnia (m²)", "Площа (м²)", "Площадь (м²)", "Површина (м²)", "Alan (m²)"),
    "Ед. цена (€/m²)": ("Unit price (€/m²)", "Einzelpreis (€/m²)", "Prix unitaire (€/m²)", "Precio unitario (€/m²)",
                        "Τιμή μονάδας (€/m²)", "Jed. cijena (€/m²)", "Preț unitar (€/m²)", "Cena jedn. (€/m²)",
                        "Ціна за од. (€/м²)", "Цена за ед. (€/м²)", "Јед. цена (€/м²)",
                        "Birim fiyat (€/m²)"),
    "Обща сума (€)": ("Total amount (€)", "Gesamtbetrag (€)", "Montant total (€)", "Importe total (€)",
                      "Συνολικό ποσό (€)", "Ukupan iznos (€)", "Sumă totală (€)", "Kwota łączna (€)",
                      "Загальна сума (€)", "Общая сумма (€)", "Укупан износ (€)",
                      "Toplam tutar (€)"),
    "Обща кофражна площ: {area} m²\n": (
        "Total formwork area: {area} m²\n", "Gesamte Schalungsfläche: {area} m²\n",
        "Surface totale de coffrage : {area} m²\n", "Superficie total de encofrado: {area} m²\n",
        "Συνολική επιφάνεια ξυλοτύπων: {area} m²\n", "Ukupna površina oplate: {area} m²\n",
        "Suprafața totală de cofraj: {area} m²\n", "Całkowita powierzchnia szalunku: {area} m²\n",
        "Загальна площа опалубки: {area} м²\n", "Общая площадь опалубки: {area} м²\n",
        "Укупна површина оплате: {area} м²\n",
        "Toplam kalıp alanı: {area} m²\n"),
    "Обща стойност за наем (без ДДС): {value} €\n": (
        "Total rental value (excl. VAT): {value} €\n", "Gesamtwert der Miete (ohne MwSt.): {value} €\n",
        "Valeur totale de la location (HT) : {value} €\n", "Valor total del alquiler (sin IVA): {value} €\n",
        "Συνολική αξία ενοικίασης (χωρίς ΦΠΑ): {value} €\n", "Ukupna vrijednost najma (bez PDV-a): {value} €\n",
        "Valoarea totală a închirierii (fără TVA): {value} €\n", "Łączna wartość wynajmu (bez VAT): {value} €\n",
        "Загальна вартість оренди (без ПДВ): {value} €\n", "Общая стоимость аренды (без НДС): {value} €\n",
        "Укупна вредност закупа (без ПДВ): {value} €\n",
        "Toplam kira bedeli (KDV hariç): {value} €\n"),
    "Обща стойност за покупка (без ДДС): {value} €\n": (
        "Total purchase value (excl. VAT): {value} €\n", "Gesamtwert des Kaufs (ohne MwSt.): {value} €\n",
        "Valeur totale de l'achat (HT) : {value} €\n", "Valor total de la compra (sin IVA): {value} €\n",
        "Συνολική αξία αγοράς (χωρίς ΦΠΑ): {value} €\n", "Ukupna vrijednost kupnje (bez PDV-a): {value} €\n",
        "Valoarea totală a achiziției (fără TVA): {value} €\n", "Łączna wartość zakupu (bez VAT): {value} €\n",
        "Загальна вартість придбання (без ПДВ): {value} €\n", "Общая стоимость покупки (без НДС): {value} €\n",
        "Укупна вредност куповине (без ПДВ): {value} €\n",
        "Toplam satın alma bedeli (KDV hariç): {value} €\n"),
    "ДДС (20%): {value} €\n": ("VAT (20%): {value} €\n", "MwSt. (20 %): {value} €\n", "TVA (20 %) : {value} €\n",
                               "IVA (20%): {value} €\n", "ΦΠΑ (20%): {value} €\n", "PDV (20%): {value} €\n",
                               "TVA (20%): {value} €\n", "VAT (20%): {value} €\n", "ПДВ (20%): {value} €\n",
                               "НДС (20%): {value} €\n", "ПДВ (20%): {value} €\n",
                               "KDV (%20): {value} €\n"),
    "ОБЩО ЗА ПЛАЩАНЕ: {value} €": ("TOTAL PAYABLE: {value} €", "ZU ZAHLENDER GESAMTBETRAG: {value} €",
                                   "TOTAL À PAYER : {value} €", "TOTAL A PAGAR: {value} €",
                                   "ΣΥΝΟΛΟ ΠΛΗΡΩΤΕΟ: {value} €", "UKUPNO ZA PLAĆANJE: {value} €",
                                   "TOTAL DE PLATĂ: {value} €", "RAZEM DO ZAPŁATY: {value} €",
                                   "РАЗОМ ДО СПЛАТИ: {value} €", "ИТОГО К ОПЛАТЕ: {value} €",
                                   "УКУПНО ЗА ПЛАЋАЊЕ: {value} €",
                                   "ÖDENECEK TOPLAM: {value} €"),
    "Условия на офертата:\n": ("Offer terms:\n", "Angebotsbedingungen:\n", "Conditions de l'offre :\n",
                               "Condiciones de la oferta:\n", "Όροι προσφοράς:\n", "Uvjeti ponude:\n",
                               "Condițiile ofertei:\n", "Warunki oferty:\n", "Умови пропозиції:\n",
                               "Условия предложения:\n", "Услови понуде:\n",
                               "Teklif koşulları:\n"),
    "1. Всички цени са посочени в евро (€) без включен ДДС.": (
        "1. All prices are in euro (€), excluding VAT.", "1. Alle Preise verstehen sich in Euro (€) ohne MwSt.",
        "1. Tous les prix sont indiqués en euros (€) hors TVA.", "1. Todos los precios se indican en euros (€) sin IVA.",
        "1. Όλες οι τιμές είναι σε ευρώ (€) χωρίς ΦΠΑ.", "1. Sve cijene izražene su u eurima (€) bez PDV-a.",
        "1. Toate prețurile sunt exprimate în euro (€), fără TVA.", "1. Wszystkie ceny podano w euro (€) bez VAT.",
        "1. Усі ціни вказано в євро (€) без ПДВ.", "1. Все цены указаны в евро (€) без НДС.",
        "1. Све цене су исказане у еврима (€) без ПДВ-а.",
        "1. Tüm fiyatlar Euro (€) cinsindendir, KDV hariçtir."),
    "2. Начин на плащане: 100% авансово плащане при потвърждение на поръчката.": (
        "2. Payment terms: 100% advance payment upon order confirmation.",
        "2. Zahlungsbedingungen: 100 % Vorauszahlung bei Auftragsbestätigung.",
        "2. Conditions de paiement : 100 % d'avance à la confirmation de la commande.",
        "2. Forma de pago: 100 % por adelantado al confirmar el pedido.",
        "2. Τρόπος πληρωμής: 100% προκαταβολή με την επιβεβαίωση της παραγγελίας.",
        "2. Način plaćanja: 100% avansno plaćanje pri potvrdi narudžbe.",
        "2. Modalitate de plată: 100% plată în avans la confirmarea comenzii.",
        "2. Warunki płatności: 100% przedpłaty przy potwierdzeniu zamówienia.",
        "2. Умови оплати: 100% передоплата при підтвердженні замовлення.",
        "2. Условия оплаты: 100% предоплата при подтверждении заказа.",
        "2. Начин плаћања: 100% авансно плаћање приликом потврде поруџбине.",
        "2. Ödeme şekli: Sipariş onayında %100 peşin ödeme."),
    "3. Срок за доставка: До 5 работни дни след постъпване на плащането.": (
        "3. Delivery time: up to 5 working days after receipt of payment.",
        "3. Lieferzeit: bis zu 5 Werktage nach Zahlungseingang.",
        "3. Délai de livraison : jusqu'à 5 jours ouvrés après réception du paiement.",
        "3. Plazo de entrega: hasta 5 días laborables tras la recepción del pago.",
        "3. Χρόνος παράδοσης: έως 5 εργάσιμες ημέρες μετά την είσπραξη της πληρωμής.",
        "3. Rok isporuke: do 5 radnih dana nakon primitka uplate.",
        "3. Termen de livrare: până la 5 zile lucrătoare de la primirea plății.",
        "3. Termin dostawy: do 5 dni roboczych od otrzymania płatności.",
        "3. Термін поставки: до 5 робочих днів після надходження оплати.",
        "3. Срок поставки: до 5 рабочих дней после поступления оплаты.",
        "3. Рок испоруке: до 5 радних дана након пријема уплате.",
        "3. Teslim süresi: Ödemenin alınmasından sonra en fazla 5 iş günü."),
    "4. Гаранция: 12 месеца за фабрични дефекти при спазване на инструкциите за работа.": (
        "4. Warranty: 12 months for manufacturing defects, provided the operating instructions are followed.",
        "4. Garantie: 12 Monate für Herstellungsfehler bei Einhaltung der Gebrauchsanleitung.",
        "4. Garantie : 12 mois pour les défauts de fabrication, sous réserve du respect des instructions d'utilisation.",
        "4. Garantía: 12 meses por defectos de fabricación, siempre que se respeten las instrucciones de uso.",
        "4. Εγγύηση: 12 μήνες για κατασκευαστικά ελαττώματα, εφόσον τηρούνται οι οδηγίες χρήσης.",
        "4. Jamstvo: 12 mjeseci za tvorničke nedostatke uz pridržavanje uputa za rad.",
        "4. Garanție: 12 luni pentru defecte de fabricație, cu respectarea instrucțiunilor de utilizare.",
        "4. Gwarancja: 12 miesięcy na wady fabryczne pod warunkiem przestrzegania instrukcji użytkowania.",
        "4. Гарантія: 12 місяців на заводські дефекти за умови дотримання інструкцій з експлуатації.",
        "4. Гарантия: 12 месяцев на заводские дефекты при соблюдении инструкции по эксплуатации.",
        "4. Гаранција: 12 месеци за фабричке недостатке уз поштовање упутстава за рад.",
        "4. Garanti: Kullanım talimatlarına uyulması koşuluyla üretim hatalarına karşı 12 ay."),
    "5. Забележка: В цената не са включени анкери, тапи, кофражно масло и пластмасови тръби.": (
        "5. Note: the price does not include anchors, plugs, release oil and plastic spacer tubes.",
        "5. Hinweis: Anker, Stopfen, Schalöl und Kunststoff-Distanzrohre sind im Preis nicht enthalten.",
        "5. Remarque : le prix n'inclut pas les ancrages, bouchons, huile de décoffrage et tubes d'écartement en plastique.",
        "5. Nota: el precio no incluye anclajes, tapones, aceite desencofrante ni tubos distanciadores de plástico.",
        "5. Σημείωση: Η τιμή δεν περιλαμβάνει αγκύρια, τάπες, λάδι ξυλοτύπων και πλαστικούς σωλήνες-αποστάτες.",
        "5. Napomena: cijena ne uključuje sidra, čepove, ulje za oplatu i plastične distancijske cijevi.",
        "5. Notă: prețul nu include ancore, dopuri, ulei de decofrare și tuburi distanțiere din plastic.",
        "5. Uwaga: cena nie obejmuje kotew, zatyczek, oleju szalunkowego ani plastikowych rurek dystansowych.",
        "5. Примітка: у ціну не входять анкери, заглушки, опалубне мастило та пластикові дистанційні трубки.",
        "5. Примечание: в цену не входят анкеры, заглушки, опалубочная смазка и пластиковые дистанционные трубки.",
        "5. Напомена: цена не обухвата анкере, чепове, уље за оплату и пластичне дистанционе цеви.",
        "5. Not: Ankrajlar, tapalar, kalıp yağı ve plastik mesafe boruları fiyata dahil değildir."),
    "6. Място на вземане: Склад на фирмата (Транспортът е за сметка на Купувача/Наемателя).": (
        "6. Collection point: the company warehouse (transport at the expense of the Buyer/Lessee).",
        "6. Abholort: Lager des Unternehmens (Transport zu Lasten des Käufers/Mieters).",
        "6. Lieu d'enlèvement : entrepôt de la société (transport à la charge de l'acheteur/du locataire).",
        "6. Lugar de recogida: almacén de la empresa (el transporte corre a cargo del comprador/arrendatario).",
        "6. Τόπος παραλαβής: Αποθήκη της εταιρείας (η μεταφορά βαρύνει τον Αγοραστή/Μισθωτή).",
        "6. Mjesto preuzimanja: skladište tvrtke (prijevoz na teret kupca/najmoprimca).",
        "6. Locul de ridicare: depozitul firmei (transportul este în sarcina cumpărătorului/chiriașului).",
        "6. Miejsce odbioru: magazyn firmy (transport na koszt kupującego/najemcy).",
        "6. Місце отримання: склад компанії (транспорт за рахунок покупця/орендаря).",
        "6. Место получения: склад компании (транспорт за счёт покупателя/арендатора).",
        "6. Место преузимања: магацин фирме (превоз на терет купца/закупца).",
        "6. Teslim alma yeri: Şirket deposu (nakliye Alıcıya/Kiracıya aittir)."),
    "С уважение,\n": ("Kind regards,\n", "Mit freundlichen Grüßen\n", "Cordialement,\n", "Atentamente,\n",
                      "Με εκτίμηση,\n", "S poštovanjem,\n", "Cu stimă,\n", "Z poważaniem\n", "З повагою,\n",
                      "С уважением,\n", "С поштовањем,\n", "Saygılarımızla,\n"),
    "Екипът на ТЕКО България ООД\nwww.tekoform.com": tuple(
        team + "\nwww.tekoform.com" for team in (
            "The TEKO Bulgaria Ltd. team", "Ihr Team der TEKO Bulgaria Ltd.", "L'équipe TEKO Bulgaria Ltd.",
            "El equipo de TEKO Bulgaria Ltd.", "Η ομάδα της TEKO Bulgaria Ltd.", "Tim TEKO Bulgaria Ltd.",
            "Echipa TEKO Bulgaria Ltd.", "Zespół TEKO Bulgaria Ltd.", "Команда TEKO Bulgaria Ltd.",
            "Команда TEKO Bulgaria Ltd.", "Тим TEKO Bulgaria Ltd.",
            "TEKO Bulgaria Ltd. ekibi")),
}

_TERMS_RE = re.compile("|".join(f"(?P<t{i}>{pattern})" for i, (pattern, _w) in enumerate(TERMS)), re.IGNORECASE)

assert all(len(v) == len(_ORDER) for v in TR.values()), [k for k, v in TR.items() if len(v) != len(_ORDER)]
assert all(len(words) == len(_ORDER) for _p, words in TERMS)
