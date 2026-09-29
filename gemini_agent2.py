import json
import google.generativeai as genai
from PIL import Image


def analyze_blueprint(image_input, api_key):
    # 1. Конвертиране в RGB и справяне със Streamlit файловия поток
    try:
        if isinstance(image_input, Image.Image):
            img = image_input
        elif hasattr(image_input, "read"):
            image_input.seek(0)
            img = Image.open(image_input)
        else:
            img = Image.open(image_input)

        if img.mode != "RGB":
            img = img.convert("RGB")
    except Exception as e:
        raise Exception(f"Грешка при зареждане на изображението: {e}")

    genai.configure(api_key=api_key)

    prompt = """
    Ти си опитен конструктор и инженер по кофражни системи.
    Анализирай внимателно предоставения чертеж/план и разпознай всички вертикални конструктивни елементи:
    - Колони ("column")
    - Прави стени ("wall")
    - L-образни стени ("l_wall")
    - U-образни стени / ядра ("u_wall")

    Върни САМО валиден JSON обект със следната структура:

    {
      "project_name": "Име на обект/проект от чертежа",
      "elements": [
        {
          "type": "column",
          "name": "К1",
          "count": 1,
          "width_m": 0.30,
          "length_m": 0.50,
          "thickness_m": 0.25,
          "l1_m": 0.0,
          "l2_m": 0.0,
          "l3_m": 0.0,
          "height_m": 3.0
        }
      ]
    }

    Инструкции за размерите (всички стойности в метри):
    - За "column" (колона): задай "width_m", "length_m", "height_m".
    - За "wall" (права стена): задай "length_m", "thickness_m", "height_m".
    - За "l_wall" (L-образна стена): задай "l1_m", "l2_m", "thickness_m", "height_m".
    - За "u_wall" (U-образна стена): задай "l1_m", "l2_m", "l3_m", "thickness_m", "height_m".
    - Прочети с най-висока точност цифрите от котите на чертежа. Ако някоя стойност липсва, сложи стандартна разумна стойност (напр. height_m=3.0, thickness_m=0.25).
    """

    # 2. Актуален списък с Gemini 3.x модели
    candidate_models = [
        "gemini-3.6-flash",  # Бърз и изключително прецизен за визуален анализ
        "gemini-3.1-pro",  # За по-сложни чертежи и детайлно логическо мислене
        "gemini-2.0-flash",
        "gemini-1.5-pro",
    ]

    raw_text = None
    last_error = None
    used_model = None

    # 3. Обхождане на моделите
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.1,
                },
            )
            response = model.generate_content([img, prompt])

            if response and response.text:
                raw_text = response.text.strip()
                used_model = model_name
                break
        except Exception as e:
            last_error = e
            continue

    if not raw_text:
        raise Exception(
            f"Не можа да се осъществи връзка с Gemini API. Последна грешка: {last_error}"
        )

    # 4. Валидиране и парсване на JSON отговора
    start_idx = raw_text.find("{")
    end_idx = raw_text.rfind("}")

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = raw_text[start_idx : end_idx + 1]
    else:
        json_str = raw_text

    try:
        parsed_json = json.loads(json_str)
        return parsed_json, used_model
    except json.JSONDecodeError as e:
        raise Exception(
            f"Грешка при обработка на JSON отговора: {e}\nПолучен текст: {raw_text[:200]}"
        )


def analyze_blueprint_with_agent2(image_input, api_key):
    res, _ = analyze_blueprint(image_input, api_key)
    return res
