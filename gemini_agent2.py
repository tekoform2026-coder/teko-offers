import json
from PIL import Image
import google.generativeai as genai

def analyze_blueprint(image_input, api_key):
    """
    Разчита чертежа чрез Gemini и автоматично извлича и парсва JSON отговора.
    """
    if isinstance(image_input, Image.Image):
        img = image_input
    elif hasattr(image_input, 'read'):
        img = Image.open(image_input)
    else:
        img = Image.open(image_input)

    # Конфигуриране на Google SDK
    genai.configure(api_key=api_key)

    prompt = """
    Анализирай чертежа/плана и разпознай всички конструктивни елементи (колони, прави стени, L-образни стени, U-образни стени).
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

    Инструкции за размерите:
    - За "column" (колона): задай "width_m", "length_m", "height_m".
    - За "wall" (права стена): задай "length_m", "thickness_m", "height_m".
    - За "l_wall" (L-образна стена): задай "l1_m", "l2_m", "thickness_m", "height_m".
    - За "u_wall" (U-образна стена): задай "l1_m", "l2_m", "l3_m", "thickness_m", "height_m".
    - Ако някоя стойност липсва, сложи разумно отгатната стойност (напр. height_m=3.0, thickness_m=0.25).
    """

    # 1. Извличане на поддържаните от акаунта модели
    candidate_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                candidate_models.append(m.name)
    except Exception:
        pass

    fallback_list = [
        'gemini-1.5-flash',
        'gemini-1.5-flash-001',
        'gemini-1.5-flash-002',
        'gemini-2.0-flash',
        'gemini-1.5-pro',
        'models/gemini-1.5-flash',
        'models/gemini-1.5-flash-001'
    ]

    for f_model in fallback_list:
        if f_model not in candidate_models:
            candidate_models.append(f_model)

    raw_text = None
    last_error = None

    # 2. Опит с откритите модели с форсиране на JSON формат
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={"response_mime_type": "application/json"}
            )
            response = model.generate_content([img, prompt])
            if response and response.text:
                raw_text = response.text.strip()
                break
        except Exception as e:
            last_error = e
            continue

    if not raw_text:
        raise Exception(f"Не можа да се осъществи връзка с Gemini API или отговорът бе празен. Последна грешка: {last_error}")

    # 3. Безопасно извличане само на JSON блока { ... }
    start_idx = raw_text.find('{')
    end_idx = raw_text.rfind('}')

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = raw_text[start_idx:end_idx + 1]
    else:
        json_str = raw_text

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise Exception(f"Грешка при обработка на JSON отговора от Gemini: {e}\nПолучен текст: {raw_text[:200]}")

def analyze_blueprint_with_agent2(image_input, api_key):
    return analyze_blueprint(image_input, api_key)
