import json
import re
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

def _open_image(image_input):
    if isinstance(image_input, Image.Image):
        return image_input
    return Image.open(image_input)


def analyze_blueprint(image_input, api_key, model_choice=None, notes_language="bg"):
    # Едно изображение или списък (всички страници на PDF-а)
    if isinstance(image_input, (list, tuple)):
        images = [_open_image(i) for i in image_input]
    else:
        images = [_open_image(image_input)]

    client = genai.Client(api_key=api_key)

    prompt = """
    Изображенията са страниците на ЕДИН чертеж (може да е една страница). Прегледай ВСИЧКИ страници -
    таблици, планове, разрези, странични изгледи, детайли - и събери данните за всеки елемент от тях.
    Разпознай бетонните елементи, които се изливат във вертикален кофраж: колони, прави стени, L-образни,
    U-образни и T-образни стени, както и ниски правоъгълни бетонни блокове (баласти, фундаментни блокове,
    цокли и подобни).
    НЕ включвай: стоманени профили и конструкции (стойки, колове/piles, posts, греди, рейки/rails, подпори/
    struts, връзки), арматура, анкери, болтове, сглобяеми и готови елементи, панели, оборудване.

    Върни САМО валиден JSON обект със следната структура:

    {
      "project_name": "Име на обект/проект от чертежа",
      "notes": ["кратка бележка за всяко противоречие или несигурност в чертежа"],
      "elements": [
        {
          "type": "wall",
          "name": "Ballast A",
          "count": 1,
          "thickness_cm": 100,
          "l1_cm": 220,
          "l2_cm": null,
          "l3_cm": null,
          "height_cm": 35,
          "thickness1_cm": null,
          "thickness2_cm": null,
          "thickness3_cm": null
        }
      ]
    }

    Инструкции за размерите:
    - Всички размери са в САНТИМЕТРИ (см). Провери мерната единица на чертежа (често е посочена в бележките,
      напр. „measurement unit: millimeters (mm)“) и преобразувай: 2200 mm -> 220, 5 м -> 500.
    - Височина ("height_cm") е вертикалният размер на елемента - взима се от разрез или страничен изглед
      (side view, section). Дължина и дебелина са размерите в план (изглед отгоре, top view, plan).
    - Запис от три числа като „350*2200*1000mm“ или „350x2200x1000“ НЕ е в определен ред. Намери в чертежа
      кое от трите числа е вертикално (височината) - напр. в страничния изглед 350 е отбелязано вертикално,
      значи височината е 35 см, а 2200 x 1000 в изгледа отгоре са дължината (220) и дебелината (100).
      Ако никъде не се вижда кое е височината, остави "height_cm" = null и го запиши в "notes".
    - За "column" (колона): "l1_cm" = по-дългата страна в план, "thickness_cm" = по-късата, "height_cm".
    - За "wall" (права стена): "l1_cm" = дължината, "thickness_cm" = дебелината, "height_cm".
    - Нисък правоъгълен бетонен блок (баласт, фундаментен блок и т.н.) е "wall": "l1_cm" = по-дългият размер
      в план, "thickness_cm" = по-късият размер в план, "height_cm" = вертикалният размер.
    - За "l_wall" (L-образна стена): задай "l1_cm", "l2_cm", "thickness_cm", "height_cm".
    - За "u_wall" (U-образна стена): задай "l1_cm", "l2_cm", "l3_cm", "thickness_cm", "height_cm".
    - За "t_wall" (T-образна стена - стена, която започва от средата или от друго място по дължината на
      друга стена и образува буквата T; върни я като един елемент "t_wall", а не като две отделни стени,
      дори когато реброто е близо до края на полката): задай "l1_cm" = цялата дължина
      на напречната стена (полката), "l2_cm" = дължината на перпендикулярната стена (реброто) от полката
      до края ѝ, "thickness_cm", "height_cm". "l3_cm" = мястото на реброто: разстоянието в см от левия
      край на полката до лявото (по-близкото) лице на реброто, като стената се гледа с полката отгоре и
      реброто надолу. Ако реброто е в средата на полката или мястото не се вижда ясно, "l3_cm" = 0 -
      не го отгатвай.
    - Дебелина на рамената (само за "l_wall", "u_wall" и "t_wall"): ако рамената на елемента са с РАЗЛИЧНА
      дебелина, задай "thickness1_cm" (рамо 1, l1_cm), "thickness2_cm" (рамо 2, l2_cm) и при "u_wall"
      "thickness3_cm" (рамо 3, l3_cm); при "t_wall" рамо 1 е полката, рамо 2 - реброто, "thickness3_cm" = null.
      "thickness_cm" е дебелината на рамо 1. Ако всички рамена са с еднаква дебелина, или при колона и права
      стена, остави "thickness1_cm", "thickness2_cm" и "thickness3_cm" = null.
    - Неизползваните полета за типа са null (не 0).
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

    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[*images, prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
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
    return parsed_json, used_model

def analyze_blueprint_with_agent2(image_input, api_key, model_choice=None, notes_language="bg"):
    res, _ = analyze_blueprint(image_input, api_key, model_choice=model_choice, notes_language=notes_language)
    return res
