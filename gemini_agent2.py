import json
from PIL import Image
import google.generativeai as genai

def analyze_blueprint(image_input, api_key, model_choice=None):
    if isinstance(image_input, Image.Image):
        img = image_input
    elif hasattr(image_input, 'read'):
        img = Image.open(image_input)
    else:
        img = Image.open(image_input)

    genai.configure(api_key=api_key)

    prompt = """
    Анализирай чертежа/плана и разпознай всички конструктивни елементи (колони, прави стени, L-образни стени, U-образни стени, T-образни стени).
    Върни САМО валиден JSON обект със следната структура:

    {
      "project_name": "Име на обект/проект от чертежа",
      "elements": [
        {
          "type": "column",
          "name": "К1",
          "count": 1,
          "width_cm": 30,
          "length_cm": 50,
          "thickness_cm": 25,
          "l1_cm": 0,
          "l2_cm": 0,
          "l3_cm": 0,
          "height_cm": 300
        }
      ]
    }

    Инструкции за размерите:
    - Всички размери са в САНТИМЕТРИ (см), напр. стена с дължина 5 м -> "length_cm": 500.
    - За "column" (колона): задай "width_cm", "length_cm", "height_cm".
    - За "wall" (права стена): задай "length_cm", "thickness_cm", "height_cm".
    - За "l_wall" (L-образна стена): задай "l1_cm", "l2_cm", "thickness_cm", "height_cm".
    - За "u_wall" (U-образна стена): задай "l1_cm", "l2_cm", "l3_cm", "thickness_cm", "height_cm".
    - За "t_wall" (T-образна стена - стена, която започва от средата на друга стена и образува буквата T;
      върни я като един елемент "t_wall", а не като две отделни стени): задай "l1_cm" = цялата дължина
      на напречната стена (полката), "l2_cm" = дължината на перпендикулярната стена (реброто) от полката
      до края ѝ, "thickness_cm", "height_cm"; "l3_cm" = 0.
    - Ако някоя стойност липсва, сложи разумно отгатната стойност (напр. height_cm=300, thickness_cm=25).
    """

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
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                clean_name = m.name.replace('models/', '')
                if clean_name not in candidate_models:
                    candidate_models.append(clean_name)
    except Exception:
        pass

    raw_text = None
    last_error = None
    used_model = None

    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={"response_mime_type": "application/json"}
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
        raise Exception(f"Не можа да се осъществи връзка с Gemini API. Последна грешка: {last_error}")

    start_idx = raw_text.find('{')
    end_idx = raw_text.rfind('}')

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = raw_text[start_idx:end_idx + 1]
    else:
        json_str = raw_text

    try:
        parsed_json = json.loads(json_str)
        return parsed_json, used_model
    except json.JSONDecodeError as e:
        raise Exception(f"Грешка при обработка на JSON отговора: {e}\nПолучен текст: {raw_text[:200]}")

def analyze_blueprint_with_agent2(image_input, api_key, model_choice=None):
    res, _ = analyze_blueprint(image_input, api_key, model_choice=model_choice)
    return res
