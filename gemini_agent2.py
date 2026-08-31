import google.generativeai as genai
from PIL import Image
import json

def analyze_blueprint_with_agent2(image_input, api_key):
    # Автоматично разпознаване дали е предадено PIL изображение или файл
    if isinstance(image_input, Image.Image):
        img = image_input
    elif hasattr(image_input, 'read'):
        img = Image.open(image_input)
    else:
        img = image_input

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

    prompt = """
    Анализирай чертежа/плана и разпознай всички конструктивни елементи (колони и стени).
    Върни САМО чист JSON масив (array) от обекти, без markdown форматиране, без ```json, без допълнителен текст.

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

    response = model.generate_content([img, prompt])
    
    # Изчистване на форматиращи тагове, ако Gemini върне съобщението в кодови блокове
    text = response.text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    return json.loads(text)
