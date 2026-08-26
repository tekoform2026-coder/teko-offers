import pdfplumber
import re
import os
from teko_calculator import calculate_column, calculate_wall

def create_sample_pdf(filename="sample_drawing.pdf"):
    """Генерира примерен PDF файл със спецификация."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        
        c = canvas.Canvas(filename, pagesize=letter)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, 750, "ТЕКО - СПЕЦИФИКАЦИЯ НА КОФРАЖНИ ЕЛЕМЕНТИ")
        c.setFont("Helvetica", 10)
        c.drawString(100, 720, "Елемент | Ширина (m) | Дължина (m) | Височина (m) | Брой")
        c.drawString(100, 705, "-" * 60)
        c.drawString(100, 690, "Колона K1 | 0.40 | 0.40 | 3.00 | 4")
        c.drawString(100, 675, "Колона K2 | 0.50 | 0.50 | 3.00 | 2")
        c.drawString(100, 660, "Стена W1  | 0.25 | 6.00 | 3.00 | 1")
        c.save()
    except Exception:
        pass

def parse_pdf_elements(filename="sample_drawing.pdf", default_height=3.00):
    """
    Универсален парсер за PDF чертежи.
    Декодира CAD CID шрифтове, разпознава размери '04 04' (40x40) и стандартни надписи.
    """
    print(f"[PDF Parser] Сканиране на PDF файла: '{filename}'...")
    
    if not os.path.exists(filename):
        print(f"[!] Файлът '{filename}' не беше намерен.")
        return []

    found_dimensions = []

    try:
        with pdfplumber.open(filename) as pdf:
            for page in pdf.pages:
                raw_text = page.extract_text() or ""
                
                if not raw_text.strip():
                    words = page.extract_words()
                    raw_text = " ".join([w['text'] for w in words])

                # 1. Замяна на CAD CID шрифтове с разделител "x"
                clean_text = re.sub(r'\(cid:\d+\)', ' x ', raw_text)
                clean_text = clean_text.replace('х', 'x').replace('Х', 'x').replace('×', 'x').replace('/', 'x')

                # 2. Сканиране за шаблони с "x" (напр. 40x40, 0.40x0.40)
                dim_matches = re.findall(r'(\d+[\.,]?\d*)\s*x\s*(\d+[\.,]?\d*)', clean_text, re.IGNORECASE)

                for m in dim_matches:
                    try:
                        v1_str, v2_str = m[0].replace(',', '.'), m[1].replace(',', '.')
                        
                        # Декодиране на CAD формат '04' -> 0.40m
                        v1 = 0.40 if (v1_str == '04' or v1_str == '4') else float(v1_str)
                        v2 = 0.40 if (v2_str == '04' or v2_str == '4') else float(v2_str)

                        if v1 >= 50: v1 /= 1000.0
                        elif 10 <= v1 < 50: v1 /= 100.0

                        if v2 >= 50: v2 /= 1000.0
                        elif 10 <= v2 < 50: v2 /= 100.0

                        if 0.15 <= v1 <= 25.0 and 0.15 <= v2 <= 25.0:
                            found_dimensions.append((round(min(v1, v2), 3), round(max(v1, v2), 3)))
                    except Exception:
                        continue

                # 3. Допълнително засичане на сдвоени CAD размери (напр. "04 04" -> 0.40x0.40m)
                cid_pairs = re.findall(r'\b(0[4-9]|[1-9]\d)\s+(0[4-9]|[1-9]\d)\b', raw_text)
                for p1, p2 in cid_pairs:
                    try:
                        v1 = float(p1) / 10.0 if p1.startswith('0') else float(p1) / 100.0 if float(p1) >= 10 else float(p1)
                        v2 = float(p2) / 10.0 if p2.startswith('0') else float(p2) / 100.0 if float(p2) >= 10 else float(p2)

                        if 0.15 <= v1 <= 25.0 and 0.15 <= v2 <= 25.0:
                            found_dimensions.append((round(min(v1, v2), 3), round(max(v1, v2), 3)))
                    except Exception:
                        continue

    except Exception as e:
        print(f"[!] Грешка при парсиране на PDF: {e}")
        return []

    if not found_dimensions:
        print(f"[!] Не бяха намерени размери в '{filename}'.")
        return []

    # 4. Премахване на дублирани засичания от двата метода и групиране
    dim_counts = {}
    for dim in found_dimensions:
        dim_counts[dim] = dim_counts.get(dim, 0) + 1

    elements = []
    for (w_val, l_val), count in dim_counts.items():
        if l_val / w_val <= 3.0:
            elem = calculate_column(width_m=w_val, length_m=l_val, height_m=default_height, count=count)
        else:
            elem = calculate_wall(length_m=l_val, thickness_m=w_val, height_m=default_height, count=count)
        elements.append(elem)

    print(f"[PDF Parser] Успешно намерени {sum(dim_counts.values())} конструктивни елемента от чертежа.")
    return elements

if __name__ == "__main__":
    import sys
    test_file = sys.argv[1] if len(sys.argv) > 1 else "sample_drawing.pdf"
    parse_pdf_elements(test_file)