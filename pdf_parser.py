import pdfplumber
import re
import os
from teko_calculator import layout_element, count_panels
from accessories_calculator import calculate_accessories

# Не се ползва от app.py (там чертежите се разчитат с Gemini); поддържа се актуален по правилата в CLAUDE.md:
# размерите в см, разположението и аксесоарите - от layout_element() и calculate_accessories().
DEFAULT_HEIGHT_CM = 270  # стандартната височина, както в app.py


def _column_element(a_cm, b_cm, height_cm, count):
    """Колона: страна A = дължината (стена A), страна B = дебелината - както в app.py."""
    layout = layout_element("column", height_cm, width_cm=a_cm, length_cm=b_cm)
    acc = calculate_accessories("column", a_cm, b_cm, height_cm, layout["faces"][0]["rows"][0],
                                layout["height_levels"], layout=layout)
    return {
        "type": "Колона",
        "dimensions": f"{a_cm:g}x{b_cm:g} см, H={height_cm:g} см",   # A x B, както на чертежа
        "count": count,
        "area_m2": round(2 * (a_cm + b_cm) * height_cm / 10000.0 * count, 2),
        "panels_spec": count_panels(layout, count),
        "accessories": {code: qty * count for code, qty in acc["bom_summary"].items()},
    }


def _wall_element(length_cm, thickness_cm, height_cm, count):
    """Права стена: двата края затворени (по подразбиране, както в таблицата на app.py)."""
    layout = layout_element("wall", height_cm, length_cm=length_cm, thickness_cm=thickness_cm,
                            closed_end_1=True, closed_end_2=True)
    acc = calculate_accessories("wall", length_cm, thickness_cm, height_cm, layout["faces"][0]["rows"][0],
                                layout["height_levels"], layout=layout)
    return {
        "type": "Права Стена / Шайба",
        "dimensions": f"L={length_cm:g} см, B={thickness_cm:g} см, H={height_cm:g} см",
        "count": count,
        "area_m2": round(2 * length_cm * height_cm / 10000.0 * count, 2),   # площта - както в офертата
        "panels_spec": count_panels(layout, count),
        "accessories": {code: qty * count for code, qty in acc["bom_summary"].items()},
    }

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

def parse_pdf_elements(filename="sample_drawing.pdf", default_height_cm=DEFAULT_HEIGHT_CM):
    """
    Универсален парсер за PDF чертежи.
    Декодира CAD CID шрифтове, разпознава размери '04 04' (40x40) и стандартни надписи.
    Връща елементите (колони и прави стени) с размери в см, панели и аксесоари по сегашните правила.
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
        w_cm, l_cm = round(w_val * 100, 1), round(l_val * 100, 1)   # засечените размери са в m
        if l_val / w_val <= 3.0:
            elem = _column_element(l_cm, w_cm, default_height_cm, count)
        else:
            elem = _wall_element(l_cm, w_cm, default_height_cm, count)
        elements.append(elem)

    print(f"[PDF Parser] Успешно намерени {sum(dim_counts.values())} конструктивни елемента от чертежа.")
    return elements

if __name__ == "__main__":
    import sys
    test_file = sys.argv[1] if len(sys.argv) > 1 else "sample_drawing.pdf"
    parse_pdf_elements(test_file)
