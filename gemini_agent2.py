import io
import json
import re
import time
from PIL import Image
from google import genai  # новият пакет google-genai (старият google-generativeai е без поддръжка)
from google.genai import types

# Предупреждение, когато отговорът на Gemini е отрязан (стигнал е ограничението на дължината)
TRUNCATED_NOTE = ("Отговорът на Gemini е отрязан - чертежът е твърде голям. Разделете го на части или "
                  "опитайте с по-малко страници.")

# Езикът на бележките ("notes") - езикът на екрана в app.py (потребителят, 18.11.2026); иначе Gemini пише
# на езика на чертежа (напр. македонски)
NOTES_LANGUAGES = {"bg": "български", "en": "английски (English)"}   # „на английски (English) език“


def _is_max_tokens(response):
    """Gemini е спрял отговора, защото е стигнал ограничението на дължината."""
    try:
        reason = response.candidates[0].finish_reason
    except (AttributeError, IndexError, TypeError):
        return False
    return getattr(reason, "name", reason) == "MAX_TOKENS" or reason == 2


def _salvage_truncated(raw_text):
    """Отрязан JSON: полетата преди "elements" и всички цели елементи до мястото на отрязване;
    (данни, текстът след последния цял елемент)."""
    start = raw_text.find('{')
    found = re.search(r'"elements"\s*:\s*\[', raw_text)
    if start == -1 or not found:
        return None
    decoder = json.JSONDecoder()
    elements, pos = [], found.end()
    while True:
        while pos < len(raw_text) and raw_text[pos] in " \t\r\n,":
            pos += 1
        if pos >= len(raw_text) or raw_text[pos] != '{':
            break
        try:
            element, pos = decoder.raw_decode(raw_text, pos)
        except json.JSONDecodeError:
            break  # последният елемент е отрязан
        elements.append(element)
    try:
        head = json.loads(raw_text[start:found.start()].rstrip().rstrip(',') + '}')
    except json.JSONDecodeError:
        head = {}
    head["elements"] = elements
    return head, raw_text[pos:].strip()

# Една заявка към Gemini е до ~20 MB (с base64); над това - качване през File API
INLINE_MAX_MB = 18

# Размерите - както са на чертежа, с мерната единица (потребителят, 20.11.2026); в см ги превръща програмата
UNIT_TO_CM = {"mm": 0.1, "cm": 1, "m": 100}
DIMENSION_FIELDS = ("thickness", "l1", "l2", "l3", "height", "thickness1", "thickness2", "thickness3")


def _to_cm(elements):
    """Размерите на всеки елемент от неговата мерна единица ("unit") в см: thickness -> thickness_cm ...
    Без единица - см (както преди)."""
    for element in elements:
        if not isinstance(element, dict):
            continue
        factor = UNIT_TO_CM.get(str(element.pop("unit", None) or "cm").strip().lower(), 1)
        for field in DIMENSION_FIELDS:
            if field not in element:
                continue
            value = element.pop(field)
            try:
                element[f"{field}_cm"] = None if value is None else round(float(value) * factor, 2)
            except (TypeError, ValueError):
                element[f"{field}_cm"] = None
    return elements


def _response_schema():
    """Видът на отговора (потребителят, 20.11.2026): типът - само от петте, размерите - числа или null.
    Редът на полетата - името и бележките преди елементите (при отрязан отговор се пазят)."""
    S, T = types.Schema, types.Type
    number = S(type=T.NUMBER, nullable=True)
    flag = S(type=T.BOOLEAN, nullable=True)
    element_fields = {
        "type": S(type=T.STRING, enum=["column", "wall", "l_wall", "u_wall", "t_wall"]),
        "name": S(type=T.STRING),
        "count": S(type=T.INTEGER),
        "unit": S(type=T.STRING, enum=list(UNIT_TO_CM)),
        "thickness": number, "l1": number, "l2": number, "l3": number, "height": number,
        "thickness1": number, "thickness2": number, "thickness3": number,
        "closed_end_1": flag, "closed_end_2": flag, "closed_end_3": flag,
        "source": S(type=T.STRING, nullable=True),
    }
    element = S(type=T.OBJECT, properties=element_fields, required=["type", "name", "count"],
                property_ordering=list(element_fields))
    return S(type=T.OBJECT,
             properties={"project_name": S(type=T.STRING, nullable=True),
                         "notes": S(type=T.ARRAY, items=S(type=T.STRING)),
                         "elements": S(type=T.ARRAY, items=element)},
             required=["notes", "elements"],
             property_ordering=["project_name", "notes", "elements"])


def _open_image(image_input):
    if isinstance(image_input, Image.Image):
        return image_input
    return Image.open(image_input)


def analyze_blueprint(image_input, api_key, model_choice=None, notes_language="bg", pdf_bytes=None,
                      double_check=False):
    # pdf_bytes: PDF-ът направо (с текстовия слой - кóтите се четат като текст); тогава без изображения
    # double_check: второ разчитане и сравнение - разликите в "double_check" (за бележките в app.py)
    # Едно изображение или списък (всички страници на PDF-а)
    if pdf_bytes:
        images = []
    elif isinstance(image_input, (list, tuple)):
        images = [_open_image(i) for i in image_input]
    else:
        images = [_open_image(image_input)]

    client = genai.Client(api_key=api_key)

    prompt = """
    Получаваш ЕДИН чертеж - PDF файл или изображенията на страниците му (може да е една страница); пред
    всяко изображение е номерът на страницата („Страница N:“). Прегледай ВСИЧКИ страници -
    таблици, планове, разрези, странични изгледи, детайли - и събери данните за всеки елемент от тях.
    Разпознай бетонните елементи, които се изливат във вертикален кофраж: колони, прави стени, L-образни,
    U-образни и T-образни стени, както и ниски правоъгълни бетонни блокове (баласти, фундаментни блокове,
    цокли и подобни).
    НЕ включвай: стоманени профили и конструкции (стойки, колове/piles, posts, греди, рейки/rails, подпори/
    struts, връзки), арматура, анкери, болтове, сглобяеми и готови елементи, панели, оборудване.

    Върни САМО валиден JSON обект (без образец - всички стойности са от чертежа):
    - "project_name" - името на обекта / проекта от чертежа;
    - "notes" - кратка бележка за всяко противоречие или несигурност в чертежа;
    - "elements" - за всеки елемент: "type" (column, wall, l_wall, u_wall, t_wall), "name", "count", "unit",
      размерите "thickness", "l1", "l2", "l3", "height", "thickness1", "thickness2", "thickness3",
      затворените краища "closed_end_1", "closed_end_2", "closed_end_3" и "source" - значенията им са по-долу.

    Инструкции за размерите:
    - Мерна единица: пиши числата ТОЧНО както са на чертежа и НЕ ги преобразувай в други единици - програмата
      го прави сама. В "unit" за всеки елемент посочи мерната единица на неговите размери: "mm", "cm" или "m"
      (често е посочена в бележките на чертежа, напр. „measurement unit: millimeters (mm)“, или личи от числата:
      стена 2500 / 250 - mm; 250 / 25 - cm; 2,50 / 0,25 - m). Всички размери на един елемент са в една единица;
      ако някой е даден в друга (напр. височина от кота в m при план в mm), преобразувай само него в единицата
      на елемента и го запиши в "notes".
    - Височина ("height") е вертикалният размер на елемента - взима се от разрез или страничен изглед
      (side view, section). Дължина и дебелина са размерите в план (изглед отгоре, top view, plan).
    - Запис от три числа като „350*2200*1000mm“ или „350x2200x1000“ НЕ е в определен ред. Намери в чертежа
      кое от трите числа е вертикално (височината) - напр. в страничния изглед 350 е отбелязано вертикално,
      значи "height" = 350, а 2200 x 1000 в изгледа отгоре са дължината (2200) и дебелината (1000), "unit" = "mm".
      Ако никъде не се вижда кое е височината, остави "height" = null и го запиши в "notes".
    - За "column" (колона): "l1" = по-дългата страна в план, "thickness" = по-късата, "height".
    - За "wall" (права стена): "l1" = дължината, "thickness" = дебелината, "height".
    - Нисък правоъгълен бетонен блок (баласт, фундаментен блок и т.н.) е "wall": "l1" = по-дългият размер
      в план, "thickness" = по-късият размер в план, "height" = вертикалният размер.
    - Дължините на стените на "l_wall", "u_wall" и "t_wall" са ВЪНШНИ - по външното лице, от външния ъгъл до
      края на стената (L-стена 3000 x 2500 mm с дебелина 250: стена A = 3000 по външното лице, не 2750 по
      вътрешното и не 2875 по оста). Ако на чертежа размерът е по оста или по вътрешното лице, преобразувай го
      във външен (по оста: + половината дебелина на перпендикулярната стена при всеки ъгъл; по вътрешното лице:
      + цялата ѝ дебелина) и го запиши в "notes".
    - За "l_wall" (L-образна стена): "l1" = стена A, "l2" = стена B - двете стени от външния ъгъл до края
      си; "thickness", "height".
    - За "u_wall" (U-образна / П-образна стена): "l1" = стена A (едното рамо, от външния ъгъл до края му),
      "l2" = стена B - ГЪРБЪТ (средната стена, цялата външна дължина между двата външни ъгъла), "l3" =
      стена C (другото рамо, от външния ъгъл до края му); "thickness", "height".
    - За "t_wall" (T-образна стена - стена, която започва от средата или от друго място по дължината на
      друга стена и образува буквата T; върни я като един елемент "t_wall", а не като две отделни стени,
      дори когато реброто е близо до края на полката): задай "l1" = цялата дължина
      на напречната стена (полката), "l2" = дължината на перпендикулярната стена (реброто) от предното лице
      на полката (откъм реброто) до края на реброто - ако полката е с различна дебелина вляво и вдясно от
      реброто, до предното лице на ПО-ТЪНКАТА част; "thickness", "height". "l3" = мястото на реброто:
      разстоянието от левия
      край на полката до лявото (по-близкото) лице на реброто, като стената се гледа с полката отгоре и
      реброто надолу. Ако реброто е в средата на полката или мястото не се вижда ясно, "l3" = 0 -
      не го отгатвай.
    - Дебелина на стените (само за "l_wall", "u_wall" и "t_wall"): ако стените на елемента са с РАЗЛИЧНА
      дебелина, задай "thickness1" (стена A, l1), "thickness2" (стена B, l2) и при "u_wall"
      "thickness3" (стена C, l3). При "t_wall": "thickness1" = полката вдясно от реброто (или цялата
      полка), "thickness2" = реброто, "thickness3" = частта от полката ВЛЯВО от реброто (от левия край
      до реброто), само ако е с различна дебелина от дясната част, иначе null.
      "thickness" е дебелината на стена A. Ако всички стени са с еднаква дебелина, или при колона и права
      стена, остави "thickness1", "thickness2" и "thickness3" = null.
    - Неизползваните полета за типа са null (не 0).

    Свързани стени - как се делят на елементи:
    - Стени, които се свързват под прав ъгъл, давай като ЕДИН елемент, когато формата е от типовете по-горе
      ("l_wall", "u_wall", "t_wall").
    - Когато не може да е един елемент от тези типове (напр. кръстовище +, повече от три свързани стени, стени
      под ъгъл, различен от 90°, колона, вградена в стената или изпъкнала от нея), раздели ги на НАЙ-МАЛКО
      елементи от петте типа (прави стени, колони, L, U, T). Краищата, с които те опират един в друг, са
      затворени = false (виж „Затворени краища“). Запиши в "notes", че тези елементи са свързани / едно до друго
      и могат да се изливат заедно, напр. „W3 и K2 са свързани - колоната е изпъкнала от стената“.

    Отвори в стените (врати, прозорци, проходи): НЕ дели стената заради отвора - давай я цяла с пълната ѝ
    дължина. За всеки отвор запиши бележка в "notes": името на стената, ширина x височина на отвора и
    мястото му, напр. „W3: отвор 900 x 2100 mm на 2000 mm от левия край“.
    - Ако някой размер не се вижда в чертежа, остави го null - НЕ го отгатвай и не слагай 0. Програмата ще
      поиска от потребителя да го попълни (празната височина се попълва със стандартната височина на етажа).

    Инструкции за броя ("count"):
    - "count" е броят еднакви елементи от този вид (от таблица с количества, спецификация или преброяване).
    - Ако за един и същ елемент има няколко колони или ревизии с бройки (напр. „Actual“ и „Revised“), вземи
      най-новата (Revised) и го запиши в "notes".
    - Ако един и същ тип елемент (едно име) се среща в няколко реда на таблица с еднакви размери, събери го
      в един елемент с общия брой.
    - Ако размерите на един елемент се различават в две таблици или изгледи, вземи тези от подробния чертеж
      на елемента (с размерни линии) и запиши противоречието в "notes".
    - Ако планът е типов етаж за няколко етажа (напр. „етажи 2-5“), НЕ умножавай броя по етажите - "count"
      е броят в чертежа; запиши в "notes" за колко етажа е планът.

    Затворени краища ("closed_end_1", "closed_end_2", "closed_end_3"):
    - true - свободен край на стената (там е нужно чело на кофража); false - краят опира в друг бетонен
      елемент (стена, колона), т.е. там няма чело; null - не се вижда ясно (програмата го смята за свободен).
    - Кой край е кой: "wall" - "closed_end_1" е десният край, "closed_end_2" - левият (както се гледа планът);
      "l_wall" - краят на стена A и краят на стена B; "u_wall" - краят на стена A и краят на стена C;
      "t_wall" - десният и левият край на полката, "closed_end_3" - краят на реброто. За "column" и за
      краищата, които типът няма, - null.

    Откъде е елементът ("source"): кратко - страницата и мястото в чертежа (оси, таблица, изглед), напр.
    „стр. 2, оси А-Б / 1-3“ или „стр. 1, таблица с колоните“; пиши го на езика на "notes".
    """
    prompt += (f'\n    Пиши всички "notes" на {NOTES_LANGUAGES.get(notes_language, NOTES_LANGUAGES["bg"])} език, '
               'независимо от езика на чертежа. Имената на елементите ("name") оставяй както са в чертежа.\n')

    # Стандартен списък с резервни модели
    fallback_models = [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash"
    ]

    candidate_models = []
    
    # Ако има избран модел от падащото меню, той застава твърдо на първо място
    if model_choice:
        candidate_models.append(model_choice)

    for m in fallback_models:
        if m not in candidate_models:
            candidate_models.append(m)

    try:
        for m in client.models.list():
            if 'generateContent' in (m.supported_actions or []):
                clean_name = m.name.replace('models/', '')
                if clean_name not in candidate_models:
                    candidate_models.append(clean_name)
    except Exception:
        pass

    raw_text = None
    last_error = None
    used_model = None
    truncated = False

    pages, uploaded = _prepare_pages(client, pdf_bytes, images)
    try:
        for model_name in candidate_models:
            try:
                response = _generate(client, model_name, pages, prompt)
                if response and response.text:
                    raw_text = response.text.strip()
                    used_model = model_name
                    truncated = _is_max_tokens(response)
                    break
            except Exception as e:
                last_error = e
                continue

        if not raw_text:
            raise Exception(f"Не можа да се осъществи връзка с Gemini API. Последна грешка: {last_error}")

        parsed_json = _parse_answer(raw_text, truncated)
        if double_check:   # второ разчитане със същия модел и сравнение (отметка, изключена по подразбиране)
            parsed_json["double_check"] = _second_reading(client, used_model, pages, prompt, parsed_json)
    finally:
        for file in uploaded:   # качените през File API - изтриват се веднага (иначе Google ги трие след 48 ч)
            try:
                client.files.delete(name=file.name)
            except Exception:
                pass
    parsed_json["file_api"] = bool(uploaded)
    return parsed_json, used_model


def _generate(client, model_name, pages, prompt):
    return client.models.generate_content(
        model=model_name,
        contents=[*pages, prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json",
                                           response_schema=_response_schema())
    )


def _prepare_pages(client, pdf_bytes, images):
    """Чертежът за заявката: PDF-ът или изображенията (PNG), пред всяко - „Страница N:“ (бележките и "source"
    казват откъде е размерът). Над ~18 MB в заявката (с base64) - качване през File API (т. 9, 20.11.2026);
    (части, качените файлове)."""
    if pdf_bytes:
        files = [("application/pdf", pdf_bytes)]
    else:
        files = []
        for image in images:
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            files.append(("image/png", buf.getvalue()))
    uploaded = []
    if sum(len(data) for _mime, data in files) * 4 / 3 > INLINE_MAX_MB * 1024 * 1024:
        parts = []
        for mime, data in files:
            file = client.files.upload(file=io.BytesIO(data), config=types.UploadFileConfig(mime_type=mime))
            uploaded.append(file)
            parts.append(_wait_active(client, file))
    else:
        parts = [types.Part.from_bytes(data=data, mime_type=mime) for mime, data in files]
    if pdf_bytes:
        return parts, uploaded
    pages = []
    for i, part in enumerate(parts, 1):
        pages += [f"Страница {i}:", part]
    return pages, uploaded


def _wait_active(client, file, timeout_s=120):
    """Качен файл - докато Google го обработи (PDF и картини - обикновено веднага)."""
    deadline = time.monotonic() + timeout_s
    while getattr(getattr(file, "state", None), "name", "ACTIVE") == "PROCESSING" and time.monotonic() < deadline:
        time.sleep(2)
        file = client.files.get(name=file.name)
    if getattr(getattr(file, "state", None), "name", "ACTIVE") == "FAILED":
        raise Exception(f"File API: Google не можа да обработи файла {file.name}")
    return file


def _second_reading(client, model_name, pages, prompt, first):
    """Двойна проверка: същият чертеж още веднъж със същия модел; разликите - списък от речници
    (kind: diff / only_first / only_second / failed), празен - съвпадат. Таблицата е от първото разчитане."""
    try:
        response = _generate(client, model_name, pages, prompt)
        second = _parse_answer(response.text.strip(), _is_max_tokens(response))
    except Exception as e:
        return [{"kind": "failed", "error": str(e)}]
    return _compare_readings(first.get("elements") or [], second.get("elements") or [])


COMPARED_FIELDS = ("count", "l1_cm", "thickness_cm", "l2_cm", "thickness2_cm", "l3_cm", "thickness3_cm",
                   "height_cm", "closed_end_1", "closed_end_2", "closed_end_3")


def _compare_readings(first, second):
    def by_key(elements):
        groups = {}
        for e in elements:
            if isinstance(e, dict):
                groups.setdefault((e.get("type"), str(e.get("name") or "?")), []).append(e)
        return groups

    def value(e, field):
        v = e.get(field)
        if field.startswith("closed_end"):
            return v is not False   # празно = затворен
        return v

    a, b = by_key(first), by_key(second)
    differences = []
    for key in list(dict.fromkeys([*a, *b])):
        list_a, list_b = a.get(key, []), b.get(key, [])
        for ea, eb in zip(list_a, list_b):
            for field in COMPARED_FIELDS:
                va, vb = value(ea, field), value(eb, field)
                same = (va == vb or (isinstance(va, (int, float)) and isinstance(vb, (int, float))
                                     and abs(va - vb) < 0.01))
                if not same:
                    differences.append({"kind": "diff", "name": key[1], "field": field, "first": va, "second": vb})
        differences += [{"kind": "only_first", "name": key[1]} for _ in list_a[len(list_b):]]
        differences += [{"kind": "only_second", "name": key[1]} for _ in list_b[len(list_a):]]
    return differences


def _parse_answer(raw_text, truncated):
    """Текстът на Gemini -> данни; размерите - в см."""
    start_idx = raw_text.find('{')
    end_idx = raw_text.rfind('}')

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = raw_text[start_idx:end_idx + 1]
    else:
        json_str = raw_text

    try:
        parsed_json = json.loads(json_str)
    except json.JSONDecodeError as e:
        # отрязан отговор: в таблицата влизат елементите до мястото на отрязване
        # (Gemini е спрял заради дължината или текстът свършва веднага след цял елемент)
        salvaged = _salvage_truncated(raw_text)
        if salvaged is None or not (truncated or not salvaged[1]):
            raise Exception(f"Грешка при обработка на JSON отговора: {e}\nПолучен текст: {raw_text[:200]}")
        parsed_json, truncated = salvaged[0], True

    if truncated:
        notes = parsed_json.get("notes") or []
        parsed_json["notes"] = [TRUNCATED_NOTE] + ([notes] if isinstance(notes, str) else list(notes))
    if isinstance(parsed_json.get("elements"), list):
        _to_cm(parsed_json["elements"])
    return parsed_json

def analyze_blueprint_with_agent2(image_input, api_key, model_choice=None, notes_language="bg"):
    res, _ = analyze_blueprint(image_input, api_key, model_choice=model_choice, notes_language=notes_language)
    return res
