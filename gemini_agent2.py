# gemini_agent2.py
import json
import google.generativeai as genai
from PIL import Image

def analyze_blueprint_with_agent2(image_input, api_key):
    """
    Втори Gemini Vision Агент: Сканира чертежа и извлича 
    структуриран списък от елементи за кофраж ТЕКО.
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = """
    Ти си главен инженер по кофражни системи ТЕКО. 
    Анализирай предоставения чертеж/план и извлечи следните елементи:
    - Колона (column)
    - Права Стена / Шайба (wall)
    - L-образна Стена / Шайба (l_wall)
    - П-образна Стена / Шайба (u_wall)

    За всеки намерен елемент върни JSON масив в следния СТРИКТЕН формат:
    [
      {
        "type": "column",
        "width_m": 0.40,
        "length_m": 0.40,
        "height_m": 2.80,
        "count": 5
      },
      {
        "type": "wall",
        "length_m": 6.00,
        "thickness_m": 0.25,
        "height_m": 3.00,
        "count": 1
      },
      {
        "type": "l_wall",
        "l1_m": 1.00,
        "l2_m": 2.00,
        "thickness_m": 0.30,
        "height_m": 2.80,
        "count": 5
      },
      {
        "type": "u_wall",
        "l1_m": 2.00,
        "l2_m": 3.00,
        "l3_m": 2.00,
        "thickness_m": 0.30,
        "height_m": 2.80,
        "count": 5
      }
    ]

    Върни САМО И ЕДИНСТВЕНО валиден JSON масив без допълнителни обяснения.
    """
    
    image = Image.open(image_input)
    response = model.generate_content([prompt, image])
    
    cleaned_text = response.text.strip()
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[7:]
    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3]
    cleaned_text = cleaned_text.strip()
    
    try:
        return json.loads(cleaned_text)
    except Exception as e:
        raise ValueError(f"Грешка при разчитане на данните от Gemini: {e}\nОтговор: {cleaned_text}")
