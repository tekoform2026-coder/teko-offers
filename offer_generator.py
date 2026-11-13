"""
Word оферта на ТЕКО България ООД.

Не се ползва от app.py - там е собствената функция generate_word_offer() (таб „Оферта“). Този файл се
поддържа като нейно копие, за да е актуален, ако някой ден се ползва: test_offer_generator_matches_app
проверява, че двете дават един и същ документ.
"""
import io

import docx
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls


def set_cell_background(cell, hex_color):
    """Задава цвят на фона на клетка от таблица."""
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)


def generate_word_offer(client_name, project_name, offer_date, offer_type, price_per_m2, detailed_rows, total_area, subtotal, vat_amount, grand_total):
    """
    Търговска оферта в Word (.docx) - същата като generate_word_offer() в app.py (със същите параметри).
    offer_type: текстът от таб „Оферта“ („Наем на кофраж ...“ / „Покупка на нов кофраж ...“);
    detailed_rows: редове с ключове „Елемент“, „Размери“ (в см), „Брой“, „Площ (m²)“, „Обща сума (€)“.
    Връща io.BytesIO с документа.
    """
    doc = docx.Document()
    
    for section in doc.sections:
        section.top_margin = Inches(0.7)
        section.bottom_margin = Inches(0.7)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    GREEN_COLOR = RGBColor(46, 125, 50)
    BLUE_COLOR = RGBColor(0, 51, 102)
    BLUE_HEX = "003366"

    is_sale = ("закуп" in offer_type.lower() or "продажба" in offer_type.lower())

    p_logo = doc.add_paragraph()
    p_logo.paragraph_format.space_before = Pt(0)
    p_logo.paragraph_format.space_after = Pt(2)
    r_logo = p_logo.add_run("TEKO")
    r_logo.bold = True
    r_logo.font.size = Pt(26)
    r_logo.font.color.rgb = GREEN_COLOR

    p_comp = doc.add_paragraph()
    p_comp.paragraph_format.space_after = Pt(12)
    p_comp.paragraph_format.line_spacing = 1.15

    r_comp = p_comp.add_run("ТЕКО България ООД | ЕИК 208141542\n")
    r_comp.bold = True
    r_comp.font.size = Pt(10.5)
    r_comp.font.color.rgb = BLUE_COLOR

    r_addr = p_comp.add_run(
        "2700 Благоевград, ул. „Ал. Стамболийски” №9, ет. 1\n"
        "www.tekoform.com | e-mail: bulgaria@tekoform.com | тел: +359 879 044 188"
    )
    r_addr.font.size = Pt(8.5)
    r_addr.font.color.rgb = RGBColor(90, 90, 90)

    p_title = doc.add_paragraph()
    action_text = "закупуване" if is_sale else "наемане"
    run_title = p_title.add_run(f"ОФЕРТА\nЗа {action_text} на пластмасова кофражна система TEKO")
    run_title.bold = True
    run_title.font.size = Pt(14)
    run_title.font.color.rgb = BLUE_COLOR
    p_title.paragraph_format.space_after = Pt(10)

    p_info = doc.add_paragraph()
    p_info.paragraph_format.line_spacing = 1.25
    p_info.paragraph_format.space_after = Pt(12)
    p_info.add_run("До: ").bold = True
    p_info.add_run(f"{client_name}\n")
    p_info.add_run("Относно: ").bold = True
    p_info.add_run(f"Кофриране на стоманобетонови елементи за обект: „{project_name}“\n")
    p_info.add_run("Дата: ").bold = True
    p_info.add_run(f"{offer_date.strftime('%d.%m.%Y')} г.")

    table = doc.add_table(rows=1, cols=6)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    hdr_cells = table.rows[0].cells
    headers = ["Елемент", "Размери", "Брой", "Площ (m²)", "Ед. цена (€/m²)", "Обща сума (€)"]
    
    for i, header_text in enumerate(headers):
        hdr_cells[i].text = header_text
        set_cell_background(hdr_cells[i], BLUE_HEX)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.font.size = Pt(9.5)

    for row_data in detailed_rows:
        row_cells = table.add_row().cells
        row_cells[0].text = str(row_data["Елемент"])
        row_cells[1].text = str(row_data["Размери"])
        row_cells[2].text = f"{row_data['Брой']} бр."
        row_cells[3].text = f"{row_data['Площ (m²)']:.2f} m²"
        row_cells[4].text = f"{price_per_m2:.2f} €"
        row_cells[5].text = f"{row_data['Обща сума (€)']:.2f} €"
        
        for i, c in enumerate(row_cells):
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i > 0 else WD_ALIGN_PARAGRAPH.LEFT
            for r in p.runs:
                r.font.size = Pt(9)

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    action_word = "покупка" if is_sale else "наем"
    p_summary = doc.add_paragraph()
    p_summary.paragraph_format.line_spacing = 1.25
    p_summary.paragraph_format.space_after = Pt(12)
    
    p_summary.add_run(f"Обща кофражна площ: {total_area:.2f} m²\n").bold = True
    p_summary.add_run(f"Обща стойност за {action_word} (без ДДС): {subtotal:.2f} €\n").bold = True
    p_summary.add_run(f"ДДС (20%): {vat_amount:.2f} €\n")
    
    run_total = p_summary.add_run(f"ОБЩО ЗА ПЛАЩАНЕ: {grand_total:.2f} €")
    run_total.bold = True
    run_total.font.size = Pt(11)
    run_total.font.color.rgb = BLUE_COLOR

    notes_p = doc.add_paragraph()
    notes_p.paragraph_format.space_before = Pt(8)
    notes_p.paragraph_format.space_after = Pt(12)
    notes_p.paragraph_format.line_spacing = 1.15
    
    run_th = notes_p.add_run("Условия на офертата:\n")
    run_th.bold = True
    run_th.font.color.rgb = BLUE_COLOR

    terms = [
        "1. Всички цени са посочени в евро (€) без включен ДДС.",
        "2. Начин на плащане: 100% авансово плащане при потвърждение на поръчката.",
        "3. Срок за доставка: До 5 работни дни след постъпване на плащането.",
        "4. Гаранция: 12 месеца за фабрични дефекти при спазване на инструкциите за работа.",
        "5. Забележка: В цената не са включени анкери, тапи, кофражно масло и пластмасови тръби.",
        "6. Място на вземане: Склад на фирмата (Транспортът е за сметка на Купувача/Наемателя)."
    ]
    for term in terms:
        r = notes_p.add_run(f"{term}\n")
        r.font.size = Pt(8.5)

    p_sign = doc.add_paragraph()
    p_sign.paragraph_format.space_before = Pt(8)
    p_sign.add_run("С уважение,\n").bold = True
    run_sign = p_sign.add_run("Екипът на ТЕКО България ООД\nwww.tekoform.com")
    run_sign.font.color.rgb = BLUE_COLOR
    run_sign.bold = True

    target_stream = io.BytesIO()
    doc.save(target_stream)
    target_stream.seek(0)
    return target_stream
