import json
from PIL import Image
from google import genai

def analyze_blueprint_with_agent2(image_input, api_key):
    client = genai.Client(api_key=api_key)

    # Проверка дали снимката вече е заредена като PIL обект
    if isinstance(image_input, Image.Image):
        img = image_input
    elif hasattr(image_input, 'read'):
        img = Image.open(image_input)
    else:
        img = image_input

    prompt = """
    Анализирай чертежа/плана и разпознай всички конструктивни елементи (колони и стени).
    Върни САМО чист JSON масив (array) от обекти, без markdown форматиране, без допълнителен текст.

    Всеки обект трябва да съдържа:
    - "type": един от следните видове: "column", "wall", "l_wall", "u_wall"
    - "count": брой на елементите (цяло число, напр. 1)
    
    За "column":
      - "width_m": ширина в метри (напр. 0.25)
      - "length_m": дължина в метри (напр. 0.50)
      - "height_m": височина в метри (напр. 3.0)

    За "wall" (права стена):
      - "length_m": дължина в метри (напр. 4.0)
      - "thickness_m": дебелина в метри (напр. 0.25)
      - "height_m": височина в метри (напр. 3.0)

    За "l_wall" (L-образна стена / ъгъл):
      - "l1_m": дължина на първото рамо в метри
      - "l2_m": дължина на второто рамо в метри
      - "thickness_m": дебелина в метри
      - "height_m": височина в метри

    За "u_wall" (U-образна стена):
      - "l1_m": дължина на първо рамо в метри
      - "l2_m": дължина на второ рамо в метри
      - "l3_m": дължина на трето рамо в метри
      - "thickness_m": дебелина в метри
      - "height_m": височина в метри

    Пример за валиден JSON изход:
    [
      {"type": "column", "count": 2, "width_m": 0.3, "length_m": 0.6, "height_m": 3.0},
      {"type": "wall", "count": 1, "length_m": 5.0, "thickness_m": 0.25, "height_m": 3.0}
    ]
    """

    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=[img, prompt],
        config={'response_mime_type': 'application/json'}
    )

    return json.loads(response.text)
