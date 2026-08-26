import os
from datetime import datetime
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def set_cell_background(cell, hex_color):
    """Задава цвят на фона на клетка от таблица."""
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def generate_word_offer(client_name, project_name, elements, price_per_m2=45.00, offer_type="sale", filename="TEKO_Offer.docx"):
    """
    Генерира търговска оферта в Word (.docx) за ПЛАСПАНЕЛ ООД / TEKO.
    offer_type: "sale" (Продажба) или "rental" (Наем)
    """
    doc = Document()

    # Полета на страницата (2 cm)
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    GREEN_COLOR = RGBColor(0, 153, 76)    # TEKO Зелено (само за логото)
    BLUE_COLOR = RGBColor(0, 80, 160)     # Корпоративно синьо
    BLUE_HEX = "0050A0"

    is_sale = (str(offer_type).lower() == "sale" or str(offer_type).lower() == "продажба")

    # ЛОГО TEKO (Зелено) и фирмени данни
    p_header = doc.add_paragraph()
    p_header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    
    run_logo = p_header.add_run("TEKO\n")
    run_logo.bold = True
    run_logo.font.size = Pt(24)
    run_logo.font.color.rgb = GREEN_COLOR

    run_company = p_header.add_run("ПЛАСПАНЕЛ ООД | ЕИК 208141542\n")
    run_company.bold = True
    run_company.font.size = Pt(10.5)
    run_company.font.color.rgb = RGBColor(50, 50, 50)

    run_sub = p_header.add_run(
        "2700 Благоевград, ул. „Ал. Стамболийски” №9, ет. 1\n"
        "www.tekoform.com | e-mail: bulgaria@tekoform.com | тел: +359 879 044 188"
    )
    run_sub.font.size = Pt(8.5)
    run_sub.font.color.rgb = RGBColor(100, 100, 100)

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # Заглавие на офертата
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    
    offer_title = "ОФЕРТА\nЗа закупуване на пластмасова кофражна система TEKO" if is_sale else "ОФЕРТА\nЗа отдаване под наем на пластмасова кофражна система TEKO"
    title_run = title_p.add_run(offer_title)
    title_run.bold = True
    title_run.font.size = Pt(16)
    title_run.font.color.rgb = BLUE_COLOR

    # Детайли за получателя и обекта
    details_p = doc.add_paragraph()
    details_p.paragraph_format.space_before = Pt(10)
    details_p.paragraph_format.space_after = Pt(15)
    
    details_p.add_run("До: ").bold = True
    details_p.add_run(f"{client_name}\n")
    details_p.add_run("Относно: ").bold = True
    details_p.add_run(f"Кофриране на стоманобетонови елементи за обект: „{project_name}“\n")
    details_p.add_run("Дата: ").bold = True
    details_p.add_run(f"{datetime.now().strftime('%d.%m.%Y')} г.")

    # Таблица с цени
    table = doc.add_table(rows=1, cols=6)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr_cells = table.rows[0].cells
    
    col_last_title = "Обща сума (€)" if is_sale else "Наем / месец (€)"
    headers = ['Елемент', 'Размери', 'Брой', 'Площ (m²)', 'Ед. цена (€/m²)', col_last_title]
    
    for i, text in enumerate(headers):
        hdr_cells[i].text = text
        set_cell_background(hdr_cells[i], BLUE_HEX)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.font.size = Pt(9.5)

    total_area = 0.0

    for elem in elements:
        row_cells = table.add_row().cells
        row_cells[0].text = str(elem['type'])
        row_cells[1].text = str(elem['dimensions'])
        row_cells[2].text = f"{elem['count']} бр."
        row_cells[3].text = f"{elem['area_m2']:.2f} m²"
        row_cells[4].text = f"{price_per_m2:.2f} €"
        
        elem_cost = elem['area_m2'] * price_per_m2
        row_cells[5].text = f"{elem_cost:.2f} €"

        total_area += elem['area_m2']

        for i in range(6):
            p = row_cells[i].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i > 0 else WD_ALIGN_PARAGRAPH.LEFT
            for run in p.runs:
                run.font.size = Pt(9)

    # Финансово резюме
    subtotal = total_area * price_per_m2
    vat = subtotal * 0.20
    grand_total = subtotal + vat

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    summary_p = doc.add_paragraph()
    summary_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    summary_p.paragraph_format.line_spacing = 1.25
    
    summary_p.add_run("Обща кофражна площ: ").bold = True
    summary_p.add_run(f"{total_area:.2f} m²\n")
    
    subtotal_label = "Обща стойност за покупка (без ДДС): " if is_sale else "Месечен наем (без ДДС): "
    summary_p.add_run(subtotal_label).bold = True
    summary_p.add_run(f"{subtotal:.2f} €\n")
    summary_p.add_run("ДДС (20%): ").bold = True
    summary_p.add_run(f"{vat:.2f} €\n")
    
    grand_label = f"ОБЩО ЗА ПЛАЩАНЕ: {grand_total:.2f} €" if is_sale else f"ОБЩО ЗА ПЛАЩАНЕ / МЕСЕЦ: {grand_total:.2f} €"
    total_run = summary_p.add_run(grand_label)
    total_run.bold = True
    total_run.font.size = Pt(11.5)
    total_run.font.color.rgb = BLUE_COLOR

    # Условия на офертата
    notes_p = doc.add_paragraph()
    notes_p.paragraph_format.space_before = Pt(15)
    notes_p.add_run("Условия на офертата:\n").bold = True
    notes_p.add_run("1. Всички цени са посочени в евро (€) без включен ДДС.\n")
    
    if is_sale:
        notes_p.add_run("2. Начин на плащане: 100% авансово плащане при потвърждение на поръчката.\n")
        notes_p.add_run("3. Срок за доставка: До 5 работни дни след постъпване на плащането.\n")
        notes_p.add_run("4. Гаранция: 12 месеца за фабрични дефекти при спазване на инструкциите за работа.\n")
    else:
        notes_p.add_run("2. Минимален срок за наем: 30 календарни дни.\n")
        notes_p.add_run(f"3. Гаранционен депозит: {subtotal:.2f} € (възстановим след връщане на кофража в чист вид).\n")
        
    notes_p.add_run("5. Забележка: В цената не са включени анкери, тапи, кофражно масло и пластмасови тръби.\n")
    notes_p.add_run("6. Място на вземане: Склад на фирмата (Транспортът е за сметка на Купувача/Наемателя).")

    # Подпис
    sign_p = doc.add_paragraph()
    sign_p.paragraph_format.space_before = Pt(20)
    sign_p.add_run("С уважение,\n").bold = True
    sign_p.add_run("Екипът на ПЛАСПАНЕЛ ООД\n")
    sign_p.add_run("www.tekoform.com")

    doc.save(filename)
    print(f"[Offer Generator] Успешно генерирана оферта за {'ПРОДАЖБА' if is_sale else 'НАЕМ'}: '{filename}'")