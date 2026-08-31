import json
from PIL import Image
import google.generativeai as genai

def analyze_blueprint(image_input, api_key):
    """
    Разчита чертежа чрез автоматично откриване на наличните Gemini модели за API ключа.
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
    Върни САМО чист JSON обект (без markdown, без ```json, без допълнителен текст) със следната структура:

    {
      "project_name": "Име на обект/проект от чертежа",
      "elements": [
        {
          "type": "column" или "wall" или "l_wall" или "u_wall",
          "name": "Маркировка (напр. К1, Ш1, W1)",
          "count": брой_елементи,
          "width_m": ширина_в_метри,
          "length_m": дължина_в_метри,
          "thickness_m": дебелина_на_стена_в_метри,
          "l1_m": дължина_рамо_1_в_метри,
          "l2_m": дължина_рамо_2_в_метри,
          "l3_m": дължина_рамо_3_в_метри,
          "height_m": височина_в_метри
        }
      ]
    }

    Инструкции за размерите:
    - За "column": задай "width_m" (напр. 0.30), "length_m" (напр. 0.50), "height_m" (напр. 3.0).
    - За "wall" (права стена): задай "length_m" (напр. 5.0), "thickness_m" (напр. 0.25), "height_m" (напр. 3.0).
    - За "l_wall" (L-образна стена): задай "l1_m", "l2_m", "thickness_m", "height_m".
    - За "u_wall" (U-образна стена): задай "l1_m", "l2_m", "l3_m", "thickness_m", "height_m".
    - Ако някоя стойност липсва, сложи разумно отгатната стойност (напр. height_m=3.0, thickness_m=0.25).
    """

    # 1. Автоматично извличане на поддържаните от вашия акаунт модели
    candidate_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                candidate_models.append(m.name)
    except Exception:
        pass

    # 2. Добавяне на стандартните наименования като резервен вариант
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

    text = None
    last_error = None

    # 3. Обхождане на откритите модели до първия успешен отговор
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([img, prompt])
            if response and response.text:
                text = response.text.strip()
                break
        except Exception as e:
            last_error = e
            continue

    if not text:
        raise Exception(f"Не можа да се осъществи връзка с Gemini API. Последна грешка: {last_error}")

    # Изчистване на евентуални форматиращи тагове
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    return json.loads(text.strip())

def analyze_blueprint_with_agent2(image_input, api_key):
    return analyze_blueprint(image_input, api_key)
