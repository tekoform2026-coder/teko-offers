import json
from PIL import Image

def analyze_blueprint(image_input, api_key):
    """
    Разчита чертежа с автоматично превключване между поддържаните Gemini модели.
    """
    if isinstance(image_input, Image.Image):
        img = image_input
    elif hasattr(image_input, 'read'):
        img = Image.open(image_input)
    else:
        img = image_input

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

    models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-flash-latest']
    text = None
    last_error = None

    # 1. Опит с новия SDK google-genai
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[img, prompt],
                    config={'response_mime_type': 'application/json'}
                )
                text = response.text.strip()
                if text:
                    break
            except Exception as e:
                last_error = e
                continue
    except ImportError:
        pass

    # 2. Опит със класическия SDK google-generativeai при липса на новия SDK
    if not text:
        import google.generativeai as genai_old
        genai_old.configure(api_key=api_key)
        for model_name in models_to_try:
            try:
                model = genai_old.GenerativeModel(model_name)
                response = model.generate_content([img, prompt])
                text = response.text.strip()
                if text:
                    break
            except Exception as e:
                last_error = e
                continue

    if not text:
        raise Exception(f"Нито един модел не успя да се свърже. Последна грешка: {last_error}")

    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    return json.loads(text.strip())

def analyze_blueprint_with_agent2(image_input, api_key):
    return analyze_blueprint(image_input, api_key)
