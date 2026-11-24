import io
import math
import re
import hmac
import hashlib
import fitz  # PyMuPDF
import pandas as pd
from PIL import Image
import streamlit as st
import docx
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from gemini_agent2 import analyze_blueprint
from drawing_generator import generate_pdf_drawings, generate_top_view_buf, generate_front_view_buf
from excel_export import (KSS_EXTRA, KSS_ITEMS, generate_excel, stock_to_excel, stock_from_excel,
                          prices_from_excel)
import projects_store
from accessories_calculator import calculate_accessories
from teko_calculator import (solve_height_cm, layout_element, count_panels, is_compensator_row, thickness_label,
                             panel_height_cm,
                             t_wall_offset_label)
from stock_layout import plan_project
from weights_db import get_item_weight
from i18n import t, t_item, init_language, language_switch, MANUAL_HELP_BG
from doc_lang import DOC_FLAGS, DOC_LANGUAGES, document_language, dt
from floor_plan import (ROW_WIDTH_CM, default_positions, drawing_places, floor_component, gemini_outlines,
                        generate_floor_pdf, pdf_shapes, piece_boxes, piece_plan)

init_language()
st.set_page_config(
    page_title=t("TEKO - Вертикален Кофраж и Оферти"),
    page_icon="🏗",
    layout="wide"
)

# === СИСТЕМА ЗА ЗАЩИТА С ПАРОЛА ===
LOGIN_COOKIE = "teko_login"   # „Запомни този компютър“ (потребителят, 20.11.2026)
LOGIN_REMEMBER_DAYS = 90

def app_password():
    """Паролата от secrets (password); празна - без вход (локално, на компютъра)."""
    try:
        return str(st.secrets.get("password", ""))
    except FileNotFoundError:
        return ""

def login_token(secret_pass):
    """Знакът в бисквитката „Запомни този компютър“ - изчислен от паролата (самата парола не се пази);
    при смяна на паролата старите бисквитки спират да важат."""
    return hmac.new(secret_pass.encode("utf-8"), b"teko-login-remember", hashlib.sha256).hexdigest()

def set_login_cookie(value, days):
    """Бисквитката в браузъра (days = 0 - изтрива я)."""
    st.html(f"<script>document.cookie = '{LOGIN_COOKIE}={value}; max-age={days * 86400}; path=/; "
            f"SameSite=Lax';</script>", unsafe_allow_javascript=True)

def check_password():
    """Вход с парола от secrets (password); без парола в secrets (локално, на компютъра) - без вход.
    Запомнен компютър (бисквитка с login_token) - направо, без парола, до изхода или смяната на паролата."""
    secret_pass = app_password()
    if not secret_pass or st.session_state.get("password_correct"):
        return True
    if not st.session_state.get("logged_out"):   # след „Изход“ бисквитката на тази сесия не важи
        try:
            saved = str(st.context.cookies.get(LOGIN_COOKIE) or "")
        except Exception:
            saved = ""
        if saved and hmac.compare_digest(saved.encode("utf-8"), login_token(secret_pass).encode("utf-8")):
            st.session_state["password_correct"] = True
            return True
    if st.session_state.pop("clear_login_cookie", False):
        set_login_cookie("", 0)
    st.title(t("🔒 Вход в системата TEKO"))
    with st.form("login"):
        user_pass = st.text_input(t("🔑 Въведете парола за достъп:"), type="password")
        remember = st.checkbox(t("Запомни този компютър ({d} дни)", d=LOGIN_REMEMBER_DAYS),
                               help=t("Следващия път влизате направо, без парола. Не отмятайте на чужд компютър. "
                                      "Изход - с бутона „🚪 Изход“ в страничното меню; при смяна на паролата всички "
                                      "запомнени компютри се изписват сами."))
        if st.form_submit_button(t("Вход")):
            # като байтове - с текст compare_digest приема само латиница (парола на кирилица дава грешка)
            if hmac.compare_digest(user_pass.encode("utf-8"), secret_pass.encode("utf-8")):
                st.session_state["password_correct"] = True
                st.session_state.pop("logged_out", None)
                if remember:   # записва се при следващото показване (след st.rerun)
                    st.session_state["login_cookie"] = login_token(secret_pass)
                st.rerun()
            st.error(t("❌ Грешна парола! Опитайте отново."))
    return False

if not check_password():
    st.stop()
if st.session_state.get("login_cookie"):
    set_login_cookie(st.session_state.pop("login_cookie"), LOGIN_REMEMBER_DAYS)
# ==================================

def set_cell_background(cell, hex_color):
    """Задава цвят на фона на клетка от таблица."""
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

# === СТЪПКА 3: Описание на редовете по височина ===
def format_height_breakdown_text(height_cm, layout=None):
    """
    Форматира височината на елемента в ясен текст за използваните нива от панели.
    layout: разположението на елемента (основата може да е сменена според дължините).
    """
    h_cm = round(float(height_cm or 300))
    h_levels = layout["height_levels"] if layout else solve_height_cm(h_cm)
    parts = []
    for idx, h_val in enumerate(h_levels, 1):
        if is_compensator_row(h_val):
            parts.append(t("Ред {i}: Компенсатор TC ({h} cm)", i=idx, h=h_val))
        elif h_val <= 60:
            parts.append(t("Ред {i}: Полегнал ({h} cm)", i=idx, h=h_val))
        else:
            parts.append(t("Ред {i}: Изправен ({h} cm)", i=idx, h=h_val))
    return " | ".join(parts)

# === СТЪПКА 4: Проверка за нестандартни размери ===
def check_element_dimensions(row):
    """
    Проверява дали въведените размери са кратни на стандартните модули на TEKO (5 cm за ширина и височина).
    """
    warnings = []
    h_cm = round(_row_float(row, "height_cm", 300))
    elem_type = str(row.get("type", "wall"))
    name = format_element_label(elem_type, str(row.get("name", "Елемент")))

    # Задължителните размери за типа; празен или 0 (напр. непопълнен от Gemini) - сметката не е вярна
    missing = [t(label) for col, label in REQUIRED_DIMENSIONS.get(elem_type, [])
               if not _row_float(row, col, 0) > 0]
    if missing:
        warnings.append(t("• **{name}**: липсва размер ({missing}) - празен или 0. Попълнете го в таблицата, иначе "
                          "сметката и чертежът не са верни.", name=name, missing=", ".join(missing)))

    if h_cm % 5 != 0:
        warnings.append(t("• **{name}**: Височина {h} cm не е кратна на 5 cm (закръгля се нагоре до 5 cm).",
                          name=name, h=h_cm))

    def board_warning(label, col, default):
        """
        Дължина, некратна на 5 cm: панелите - надолу до 5 cm, остатъкът под 5 cm - дървена дъска
        (само на чертежа). Кратните на 5 (и 5 / 10 / 15 cm в реда - компенсатор TC) - без предупреждение.
        """
        value = _row_float(row, col, default)
        panels = math.floor(round(value, 6) / 5.0) * 5
        board = round(value - panels, 6)
        if board > 0:
            warnings.append(t("• **{name}**: {label} {value} cm не е кратна на 5 cm - панели до {panels} cm + "
                              "дървена дъска {board} cm (само на чертежа, не влиза в сметката и площта).",
                              name=name, label=t(label), value=f"{value:g}", panels=f"{panels:g}", board=f"{board:g}"))

    if elem_type == "column":
        board_warning("Стена A", "l1_cm", 50)
        board_warning("Дебелина стена A", "thickness_cm", 25)
    elif elem_type == "wall":
        board_warning("Дължината", "l1_cm", 500)
    elif elem_type == "l_wall":
        board_warning("Стена A", "l1_cm", 200)
        board_warning("Стена B", "l2_cm", 200)
    elif elem_type == "u_wall":
        board_warning("Стена A", "l1_cm", 200)
        board_warning("Стена B", "l2_cm", 200)
        board_warning("Стена C", "l3_cm", 200)
    elif elem_type == "t_wall":
        l1_cm = round(_row_float(row, "l1_cm", 200))
        l2_cm = round(_row_float(row, "l2_cm", 200))
        # реброто: „Дебелина стена B“, празна = дебелина стена A
        t_cm = round(_row_float(row, "thickness2_cm", None) or _row_float(row, "thickness_cm", 25))
        # Стена C: от левия край на полката до лявото лице на реброто; празно = реброто е в средата
        l3_cm = round(_row_float(row, "l3_cm", 0))
        board_warning("Стена A", "l1_cm", 200)
        board_warning("Стена B", "l2_cm", 200)
        if l3_cm % 5 != 0:
            warnings.append(t("• **{name}**: Мястото на реброто (Стена C = {l3} cm) не е кратно на 5 cm.",
                              name=name, l3=l3_cm))
        # от всяка страна на реброто трябва да остане място за IN (10 cm) и поне 5 cm панел
        if l3_cm and (l3_cm - 10 < 5 or l1_cm - l3_cm - t_cm - 10 < 5):
            warnings.append(t("• **{name}**: Реброто на {l3} cm от левия край не оставя място за ъгъл IN (10 cm) и "
                              "поне 5 cm панел от двете страни на полката ({l1} cm) - проверете Стена C.",
                              name=name, l3=l3_cm, l1=l1_cm))
        if (not l3_cm and (l1_cm - t_cm) / 2 <= 10) or l2_cm <= 10:
            warnings.append(t("• **{name}**: Страна A ({l1} cm) или B ({l2} cm) е твърде къса за T-стена с дебелина "
                              "{t} cm - проверете Стена A и Стена B.", name=name, l1=l1_cm, l2=l2_cm, t=t_cm))

    # Правдоподобност (потребителят, 20.11.2026) - само предупреждение, размерите не се сменят:
    # необичайна дебелина или височина, права стена по-къса от дебелината, стена без място за панела до EX
    if elem_type in WALL_THICKNESS_COLUMNS and elem_type != "column":
        n_walls = 3 if elem_type == "t_wall" else WALL_THICKNESS_COLUMNS[elem_type]
        for col, label in list(zip(("thickness_cm", "thickness2_cm", "thickness3_cm"),
                                   ("Дебелина стена A", "Дебелина стена B", "Дебелина стена C")))[:n_walls]:
            value = _row_float(row, col, None)
            if value and not 10 <= value <= 100:
                warnings.append(t("• **{name}**: {label} {value} cm е необичайна (обикновено 10-100 cm) - проверете "
                                  "размера.", name=name, label=t(label), value=f"{value:g}"))
    h_raw = _row_float(row, "height_cm", None)
    if h_raw and not 20 <= h_raw <= 1200:
        warnings.append(t("• **{name}**: Височина {h} cm е необичайна (обикновено 20-1200 cm) - проверете размера.",
                          name=name, h=f"{h_raw:g}"))
    t1 = _row_float(row, "thickness_cm", None) or _row_float(row, "thickness1_cm", None)
    if elem_type == "wall" and t1:
        length = _row_float(row, "l1_cm", 0)
        if 0 < length < t1:
            warnings.append(t("• **{name}**: Дължината ({l} cm) е по-малка от дебелината ({t} cm) - разменени ли са?",
                              name=name, l=f"{length:g}", t=f"{t1:g}"))
    if elem_type in ("l_wall", "u_wall") and t1:
        t2 = _row_float(row, "thickness2_cm", None) or t1
        t3 = _row_float(row, "thickness3_cm", None) or t1
        if elem_type == "l_wall":   # до EX: дебелината на перпендикулярната стена + 10 (ъгъл IN)
            arms = [("Стена A", "l1_cm", t2 + 10), ("Стена B", "l2_cm", t1 + 10)]
        else:                       # гърбът B - между двата ъгъла
            arms = [("Стена A", "l1_cm", t2 + 10), ("Стена B", "l2_cm", t1 + t3 + 20), ("Стена C", "l3_cm", t2 + 10)]
        for label, col, need in arms:
            length = _row_float(row, col, 0)
            if 0 < length < need + 5:
                warnings.append(t("• **{name}**: {label} ({l} cm) е твърде къса - до ъглите са нужни {k} cm и поне "
                                  "5 cm панел. Проверете размерите.", name=name, label=t(label), l=f"{length:g}",
                                  k=f"{need:g}"))

    # Размерите са в см - стойност под 10 най-вероятно е въведена в метри (напр. 2.5 вместо 250)
    small = [f"{col} = {row.get(col):g}" for col in LENGTH_COLUMNS
             if pd.notna(pd.to_numeric(row.get(col), errors="coerce")) and 0 < float(row.get(col)) < 10]
    if small:
        warnings.append(t("• **{name}**: {small} - размерите са в **сантиметри**; въведени ли са в метри? "
                          "(напр. 2.5 м = 250 см)", name=name, small=", ".join(small)))

    return warnings

def _row_float(row, key, default):
    val = row.get(key)
    return float(val) if pd.notna(val) and val != "" else default

DEFAULT_HEIGHT_CM = 270

# Размерите в таблицата са в сантиметри
LENGTH_COLUMNS = ["width_cm", "length_cm", "thickness_cm", "l1_cm", "l2_cm", "l3_cm", "height_cm",
                  "thickness1_cm", "thickness2_cm", "thickness3_cm"]

# Размерите, без които елементът не може да се сметне (Стена C на Т-стена е по желание);
# thickness_cm = „Дебелина стена A“ (thickness_to_walls)
REQUIRED_DIMENSIONS = {
    "column": [("thickness_cm", "Дебелина стена A"), ("l1_cm", "Стена A"), ("height_cm", "Височина")],
    "wall": [("thickness_cm", "Дебелина стена A"), ("l1_cm", "Стена A"), ("height_cm", "Височина")],
    "l_wall": [("thickness_cm", "Дебелина стена A"), ("l1_cm", "Стена A"), ("l2_cm", "Стена B"),
               ("height_cm", "Височина")],
    "u_wall": [("thickness_cm", "Дебелина стена A"), ("l1_cm", "Стена A"), ("l2_cm", "Стена B"),
               ("l3_cm", "Стена C"), ("height_cm", "Височина")],
    "t_wall": [("thickness_cm", "Дебелина стена A"), ("l1_cm", "Стена A"), ("l2_cm", "Стена B"),
               ("height_cm", "Височина")],
}

# Дебелина стена A / B / C (thickness1_cm ...); общата „Дебелина“ (thickness_cm) не се показва
ARM_THICKNESS_COLUMNS = ("thickness1_cm", "thickness2_cm", "thickness3_cm")
# Стените на всеки тип, за които се показва дебелина (колона и права стена - само A)
WALL_THICKNESS_COLUMNS = {"column": 1, "wall": 1, "l_wall": 2, "t_wall": 2, "u_wall": 3}

# Колоните на таблицата по реда на показване; дължината на права стена и колона е в „Стена A“,
# другият размер на колоната - в „Дебелина стена A“; thickness_cm остава в данните (архив, Gemini), скрита
# Тип елемент: в таблицата се виждат имената, в данните (архив, Gemini) остават кодовете
TYPE_LABELS = {"column": "Колона", "wall": "Права стена", "l_wall": "L-стена", "u_wall": "П-стена", "t_wall": "T-стена"}
TABLE_COLUMNS = ["type", "name", "count", "l1_cm", "thickness1_cm", "l2_cm", "thickness2_cm", "l3_cm",
                 "thickness3_cm", "height_cm", "closed_end_1", "closed_end_2", "closed_end_3"]
DATA_COLUMNS = TABLE_COLUMNS + ["thickness_cm", "drawing"]

# Чертежи (потребителят, 18.11.2026): всеки разчетен чертеж добавя своите елементи в отделна таблица под
# заглавие „Чертеж N: име на файла“; drawing е името на чертежа, празно - без чертеж (ръчно, стари проекти).
# Сметките (табове 2-5) са за всички чертежи заедно.
TABLE_EDITOR_KEY = "elements_form_editor"

def drawing_name(value):
    return "" if value is None or (not isinstance(value, str) and pd.isna(value)) else str(value).strip()

def drawing_groups(df):
    """[(име на чертежа, редовете му)] по реда на първата поява; "" - редовете без чертеж."""
    if "drawing" not in df.columns:
        return [("", df)] if len(df) else []
    names = df["drawing"].map(drawing_name)
    return [(name, df[names == name]) for name in dict.fromkeys(names)]

def join_drawing_groups(groups):
    """Обратно в една таблица: чертежите един след друг, всеки ред с името на своя чертеж."""
    parts = []
    for name, part in groups:
        part = part.copy()
        part["drawing"] = name or None
        parts.append(part)
    parts = [p for p in parts if len(p)]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=DATA_COLUMNS)

def drawing_file_key(drawing):
    return (st.session_state.get("current_project"), drawing)

def keep_drawing_file(drawing, uploaded_file):
    """Файлът на разчетения чертеж - в сесията (не в архива), за фона в таб 6 „3D план на етажа“."""
    st.session_state.setdefault("drawing_files", {})[drawing_file_key(drawing)] = {
        "name": uploaded_file.name, "type": uploaded_file.type, "data": uploaded_file.getvalue()}

def drawing_file(drawing):
    """
    Файлът на чертежа за фона: разчетеният в таб 1 (пази се, докато страницата е отворена) или качения в
    момента в таб 1 със същото име. None - няма го (напр. проектът е отворен наново след F5).
    """
    saved = st.session_state.get("drawing_files", {}).get(drawing_file_key(drawing))
    if saved:
        return saved
    current_upload = st.session_state.get("blueprint_upload")
    if drawing and current_upload is not None and current_upload.name == drawing:
        return {"name": current_upload.name, "type": current_upload.type, "data": current_upload.getvalue()}
    return None

def unique_drawing_name(name, existing):
    """„план.pdf“, а ако го има - „план.pdf (2)“, „план.pdf (3)“ ..."""
    if name not in existing:
        return name
    n = 2
    while f"{name} ({n})" in existing:
        n += 1
    return f"{name} ({n})"

def reset_table_editors():
    """Таблиците на чертежите се показват наново от записаните данни (след смяна на редовете или чертежите)."""
    for key in [k for k in st.session_state if str(k).startswith(TABLE_EDITOR_KEY)]:
        st.session_state.pop(key, None)

def thickness_to_walls(df, migrate=True):
    """
    „Дебелина стена A / B / C“ вместо общата „Дебелина“ (потребителят, 09.11.2026). Празна „Дебелина
    стена B / C“ = като стена A, така че една стойност в A е дебелината на целия елемент; B / C, равни на A,
    се изчистват. Празна A се попълва от общата дебелина (thickness_cm - стари проекти, Gemini), после
    thickness_cm = дебелина стена A - сметките са както досега.
    migrate: стар ред с A, различна от общата - празните B / C са били общата дебелина и я получават
    (при „Запази и Изчисли“ - не: там thickness_cm е старата A, а празните B / C са „като новата A“).
    """
    df = df.copy()
    for col in ARM_THICKNESS_COLUMNS + ("thickness_cm",):
        if col not in df.columns:
            df[col] = None
    common = pd.to_numeric(df["thickness_cm"], errors="coerce")
    t1 = pd.to_numeric(df["thickness1_cm"], errors="coerce")
    t1 = t1.where(t1 > 0, common)
    n_walls = df["type"].map(WALL_THICKNESS_COLUMNS).fillna(1) if "type" in df.columns else 1
    for i, col in enumerate(ARM_THICKNESS_COLUMNS[1:], 2):
        value = pd.to_numeric(df[col], errors="coerce")
        value = value.where(value > 0)
        if migrate:
            old_common = value.isna() & (n_walls >= i) & common.notna() & (common != t1)
            value = value.where(~old_common, common)
        df[col] = value.where(value != t1)
    df["thickness1_cm"] = t1
    df["thickness_cm"] = t1
    return df

def columns_to_cm(df):
    """Стари колони в метри (width_m, height_m ...) -> същите в сантиметри (width_cm, height_cm ...).
    Старата „Дължина“ (length_cm, напр. от Gemini) отива в „Стена A“ (l1_cm),
    старата „Ширина“ на колона (width_cm) - в „Дебелина“ (thickness_cm), ако там е празно или 0."""
    df = df.copy()
    for col_cm in LENGTH_COLUMNS:
        col_m = col_cm[:-3] + "_m"
        if col_m in df.columns:
            meters = pd.to_numeric(df[col_m], errors="coerce") * 100
            df[col_cm] = df[col_cm].fillna(meters) if col_cm in df.columns else meters
            df = df.drop(columns=[col_m])
    # Празна или 0 (Gemini връща 0 за непопълнено поле) се попълва от старата колона
    for old, new in (("length_cm", "l1_cm"), ("width_cm", "thickness_cm")):
        if old not in df.columns:
            continue
        if new in df.columns:
            current = pd.to_numeric(df[new], errors="coerce")
            df[new] = df[new].where(current.fillna(0) != 0, df[old])
        else:
            df[new] = df[old]
        df = df.drop(columns=[old])
    return df

def fill_default_height(df, height_cm):
    """Празната „Височина“ се смята със стандартната височина на етажа; въведената остава."""
    df = df.copy()
    if "height_cm" not in df.columns:
        df["height_cm"] = None
    df["height_cm"] = pd.to_numeric(df["height_cm"], errors="coerce").fillna(height_cm)
    return df

def _row_bool(row, key, default=False):
    val = row.get(key)
    return bool(val) if pd.notna(val) and val != "" else default

CLOSED_END_COLUMNS = ("closed_end_1", "closed_end_2", "closed_end_3")

def _closed_end(row, key):
    """Краищата на стените са затворени по подразбиране; отворен е само край с махната отметка."""
    return _row_bool(row, key, default=True)

def row_to_layout(elem_type, row):
    """Превежда ред от таблицата към разположение на панелите (teko_calculator.layout_element)."""
    h_cm = _row_float(row, "height_cm", 300)
    t_cm = _row_float(row, "thickness_cm", 25)
    closed = {"closed_end_1": _closed_end(row, "closed_end_1"),
              "closed_end_2": _closed_end(row, "closed_end_2")}
    # празна „Дебелина стена B / C“ = дебелина стена A (thickness_cm, thickness_to_walls)
    arms = {col: _row_float(row, col, None) for col in ("thickness1_cm", "thickness2_cm", "thickness3_cm")}

    if elem_type == "column":
        # страна A = „Стена A“ (l1_cm), страна B = „Дебелина стена A“: колона 80x30 - A 80, B 30
        return layout_element("column", h_cm,
                              width_cm=_row_float(row, "l1_cm", 50),
                              length_cm=t_cm)
    elif elem_type == "wall":
        return layout_element("wall", h_cm, length_cm=_row_float(row, "l1_cm", 500),
                              thickness_cm=t_cm, **closed)
    elif elem_type == "l_wall":
        return layout_element("l_wall", h_cm,
                              l1_cm=_row_float(row, "l1_cm", 200),
                              l2_cm=_row_float(row, "l2_cm", 200),
                              thickness_cm=t_cm, thickness1_cm=arms["thickness1_cm"],
                              thickness2_cm=arms["thickness2_cm"], **closed)
    elif elem_type == "u_wall":
        return layout_element("u_wall", h_cm,
                              l1_cm=_row_float(row, "l1_cm", 200),
                              l2_cm=_row_float(row, "l2_cm", 200),
                              l3_cm=_row_float(row, "l3_cm", 200),
                              thickness_cm=t_cm, **arms, **closed)
    elif elem_type == "t_wall":
        return layout_element("t_wall", h_cm,
                              l1_cm=_row_float(row, "l1_cm", 200),
                              l2_cm=_row_float(row, "l2_cm", 200),
                              l3_cm=_row_float(row, "l3_cm", 0),  # мястото на реброто; празно = средата
                              thickness_cm=t_cm, **arms,   # дебелина C - полката вляво от реброто
                              closed_end_3=_closed_end(row, "closed_end_3"), **closed)
    return None

def row_layout_key(elem_type, row):
    """Размерите, от които зависи разположението (без броя и името) - еднаквите редове имат един ключ."""
    sizes = ("height_cm", "thickness_cm", "l1_cm", "l2_cm", "l3_cm", "thickness1_cm", "thickness2_cm", "thickness3_cm")
    return ((elem_type,) + tuple(_row_float(row, col, None) for col in sizes)
            + tuple(_closed_end(row, col) for col in CLOSED_END_COLUMNS))

def element_layout(elem_type, row):
    """
    Разположението на реда: при „Редене според складовата наличност“ - от плана (stock_layout.py),
    иначе - алгоритъмът (row_to_layout).
    """
    planned = st.session_state.get("stock_plan", {}).get(row_layout_key(elem_type, row))
    return planned["layout"] if planned else row_to_layout(elem_type, row)

def get_element_teko_panels(elem_type, row):
    cnt = int(_row_float(row, "count", 1))
    layout = element_layout(elem_type, row)
    if layout is None:
        return {}
    return count_panels(layout, cnt)

def get_element_accessories(elem_type, row):
    cnt = int(_row_float(row, "count", 1))
    layout = element_layout(elem_type, row)
    if layout is None:
        return {}

    h_cm = layout["height_cm"]
    h_levels = layout["height_levels"]
    widths_a = layout["faces"][0]["rows"][0]

    if elem_type == "column":
        dims = layout["dims"]
        acc = calculate_accessories("column", dims["a"], dims["b"], h_cm, widths_a, h_levels, layout=layout)
    elif elem_type == "wall":
        dims = layout["dims"]
        acc = calculate_accessories("wall", dims["length"], dims["t"], h_cm, widths_a, h_levels, layout=layout)
    elif elem_type == "l_wall":
        dims = layout["dims"]
        acc = calculate_accessories("L-образна стена", dims["l1"], dims["l2"], h_cm, widths_a, h_levels, layout=layout)
    elif elem_type == "t_wall":
        dims = layout["dims"]
        stem = next(f for f in layout["faces"] if f["name"] == "B")["length_cm"]
        acc = calculate_accessories("T-образна стена", dims["l1"], stem, h_cm, widths_a, h_levels, layout=layout)
    else:
        dims = layout["dims"]
        acc = calculate_accessories("П-образна стена", dims["l1"] + dims["l2"] + dims["l3"], dims["t"], h_cm, widths_a, h_levels, layout=layout)

    res = {}
    for code, qty in acc["bom_summary"].items():
        res[code] = qty * cnt
    return res

# Складова наличност (таб 5): елементите в реда от „1. Наличности.xlsx“ (лист „Складова наличност“).
# Таблицата се редактира в таб 5 и се пази в архива (лист „Наличност“, обща за всички проекти);
# без архив - само докато страницата е отворена. Празен архив - този списък с празна наличност.
# Складът - същите артикули и ред като „Кол. сметка“ в Excel („1. Оферта – софтуер.xlsx“, потребителят 18.11.2026);
# наличността не е в кода - зарежда се от Excel („📥 Зареди от Excel“) или се пише в таблицата
STOCK_ITEMS = [(name, "бр") for name, _codes in KSS_ITEMS]
STOCK_COLUMNS = ["Елемент", "Мярка", "Остава"]

def default_stock_df():
    stock_df = pd.DataFrame(STOCK_ITEMS, columns=STOCK_COLUMNS[:2])
    stock_df["Остава"] = pd.Series([None] * len(stock_df), dtype="float")
    return stock_df

def load_stock_once():
    """Наличността от архива - веднъж за сесията (F5 зарежда наново); без архив или празен лист - STOCK_ITEMS."""
    if "stock_df" in st.session_state:
        return
    stock_df, modified = None, None
    try:
        stock_df, modified = projects_store.load_stock()
    except Exception as exc:  # noqa: BLE001 - архивът не е достъпен, таб 5 работи без него
        st.session_state["stock_error"] = f"{type(exc).__name__}: {exc}"
    st.session_state["stock_df"] = stock_df if stock_df is not None else default_stock_df()
    st.session_state["stock_modified"] = modified

def reload_stock():
    """„🔄 Обнови от архива“ (потребителят, 20.11.2026): наличността наново от Google, без F5 - незаписаните
    промени в таблицата се губят."""
    for key in ("stock_df", "stock_error", "stock_modified", "stock_editor", "excel_bytes"):
        st.session_state.pop(key, None)
    load_stock_once()

def store_stock(stock_df):
    """Записва наличността в сесията и в архива; при грешка в архива - съобщение в таб 5."""
    st.session_state["stock_df"] = stock_df.reset_index(drop=True)
    st.session_state.pop("stock_error", None)
    st.session_state.pop("excel_bytes", None)   # колоната „Наличност в склада“ в Excel - наново
    try:
        st.session_state["stock_modified"] = projects_store.save_stock(st.session_state["stock_df"])
    except Exception as exc:  # noqa: BLE001
        st.session_state["stock_error"] = f"{type(exc).__name__}: {exc}"

_LATIN = str.maketrans("АВЕКМНОРСТХ", "ABEKMHOPCTX")  # кирилски букви, които изглеждат като латински

def stock_key(name):
    """
    Общ ключ за името в склада и кода от сметката: „Панел TEKO TK 150/60“ и „TK 150/60 (полегнал)“ -> TK 150/60,
    „Ръкохватка H8 зелени“ -> H8, „Шпилка d12 TR12“ и „Шпилка TR 12“ -> TR12. Без ключ (FP, AC, EС240) - None.
    """
    s = re.sub(r"\s+", "", str(name).upper().translate(_LATIN))
    for pattern, fmt in ((r"TK(\d+)/(\d+)", "TK {}/{}"), (r"TC(\d+)/(\d+)", "TC {}/{}"),
                         (r"(IN|EX)(\d+)", "{}{}"), (r"AW(\d+)", "AW {}"), (r"(TR12)", "{}"),
                         (r"(N12)", "{}"), (r"(PP)", "{}"), (r"H(\d)(?!\d)", "H{}")):
        m = re.search(pattern, s)
        if m:
            return fmt.format(*m.groups())
    return None

def project_requirements(df_calc):
    """Нужните бройки за проекта (панели и аксесоари, по броя елементи), събрани по stock_key."""
    need = {}
    for _, row in df_calc.iterrows():
        elem_type = str(row.get("type", "wall"))
        try:
            items = {**get_element_teko_panels(elem_type, row), **get_element_accessories(elem_type, row)}
        except Exception:
            continue  # грешен ред - предупреждението за размерите е в таб 2
        for code, qty in items.items():
            key = stock_key(code)
            if key:
                need[key] = need.get(key, 0) + qty
    return need

def stock_available():
    """
    Въведената наличност по stock_key: ({ключ: наличност}, всички ключове в склада). Редовете с един ключ
    се събират (H8 зелени + сиви); празна наличност не се брои.
    """
    stock_df = st.session_state.get("stock_df")
    available, listed = {}, set()
    if stock_df is None:
        return available, listed
    for _, row in stock_df.iterrows():
        key = stock_key(row.get("Елемент", ""))
        if not key:
            continue
        listed.add(key)
        qty = pd.to_numeric(row.get("Остава"), errors="coerce")
        if pd.notna(qty):
            available[key] = available.get(key, 0) + float(qty)
    return available, listed

def update_stock_plan(df_calc):
    """
    „Редене според складовата наличност“ (stock_layout.py): разположенията на всички елементи според склада,
    в st.session_state["stock_plan"]; без отметката или без въведена наличност - празно (алгоритъмът).
    Смята се наново само при промяна на таблицата, наличността или отметката.
    """
    on = bool(st.session_state.get("stock_layout_on")) and not df_calc.empty
    stock_df = st.session_state.get("stock_df")
    signature = (df_calc.to_json(), None if stock_df is None else stock_df.to_json()) if on else None
    if st.session_state.get("stock_plan_signature", None) == signature and "stock_plan" in st.session_state:
        return
    st.session_state.pop("excel_bytes", None)  # старият Excel е с другото разположение
    st.session_state["stock_plan_signature"] = signature
    if not on:
        st.session_state["stock_plan"] = {}
        return
    elements, index = [], {}
    for _, row in df_calc.iterrows():
        elem_type = str(row.get("type", "wall"))
        try:
            layout = row_to_layout(elem_type, row)
        except Exception:
            continue  # грешен ред - предупреждението за размерите е в таб 2
        if layout is None:
            continue
        key = row_layout_key(elem_type, row)
        cnt = int(_row_float(row, "count", 1))
        if key in index:   # еднакви редове - един елемент, броят се събира
            elements[index[key]][2] += cnt
        else:
            index[key] = len(elements)
            elements.append([key, layout, cnt])
    available, _ = stock_available()
    st.session_state["stock_plan"] = plan_project([tuple(e) for e in elements], available, stock_key)
    st.session_state["stock_plan_signature"] = signature

def stock_plan_signature(elem_type, row):
    """Разположението на реда според склада като текст - за кеша на прегледа; без промяна - празно."""
    planned = st.session_state.get("stock_plan", {}).get(row_layout_key(elem_type, row))
    if not planned or not (planned["replaced"] or planned["levels_changed"]):
        return ""
    layout = planned["layout"]
    return repr((layout["height_levels"], [face["rows"] for face in layout["faces"]]))

def show_stock_layout_notes(df_calc):
    """Какво е сменено при „Редене според складовата наличност“ (табове 1 и 2)."""
    if not st.session_state.get("stock_layout_on"):
        return
    plan = st.session_state.get("stock_plan", {})
    if not plan:
        st.info(t("ℹ️ Редене според складовата наличност: няма въведена наличност - панелите са по алгоритъма."))
        return
    names = {}
    for _, row in df_calc.iterrows():
        elem_type = str(row.get("type", "wall"))
        names.setdefault(row_layout_key(elem_type, row), []).append(format_element_label(elem_type, row.get("name", "")))
    lines = []
    for key, result in plan.items():
        label = ", ".join(names.get(key, []))
        if result["levels_changed"]:
            levels = " + ".join(str(h) for h in result["layout"]["height_levels"])
            lines.append(t("- **{e}**: пренареден по височина - {levels} см", e=label, levels=levels))
        moved = {}
        for old, new, qty in result["replaced"]:
            item = (old, " + ".join(new))
            moved[item] = moved.get(item, 0) + qty
        for (old, new), qty in moved.items():
            lines.append(t("- **{e}**: {old} → {new} ({n} места)", e=label, old=t_item(old), new=t_item(new), n=qty))
    if lines:
        st.info(t("🔁 Редене според складовата наличност - сменени панели:") + "\n" + "\n".join(lines))
    else:
        st.info(t("✅ Редене според складовата наличност: всички панели по алгоритъма са налични."))

def load_prices_once():
    """Единичните цени (потребителят, 20.11.2026) от архива - веднъж за сесията; без архив - само в сесията."""
    if "prices_df" in st.session_state:
        return
    prices_df, modified = None, None
    try:
        prices_df, modified = projects_store.load_prices()
    except Exception as exc:  # noqa: BLE001 - архивът не е достъпен, Excel е без цени
        st.session_state["prices_error"] = f"{type(exc).__name__}: {exc}"
    st.session_state["prices_df"] = prices_df
    st.session_state["prices_modified"] = modified

def store_prices(prices_df):
    """Записва цените в сесията и в архива (лист „Цени“); готовият Excel се прави наново."""
    st.session_state["prices_df"] = prices_df.reset_index(drop=True)
    st.session_state.pop("prices_error", None)
    st.session_state.pop("excel_bytes", None)
    try:
        st.session_state["prices_modified"] = projects_store.save_prices(st.session_state["prices_df"])
    except Exception as exc:  # noqa: BLE001
        st.session_state["prices_error"] = f"{type(exc).__name__}: {exc}"

def kss_prices():
    """
    Цените за колоната „Ед. Цена“ в „Кол. сметка“ (Excel): {наименование в КСС: цена}. По името, иначе по
    stock_key (първата цена с този код); FP, AC, Тапа нямат код - само по името.
    """
    prices_df = st.session_state.get("prices_df")
    if prices_df is None:
        return {}
    by_name, by_key = {}, {}
    for _, row in prices_df.iterrows():
        price = pd.to_numeric(row.get("Ед. цена"), errors="coerce")
        if pd.notna(price) and price > 0:
            name = " ".join(str(row.get("Елемент", "")).split())
            by_name.setdefault(name, float(price))
            if stock_key(name):
                by_key.setdefault(stock_key(name), float(price))
    result = {}
    for name in [n for n, _codes in KSS_ITEMS] + [n for n, *_rest in KSS_EXTRA]:
        if name in by_name:
            result[name] = by_name[name]
        elif stock_key(name) in by_key:
            result[name] = by_key[stock_key(name)]
    return result

def render_prices_box():
    """„💶 Цени от Excel“ в таб 2 (вариант А, 20.11.2026): цените влизат в колона „Ед. Цена“ на „Кол. сметка“."""
    load_prices_once()
    prices_df = st.session_state.get("prices_df")
    count = 0 if prices_df is None else len(prices_df)
    modified = st.session_state.get("prices_modified")
    if count:
        st.caption(t("💶 Цени в Excel: {n} артикула", n=count) +
                   (t(" (заредени на {d})", d=modified.strftime("%d.%m.%Y %H:%M")) if modified else ""))
    else:
        st.caption(t("💶 Няма заредени цени - колоната „Ед. Цена“ в Excel е празна (попълва се на ръка)."))
    if st.session_state.get("prices_error"):
        st.warning(t("⚠️ Цените не са записани в архива: {error}", error=st.session_state["prices_error"]))
    with st.expander(t("💶 Цени от Excel")):
        uploaded = st.file_uploader(t("Excel с цени („1. Оферта – софтуер.xlsx“ - колони Елемент и Ед. Цена):"),
                                    type=["xlsx"], key="prices_upload")
        if uploaded is not None and st.button(t("📥 Зареди цените"), key="load_prices",
                                              help=t("Заменя всички цени с тези от файла и ги записва - важат за "
                                                     "всички проекти.")):
            try:
                loaded = prices_from_excel(uploaded)
            except Exception as exc:  # noqa: BLE001 - грешен файл
                st.error(t("Файлът не може да се прочете: {error}", error=exc))
            else:
                if loaded.empty:
                    st.error(t("Във файла няма цени под „Ед. Цена“."))
                else:
                    store_prices(loaded)
                    st.success(t("✅ Заредени {n} цени от Excel. Създайте Excel наново.", n=len(loaded)))

def kss_stock():
    """
    Наличността за колоната „Наличност в склада“ в „Кол. сметка“ (Excel): {наименование в КСС: наличност}.
    По името в склада, иначе по stock_key (FP, AC, Тапа нямат код - само по името).
    """
    stock_df = st.session_state.get("stock_df")
    if stock_df is None:
        return {}
    by_name = {}
    for _, row in stock_df.iterrows():
        qty = pd.to_numeric(row.get("Остава"), errors="coerce")
        if pd.notna(qty):
            name = " ".join(str(row.get("Елемент", "")).split())
            by_name[name] = by_name.get(name, 0) + float(qty)
    available, _ = stock_available()
    result = {}
    for name in [n for n, _codes in KSS_ITEMS] + [n for n, *_rest in KSS_EXTRA]:
        if name in by_name:
            result[name] = by_name[name]
        elif stock_key(name) in available:
            result[name] = available[stock_key(name)]
    return result

def stock_need(stock_df, df_calc):
    """„Нужно за проекта“ за всеки ред на склада (по stock_key; без проект или без код - празно)."""
    need = project_requirements(df_calc) if not df_calc.empty else {}
    return [need.get(stock_key(name)) or None for name in stock_df["Елемент"].fillna("")]

def stock_shortages(df_calc):
    """
    Сравнение със складовата наличност: (не стигат [(ключ, нужни, на склад)], няма ги в склада [(ключ, нужни)]).
    Редовете в склада с един ключ се събират (H8 зелени + сиви). Празна наличност не се проверява;
    без нито една въведена наличност - няма предупреждения.
    """
    if st.session_state.get("stock_df") is None or df_calc.empty:
        return [], []
    available, listed = stock_available()
    if not available:
        return [], []
    need = project_requirements(df_calc)
    short = [(k, q, available[k]) for k, q in need.items() if k in available and q > available[k]]
    missing = [(k, q) for k, q in need.items() if k not in listed]
    return short, missing

def show_stock_warnings(df_calc):
    """Предупреждения при недостиг в склада (табове 1, 2 и 5)."""
    short, missing = stock_shortages(df_calc)
    if short:
        lines = [t("- **{k}**: нужни {q} бр., на склад {a} бр. (не стигат {d} бр.)",
                   k=k, q=f"{q:g}", a=f"{a:g}", d=f"{q - a:g}") for k, q, a in short]
        st.warning(t("⚠️ Не стигат в склада (таб „Складова наличност“):") + "\n" + "\n".join(lines))
    if missing:
        lines = [t("- **{k}**: нужни {q} бр.", k=k, q=f"{q:g}") for k, q in missing]
        st.warning(t("⚠️ Няма ги в складовата наличност:") + "\n" + "\n".join(lines))

def element_dims_and_area(elem_type, row):
    """
    Надпис с размерите (в см) и кофражната площ (m²) на реда, умножена по броя елементи.
    Площта е по панелите: ширина x височина на всеки панел и компенсатор TC от разположението
    (с челата); без ъглите EX / IN и без дървената дъска.
    """
    cnt = int(_row_float(row, "count", 1))
    h = _row_float(row, "height_cm", 300)
    t = _row_float(row, "thickness_cm", 25)
    if elem_type not in ("column", "wall", "l_wall", "u_wall", "t_wall"):
        return "", 0.0
    panels = element_layout(elem_type, row)
    hp = panel_height_cm(panels)  # H в надписа - височината на панелите (262 -> 265)
    panel_area = sum(sum(widths) * h_val for face in panels["faces"]
                     for h_val, widths in zip(panels["height_levels"], face["rows"])) / 10000.0
    if elem_type in ("l_wall", "u_wall", "t_wall"):
        # с „Дебелина стена A / B / C“: една дебелина (B=30 см) или по стени (стена A дебелина 30 см, ...)
        layout = element_layout(elem_type, row)
        t = layout["dims"]["t1"]
        b_str = f"B={t:g} см" if thickness_label(layout).startswith(dt("дебелина")) else thickness_label(layout)
    if elem_type == "column":
        w, l = t, _row_float(row, "l1_cm", 50)
        perimeter = 2 * (w + l)
        dim_str = f"{l:g}x{w:g} см, H={hp:g} см"   # A x B, както на чертежа
    elif elem_type == "wall":
        l = _row_float(row, "l1_cm", 500)
        perimeter = 2 * l
        dim_str = f"L={l:g} см, B={t:g} см, H={hp:g} см"
    elif elem_type == "l_wall":
        l1, l2 = _row_float(row, "l1_cm", 200), _row_float(row, "l2_cm", 200)
        perimeter = 2 * (l1 + l2)
        dim_str = f"L={l1:g}+{l2:g} см, {b_str}, H={hp:g} см"
    elif elem_type == "u_wall":
        l1, l2, l3 = _row_float(row, "l1_cm", 200), _row_float(row, "l2_cm", 200), _row_float(row, "l3_cm", 200)
        perimeter = 2 * (l1 + l2 + l3)
        dim_str = f"L={l1:g}+{l2:g}+{l3:g} см, {b_str}, H={hp:g} см"
    elif elem_type == "t_wall":
        l1, l2 = _row_float(row, "l1_cm", 200), _row_float(row, "l2_cm", 200)
        perimeter = 2 * (l1 + l2)
        offset = t_wall_offset_label(layout)
        dim_str = f"T: A={l1:g} см, B={l2:g} см, {offset + ', ' if offset else ''}{thickness_label(layout)}, H={hp:g} см"
    else:
        return "", 0.0
    return dim_str.replace(" см", " " + dt("см")), panel_area * cnt   # мерната единица на езика на документа

DISPLAY_TYPES = {
    "column": "Колона",
    "wall": "Права Стена",
    "l_wall": "L-образна Стена",
    "u_wall": "П-образна Стена",
    "t_wall": "T-образна Стена",
}

def build_drawing_elements(df):
    """Елементите за чертежите (PDF и Excel): наименование, тип, брой, разположение и сметка."""
    elements = []
    for _, row in df.iterrows():
        elem_type = str(row.get("type", "wall"))
        name = str(row.get("name", "Елемент"))
        layout = element_layout(elem_type, row)
        if layout is None:
            continue
        elem_bom = dict(get_element_teko_panels(elem_type, row))
        for acc_code, acc_qty in get_element_accessories(elem_type, row).items():
            elem_bom[acc_code] = elem_bom.get(acc_code, 0) + acc_qty
        elements.append({
            "name": format_element_label(elem_type, name),
            "wall_type": dt(DISPLAY_TYPES[elem_type]),
            "count": int(_row_float(row, "count", 1)),
            "layout": layout,
            "bom": elem_bom
        })
    return elements

# === Преглед на елементите под таблицата ===
@st.cache_data(show_spinner=False, max_entries=300)
def preview_top_png(row_items, plan_sig=""):
    """Изгледът отгоре (PNG) на реда; кешира се по стойностите на реда и разположението според склада."""
    row = dict(row_items)
    elem_type = str(row.get("type", "wall"))
    layout = element_layout(elem_type, row)
    return generate_top_view_buf(layout, format_element_label(elem_type, row.get("name", ""))).getvalue()

@st.cache_data(show_spinner=False, max_entries=300)
def preview_front_png(row_items, plan_sig=""):
    """Изгледът отпред (PNG) на реда; кешира се по стойностите на реда и разположението според склада."""
    row = dict(row_items)
    elem_type = str(row.get("type", "wall"))
    layout = element_layout(elem_type, row)
    return generate_front_view_buf(layout, format_element_label(elem_type, row.get("name", ""))).getvalue()

def preview_counts(elem_type, row):
    """Бройките за реда по групи: панели, ъгли, ригели, вертикализатори, ръкохватки, шпилки."""
    acc = get_element_accessories(elem_type, row)
    def group(word):
        return sum(qty for code, qty in acc.items() if word in code)
    # думите на български - на екрана се превеждат (t)
    return [("панела", sum(get_element_teko_panels(elem_type, row).values())),
            ("ъгли", group("ъгъл")),
            ("ригели", group("Ригел")),
            ("верт.", group("Вертикализатор")),
            ("ръкохватки", group("Ръкохватка")),
            ("шпилки", group("Шпилка"))]

def render_element_preview(idx, row):
    """Сгъваемо поле за един ред: размери, бройки, изглед отгоре и (с отметка) изглед отпред."""
    elem_type = str(row.get("type", "wall"))
    if elem_type not in DISPLAY_TYPES:
        return
    label = format_element_label(elem_type, row.get("name", ""))
    dim_str, _ = element_dims_and_area(elem_type, row)
    cnt = int(_row_float(row, "count", 1))
    ends = CLOSED_END_COLUMNS if elem_type == "t_wall" else CLOSED_END_COLUMNS[:2]
    closed = "" if elem_type == "column" else t(", затворени краища: {n}", n=sum(_closed_end(row, k) for k in ends))
    title = f"{label} · {t(DISPLAY_TYPES[elem_type])} — {t_item(dim_str)}{closed}, {cnt} {t('бр.')}"
    with st.expander(title):
        for w in check_element_dimensions(row):
            st.warning(w)
        row_items = tuple(row.items())
        plan_sig = stock_plan_signature(elem_type, row)
        try:
            counts = preview_counts(elem_type, row)
            top_png = preview_top_png(row_items, plan_sig)
        except Exception as e:
            st.error(t("Елементът не може да се начертае - проверете размерите ({error}).", error=e))
            return
        st.markdown(t("Количества ({n} бр.): ", n=cnt)
                    + " ".join(f":gray-badge[{qty} {t(word)}]" for word, qty in counts))
        st.image(top_png, caption=t("Изглед отгоре"), width=700)
        if st.checkbox(t("Покажи изгледа отпред"), key=f"preview_front_{idx}"):
            st.image(preview_front_png(row_items, plan_sig), caption=t("Изглед отпред"), width=900)

def format_element_label(elem_type, name):
    name_str = str(name).strip() if name else ""
    if elem_type == "column":
        return name_str if name_str.lower().startswith("колона") else f"{dt('Колона')} {name_str}".strip()
    elif elem_type == "wall":
        return name_str if name_str.lower().startswith("стена") else f"{dt('Стена')} {name_str}".strip()
    elif elem_type == "l_wall":
        return name_str if (name_str.lower().startswith("l-стена") or name_str.lower().startswith("стена")) else f"{dt('L-стена')} {name_str}".strip()
    elif elem_type == "u_wall":
        return name_str if (name_str.lower().startswith("п-стена") or name_str.lower().startswith("стена")) else f"{dt('П-стена')} {name_str}".strip()
    elif elem_type == "t_wall":
        return name_str if (name_str.lower().startswith("t-стена") or name_str.lower().startswith("стена")) else f"{dt('T-стена')} {name_str}".strip()
    return name_str

EXTRA_PAGE_MAX_PX = 3500  # страниците след първата - най-много толкова пиксела по дългата страна
PREVIEW_MAX_PX = 1460  # картината на чертежа на екрана - колкото е най-широкото показване в Streamlit

def process_uploaded_file(uploaded_file):
    """Чертежът като списък от изображения: всички страници на PDF, без ограничение на броя (детайлите,
    напр. страничен изглед с височината, често са на следващите страници); първата - 200 dpi."""
    uploaded_file.seek(0)
    if uploaded_file.type == "application/pdf":
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        images = []
        for i in range(doc.page_count):
            page = doc.load_page(i)
            dpi = 200 if i == 0 else min(200, int(EXTRA_PAGE_MAX_PX * 72 / max(page.rect.width, page.rect.height)))
            pix = page.get_pixmap(dpi=dpi)
            # точките направо в картина (без запис в PNG и отваряне обратно - същите точки, по-бързо)
            images.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        return images
    else:
        return [Image.open(uploaded_file)]

PDF_DIRECT_MAX_MB = 50      # Gemini приема PDF до 50 MB (над ~18 MB - през File API, в gemini_agent2.py)
PDF_DIRECT_MIN_NUMBERS = 20  # най-малко толкова числа в текстовия слой - иначе е сканиран / кóтите са линии
# Как да се разчете PDF (потребителят, 20.11.2026): автоматично - по текстовия слой; или избрано на ръка
READ_MODES = ["Автоматично", "Като текст (PDF)", "Като картина"]

def pdf_for_gemini(uploaded_file, mode="Автоматично"):
    """PDF-ът направо към Gemini (потребителят, 20.11.2026): кóтите от текстовия слой се четат като текст, без
    смаляване на голямата картина. Автоматично - само при текстов слой с числа (плотиран PDF); „Като текст“ -
    винаги; „Като картина“ - никога. Над 50 MB или не PDF - None: страниците като изображения, както преди
    (сканиран / принтиран чертеж, кóти като линии)."""
    if (mode == "Като картина" or uploaded_file.type != "application/pdf"
            or uploaded_file.size > PDF_DIRECT_MAX_MB * 1024 * 1024):
        return None
    uploaded_file.seek(0)
    data = uploaded_file.read()
    if mode == "Като текст (PDF)":
        return data
    numbers = 0
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            numbers += sum(any(ch.isdigit() for ch in word[4]) for word in page.get_text("words"))
            if numbers >= PDF_DIRECT_MIN_NUMBERS:
                return data
    return None

def uploaded_preview(uploaded_file):
    """Първата страница за екрана (смалена до ширината на показване) и броят страници. Прави се веднъж
    за качения файл и се пази, докато е качен - кликовете в таба не рисуват чертежа наново.
    Към Gemini отиват пълните страници от process_uploaded_file."""
    key = (uploaded_file.file_id, uploaded_file.size)
    saved = st.session_state.get("upload_preview")
    if saved and saved[0] == key:
        return saved[1], saved[2]
    uploaded_file.seek(0)
    if uploaded_file.type == "application/pdf":
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        n_pages = doc.page_count
        pix = doc.load_page(0).get_pixmap(dpi=200)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    else:
        n_pages = 1
        img = Image.open(uploaded_file)
        img.load()
    if img.width > PREVIEW_MAX_PX:  # както st.image смалява сам при всяко показване
        img = img.resize((PREVIEW_MAX_PX, int(img.height * PREVIEW_MAX_PX / img.width)), Image.BILINEAR)
    st.session_state["upload_preview"] = (key, img, n_pages)
    return img, n_pages

def generate_word_offer(client_name, project_name, offer_date, offer_type, price_per_m2, detailed_rows, total_area, subtotal, vat_amount, grand_total):
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

    r_comp = p_comp.add_run(dt("ТЕКО България ООД | ЕИК 208141542\n"))
    r_comp.bold = True
    r_comp.font.size = Pt(10.5)
    r_comp.font.color.rgb = BLUE_COLOR

    r_addr = p_comp.add_run(dt(
        "2700 Благоевград, ул. „Ал. Стамболийски” №9, ет. 1\n"
        "www.tekoform.com | e-mail: bulgaria@tekoform.com | тел: +359 879 044 188"
    ))
    r_addr.font.size = Pt(8.5)
    r_addr.font.color.rgb = RGBColor(90, 90, 90)

    p_title = doc.add_paragraph()
    run_title = p_title.add_run(dt("ОФЕРТА\nЗа закупуване на пластмасова кофражна система TEKO") if is_sale
                                else dt("ОФЕРТА\nЗа наемане на пластмасова кофражна система TEKO"))
    run_title.bold = True
    run_title.font.size = Pt(14)
    run_title.font.color.rgb = BLUE_COLOR
    p_title.paragraph_format.space_after = Pt(10)

    p_info = doc.add_paragraph()
    p_info.paragraph_format.line_spacing = 1.25
    p_info.paragraph_format.space_after = Pt(12)
    p_info.add_run(dt("До: ")).bold = True
    p_info.add_run(f"{client_name}\n")
    p_info.add_run(dt("Относно: ")).bold = True
    p_info.add_run(dt("Кофриране на стоманобетонови елементи за обект: „{project}“\n", project=project_name))
    p_info.add_run(dt("Дата: ")).bold = True
    p_info.add_run(f"{offer_date.strftime('%d.%m.%Y')}{dt(' г.')}")

    table = doc.add_table(rows=1, cols=6)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    hdr_cells = table.rows[0].cells
    headers = [dt(h) for h in ("Елемент", "Размери", "Брой", "Площ (m²)", "Ед. цена (€/m²)", "Обща сума (€)")]
    
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
        row_cells[2].text = f"{row_data['Брой']} {dt('бр.')}"
        row_cells[3].text = f"{row_data['Площ (m²)']:.2f} m²"
        row_cells[4].text = f"{price_per_m2:.2f} €"
        row_cells[5].text = f"{row_data['Обща сума (€)']:.2f} €"
        
        for i, c in enumerate(row_cells):
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i > 0 else WD_ALIGN_PARAGRAPH.LEFT
            for r in p.runs:
                r.font.size = Pt(9)

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    p_summary = doc.add_paragraph()
    p_summary.paragraph_format.line_spacing = 1.25
    p_summary.paragraph_format.space_after = Pt(12)
    
    p_summary.add_run(dt("Обща кофражна площ: {area} m²\n", area=f"{total_area:.2f}")).bold = True
    p_summary.add_run(dt("Обща стойност за покупка (без ДДС): {value} €\n" if is_sale
                         else "Обща стойност за наем (без ДДС): {value} €\n", value=f"{subtotal:.2f}")).bold = True
    p_summary.add_run(dt("ДДС (20%): {value} €\n", value=f"{vat_amount:.2f}"))
    
    run_total = p_summary.add_run(dt("ОБЩО ЗА ПЛАЩАНЕ: {value} €", value=f"{grand_total:.2f}"))
    run_total.bold = True
    run_total.font.size = Pt(11)
    run_total.font.color.rgb = BLUE_COLOR

    notes_p = doc.add_paragraph()
    notes_p.paragraph_format.space_before = Pt(8)
    notes_p.paragraph_format.space_after = Pt(12)
    notes_p.paragraph_format.line_spacing = 1.15
    
    run_th = notes_p.add_run(dt("Условия на офертата:\n"))
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
        r = notes_p.add_run(f"{dt(term)}\n")
        r.font.size = Pt(8.5)

    p_sign = doc.add_paragraph()
    p_sign.paragraph_format.space_before = Pt(8)
    p_sign.add_run(dt("С уважение,\n")).bold = True
    run_sign = p_sign.add_run(dt("Екипът на ТЕКО България ООД\nwww.tekoform.com"))
    run_sign.font.color.rgb = BLUE_COLOR
    run_sign.bold = True

    target_stream = io.BytesIO()
    doc.save(target_stream)
    target_stream.seek(0)
    return target_stream

try:
    api_key = st.secrets.get("GEMINI_API_KEY", "")
except FileNotFoundError:
    # Няма secrets.toml - ключът се въвежда в страничното меню
    api_key = ""

if "blueprint_data" not in st.session_state:
    st.session_state["blueprint_data"] = None
if "used_model" not in st.session_state:
    st.session_state["used_model"] = None

EMPTY_DF = pd.DataFrame(columns=DATA_COLUMNS)

if "edited_df" not in st.session_state:
    st.session_state["edited_df"] = EMPTY_DF.copy()
else:
    # стари колони и обща дебелина (архив, Gemini) -> „Дебелина стена A / B / C“
    st.session_state["edited_df"] = thickness_to_walls(columns_to_cm(st.session_state["edited_df"]))

with st.sidebar:
    st.header(t("⚙️ Настройки"))
    if not api_key:
        api_key = st.text_input(t("Въведете Gemini API Key:"), type="password", key="api_key_input")
    else:
        st.success(t("🔑 API Ключът е зареден!"))
    if app_password() and st.button(t("🚪 Изход"), key="logout",
                                    help=t("Изход от приложението; ако компютърът е запомнен - забравя го.")):
        st.session_state.update(password_correct=False, logged_out=True, clear_login_cookie=True)
        st.rerun()

# === ГОРНА ЛЕНТА И ВИД НА СТРАНИЦАТА „ПРОЕКТИ“ (по снимка 19 в reference/screenshots) ===
language_switch()  # езикът - горе вдясно, над лентата
st.markdown("""
    <style>
    .teko-header {display: flex; align-items: center; gap: 14px; background: #0f1b2d; color: #fff;
                  padding: 14px 22px; border-radius: 10px; margin-bottom: 18px;}
    .teko-logo {background: #0ea5e9; color: #fff; font-weight: 800; font-size: 20px; width: 42px;
                height: 42px; border-radius: 8px; display: flex; align-items: center; justify-content: center;}
    .teko-title {font-weight: 800; font-size: 19px; line-height: 1.2;}
    .teko-sub {color: #9fb3c8; font-size: 13px;}
    .teko-right {margin-left: auto; color: #9fb3c8; font-size: 13px;}
    .teko-projects-title {font-size: 26px !important; font-weight: 700; color: #0f172a; margin: 0;}
    .teko-right-head {text-align: right;}
    .st-key-new_project button {background: #0b84d8; color: #fff; border: none; font-weight: 600;}
    .st-key-new_project button:hover {background: #0a73bd; color: #fff;}
    .st-key-projects_table {background: #fff; border-radius: 10px; gap: 0;}
    .st-key-projects_head {background: #f8fafc; border-bottom: 1px solid #e5e7eb; padding: 12px 16px;}
    .st-key-projects_head p {color: #475569; font-weight: 700; font-size: 14px;}
    [class*="st-key-prow_"] {border-bottom: 1px solid #eef0f3; padding: 4px 16px;}
    [class*="st-key-prow_"] p {font-size: 14px; color: #1f2937;}
    .teko-mono {font-family: ui-monospace, Consolas, monospace; font-size: 13px; color: #475569;}
    [class*="st-key-open_"] button {padding: 0; justify-content: flex-start; text-align: left;}
    [class*="st-key-open_"] button p {color: #0b6fb8; font-weight: 500; font-size: 15px;}
    [class*="st-key-act_"] {flex-wrap: nowrap;}
    [class*="st-key-dup_"] button p, [class*="st-key-del_"] button p {white-space: nowrap;}
    [class*="st-key-dup_"] button p {color: #475569; font-size: 13px;}
    [class*="st-key-del_"] button p {color: #94a3b8; font-size: 13px;}
    </style>
    <div class="teko-header">
      <div class="teko-logo">TK</div>
      <div><div class="teko-title">""" + t("TEKO — Оптимизация на панели") + """</div>
           <div class="teko-sub">""" + t("AI система за кофражно планиране") + """</div></div>
      <div class="teko-right">""" + t("ТЕКО България ООД") + """</div>
    </div>
""", unsafe_allow_html=True)

# === ПЪРВА СТРАНИЦА: ПРОЕКТИ (архив в Google Sheets; без ключ в secrets - само докато страницата е отворена) ===
@st.cache_resource(show_spinner=False)
def connect_projects_archive():
    """Връзка с таблицата „TEKO Проекти“ (веднъж за приложението); (архив, грешка)."""
    try:
        info = st.secrets.get("gcp_service_account")
        sheet_id = st.secrets.get("PROJECTS_SHEET_ID", "")
    except FileNotFoundError:
        return None, None
    if not info or not sheet_id:
        return None, None
    try:
        return projects_store.connect_google_sheets(info, sheet_id), None
    except Exception as exc:  # noqa: BLE001 - архивът не е достъпен, приложението работи без него
        return None, f"{type(exc).__name__}: {exc}"

archive, archive_error = connect_projects_archive()
projects_store.use_archive(archive)

if "projects" not in st.session_state:
    st.session_state["projects"] = {}
if "current_project" not in st.session_state:
    st.session_state["current_project"] = None

STD_HEIGHT_CHOICES = ["270 см", "300 см"]

def open_project(pid):
    """Зарежда проекта в табовете: таблицата с елементите и стандартната височина."""
    project = projects_store.get_project(st.session_state["projects"], pid)
    if project is None:  # друго изпълнение на страницата е обновило списъка от Google преди записа
        st.session_state["open_project_failed"] = True
        return
    st.session_state["current_project"] = pid
    elements = project["elements"]
    st.session_state["edited_df"] = EMPTY_DF.copy() if elements is None else elements.copy()
    for key in ("excel_bytes", "delete_project_id", "drawing_notes", "delete_drawing"):
        st.session_state.pop(key, None)
    reset_table_editors()
    st.session_state["blueprint_data"] = None
    h = project["std_height_cm"]
    st.session_state["std_height_cm"] = h
    st.session_state["stock_layout_on"] = bool(project.get("stock_layout", False))
    choice = f"{h} см"
    if choice in STD_HEIGHT_CHOICES:
        st.session_state["std_height_choice_cm"] = choice
    else:
        st.session_state["std_height_choice_cm"] = "Друга"
        st.session_state["std_height_other_cm"] = h

def save_current_project():
    """Записва таблицата и стандартната височина в отворения проект."""
    pid = st.session_state["current_project"]
    if pid in st.session_state["projects"]:
        projects_store.save_project(st.session_state["projects"], pid,
                                    elements=st.session_state["edited_df"],
                                    std_height_cm=st.session_state.get("std_height_cm", DEFAULT_HEIGHT_CM),
                                    stock_layout=st.session_state.get("stock_layout_on", False))

def close_project():
    save_current_project()
    st.session_state["current_project"] = None

def create_project():
    pid = projects_store.new_project(st.session_state["projects"],
                                     st.session_state.get("new_project_name", ""),
                                     st.session_state.get("new_project_client", ""),
                                     st.session_state.get("new_project_date"),
                                     std_height_cm=DEFAULT_HEIGHT_CM)
    for key in ("new_project_name", "new_project_client", "new_project_date"):
        st.session_state.pop(key, None)
    open_project(pid)

def duplicate_project(pid):
    projects_store.duplicate_project(st.session_state["projects"], pid)

def delete_project(pid):
    projects_store.delete_project(st.session_state["projects"], pid)
    st.session_state.pop("delete_project_id", None)

def render_projects_page():
    _, page, _ = st.columns([1, 6, 1])
    with page:
        col_h, col_new = st.columns([5, 1], vertical_alignment="center")
        col_h.markdown(f'<p class="teko-projects-title">{t("Проекти")}</p>', unsafe_allow_html=True)
        with col_new.container(key="new_project"):
            with st.popover(t("Нов проект"), use_container_width=True):
                st.text_input(t("Име на проекта:"), key="new_project_name")
                st.text_input(t("Клиент:"), key="new_project_client")
                st.date_input(t("Дата:"), key="new_project_date")
                st.button(t("Създай и отвори"), type="primary", on_click=create_project, use_container_width=True)

        if archive_error:
            st.error(t("Архивът в Google не е достъпен ({error}). Проектите се пазят само докато страницата е "
                       "отворена.", error=archive_error))
        elif not projects_store.has_archive():
            st.caption(t("Без архив (няма ключ за Google в secrets): проектите се губят при презареждане."))
        else:
            try:
                projects_store.refresh(st.session_state["projects"])
            except Exception as exc:  # noqa: BLE001
                st.error(t("Списъкът не може да се зареди от Google: {error}", error=exc))

        if st.session_state.pop("open_project_failed", False):
            st.warning(t("Презаредете страницата (F5). Проектът е създаден и записан, но не можа да се отвори "
                         "веднага, защото бутонът „Създай и отвори“ беше натиснат твърде бързо след въвеждането "
                         "на името. Следващия път изчакайте 2-3 секунди, преди да натиснете бутона."))

        rows = projects_store.project_rows(st.session_state["projects"])
        if not rows:
            st.info(t("ℹ️ Няма проекти. Натиснете „Нов проект“."))
            return
        widths = [3.6, 2.8, 1.4, 1.7, 2.3]
        with st.container(border=True, key="projects_table"):
            with st.container(key="projects_head"):
                head = st.columns(widths, vertical_alignment="center")
                for col, title in zip(head, ["Име", "Клиент", "Дата", "Последна промяна"]):
                    col.markdown(t(title))
                head[-1].markdown(f'<p class="teko-right-head">{t("Действия")}</p>', unsafe_allow_html=True)
            for row in rows:
                pid = row["id"]
                with st.container(key=f"prow_{pid}"):
                    c_name, c_client, c_date, c_mod, c_act = st.columns(widths, vertical_alignment="center")
                    actions = c_act.container(horizontal=True, horizontal_alignment="right", gap="small",
                                              key=f"act_{pid}")
                    c_name.button(row["Име"], key=f"open_{pid}", type="tertiary", on_click=open_project, args=(pid,))
                    c_client.markdown(row["Клиент"] or "")
                    c_date.markdown(f'<span class="teko-mono">{row["Дата"]}</span>', unsafe_allow_html=True)
                    c_mod.markdown(f'<span class="teko-mono">{row["Последна промяна"]}</span>',
                                   unsafe_allow_html=True)
                    actions.button(t("Дублирай"), key=f"dup_{pid}", type="tertiary", width="content", on_click=duplicate_project,
                                 args=(pid,))
                    if st.session_state.get("delete_project_id") == pid:
                        actions.button(t("Потвърди"), key=f"delok_{pid}", type="primary", width="content", on_click=delete_project,
                                     args=(pid,),
                                     help=t("Проектът се маха от списъка (в архива остава с отметка „Изтрит“)."))
                    else:
                        actions.button(t("Изтрий"), key=f"del_{pid}", type="tertiary", width="content",
                                     on_click=st.session_state.__setitem__, args=("delete_project_id", pid))

current = projects_store.get_project(st.session_state["projects"], st.session_state["current_project"])
if current is None:
    st.session_state["current_project"] = None
    render_projects_page()
    st.stop()

def rename_current_project(pid):
    """Записва новото име, клиент и дата от „✏️ Промени“."""
    projects_store.rename_project(st.session_state["projects"], pid,
                                  st.session_state.get(f"rename_name_{pid}", ""),
                                  st.session_state.get(f"rename_client_{pid}", ""),
                                  st.session_state.get(f"rename_date_{pid}"))
    for key in (f"rename_name_{pid}", f"rename_client_{pid}", f"rename_date_{pid}"):
        st.session_state.pop(key, None)

col_proj, col_edit, col_back = st.columns([4, 1, 1], vertical_alignment="center")
col_proj.subheader(f"📁 {current['name']}" + (f" · {current['client']}" if current["client"] else ""))
with col_edit.popover(t("✏️ Промени"), use_container_width=True,
                      help=t("Промяна на името на проекта, клиента (възложителя) и датата.")):
    pid = current["id"]
    st.text_input(t("Име на проекта:"), value=current["name"], key=f"rename_name_{pid}")
    st.text_input(t("Клиент (възложител):"), value=current["client"], key=f"rename_client_{pid}")
    st.date_input(t("Дата:"), value=current["date"], key=f"rename_date_{pid}")
    st.button(t("Запази"), type="primary", on_click=rename_current_project, args=(pid,), use_container_width=True)
col_back.button(t("← Проекти"), on_click=close_project, use_container_width=True,
                help=t("Записва таблицата и се връща към списъка с проекти."))

load_stock_once()  # преди табовете - предупрежденията за наличността са и в табове 1 и 2
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([t(label) for label in (
    "📐 Чертеж и Редактиране",
    "🧱 Кофражни Елементи и Панели TEKO",
    "📄 PDF Чертежи",
    "📄 Оферта",
    "📦 Складова наличност",
    "🏗️ 3D план на етажа"
)])

def element_column_config():
    """Колоните на таблицата с елементите (една и съща за всеки чертеж)."""
    return {
        "type": st.column_config.SelectboxColumn(t("Тип елемент"), options=list(TYPE_LABELS), required=True, default="wall", width="auto",
                                                 format_func=lambda code: t(TYPE_LABELS.get(code, code))),
        "name": st.column_config.TextColumn(t("Наименование / Маркировка"), width="auto"),
        "count": st.column_config.NumberColumn(t("Брой"), min_value=1, step=1, default=1, width="auto"),
        "l1_cm": st.column_config.NumberColumn(t("Стена A (см)"), format="%g", width="auto",
                                               help=t("При права стена и колона - дължината")),
        "thickness1_cm": st.column_config.NumberColumn(t("Дебелина стена A (см)"), format="%g", width="auto"),
        "l2_cm": st.column_config.NumberColumn(t("Стена B (см)"), format="%g", width="auto"),
        "thickness2_cm": st.column_config.NumberColumn(t("Дебелина стена B (см)"), format="%g", width="auto",
                                                       help=t("L-, П- и Т-стена; празна = като стена A "
                                                              "(попълва се само когато е различна)")),
        "l3_cm": st.column_config.NumberColumn(t("Стена C (см)"), format="%g", width="auto",
                                               help=t("При Т-стена: от левия край на полката до лявото лице "
                                                      "на реброто; празно = реброто е в средата")),
        "thickness3_cm": st.column_config.NumberColumn(t("Дебелина стена C (см)"), format="%g", width="auto",
                                                       help=t("П-стена; при Т-стена - полката вляво от реброто "
                                                              "(дължината „Стена C“); празна = като стена A "
                                                              "(попълва се само когато е различна)")),
        "height_cm": st.column_config.NumberColumn(t("Височина (см)"), format="%g", width="auto"),
        "closed_end_1": st.column_config.CheckboxColumn(t("Затворен край 1"), default=True, width="auto"),
        "closed_end_2": st.column_config.CheckboxColumn(t("Затворен край 2"), default=True, width="auto"),
        "closed_end_3": st.column_config.CheckboxColumn(t("Затворен край 3 (само T-стена)"), default=True, width="auto")
    }

SOURCE_NOTE_PREFIX = "📍 "   # бележка „откъде е елементът“ (source от Gemini) - отделно от забележките

# Двойна проверка (потребителят, 20.11.2026): полетата от сравнението - с имената на колоните в таблицата
DOUBLE_CHECK_LABELS = {"count": "Брой", "l1_cm": "Стена A", "thickness_cm": "Дебелина стена A",
                       "l2_cm": "Стена B", "thickness2_cm": "Дебелина стена B", "l3_cm": "Стена C",
                       "thickness3_cm": "Дебелина стена C", "height_cm": "Височина",
                       "closed_end_1": "Затворен край 1", "closed_end_2": "Затворен край 2",
                       "closed_end_3": "Затворен край 3"}

def double_check_notes(differences):
    """Разликите между двете разчитания (gemini_agent2._compare_readings) - като забележки на AI."""
    def show(value):
        if isinstance(value, bool):
            return t("да") if value else t("не")
        return "-" if value is None else f"{value:g}" if isinstance(value, (int, float)) else str(value)

    if not differences:
        return [t("🔁 Двойна проверка: двете разчитания съвпадат.")]
    notes = []
    for d in differences:
        if d["kind"] == "failed":
            notes.append(t("🔁 Двойната проверка не мина: {error}", error=d.get("error", "")))
        elif d["kind"] == "only_first":
            notes.append(t("🔁 Двойна проверка: {name} е само в първото разчитане (в таблицата е) - проверете го.",
                           name=d["name"]))
        elif d["kind"] == "only_second":
            notes.append(t("🔁 Двойна проверка: {name} е само във второто разчитане (не е в таблицата) - проверете "
                           "чертежа.", name=d["name"]))
        else:
            notes.append(t("🔁 Двойна проверка: {name} - {field}: {first} (в таблицата) / {second} (второ "
                           "разчитане).", name=d["name"], field=t(DOUBLE_CHECK_LABELS.get(d["field"], d["field"])),
                           first=show(d["first"]), second=show(d["second"])))
    return notes

def render_drawing_notes():
    """
    Забележките на AI (противоречия и несигурности в чертежа) - точно над таблица 1, по чертежи, с по-малък шрифт.
    Пазят се докато страницата е отворена.
    """
    notes = st.session_state.get("drawing_notes", {})
    numbers = {name: i for i, (name, _part) in enumerate(drawing_groups(st.session_state["edited_df"]), 1)}
    shown = [(name, items) for name, items in notes.items() if items and name in numbers]
    if not shown:
        return
    with st.container(key="drawing_notes_box"):
        st.markdown("<style>.st-key-drawing_notes_box [data-testid='stAlert'] p, "
                    ".st-key-drawing_notes_box [data-testid='stAlert'] li {font-size: 13px; line-height: 1.35;}</style>",
                    unsafe_allow_html=True)
        for name, items in shown:
            remarks = [note for note in items if not str(note).startswith(SOURCE_NOTE_PREFIX)]
            sources = [note[len(SOURCE_NOTE_PREFIX):] for note in items if str(note).startswith(SOURCE_NOTE_PREFIX)]
            if remarks:
                st.warning("**" + t("⚠️ Забележки на AI - Чертеж {i}: {name}", i=numbers[name], name=name) + "**\n"
                           + "\n".join(f"- {t(note)}" for note in remarks))   # t() - само TRUNCATED_NOTE
            if sources:   # откъде е всеки елемент (страница, оси) - сгънато, може да са много
                with st.expander(t("📍 Откъде е всеки елемент - Чертеж {i}: {name} ({n})", i=numbers[name],
                                   name=name, n=len(sources))):
                    st.markdown("\n".join(f"- {s}" for s in sources))

def render_drawing_manager(groups):
    """Чертежите в проекта: преименуване и изтриване (с потвърждение). Незаписаните промени в таблиците се губят."""
    with st.expander(t("📄 Чертежи в проекта ({n}) - преименуване и изтриване", n=len(groups))):
        st.caption(t("Първо натиснете „💾 Запази и Изчисли“ - незаписаните промени в таблиците се губят."))
        for i, (dname, part) in enumerate(groups):
            c_name, c_save, c_del = st.columns([4, 1, 1], vertical_alignment="bottom")
            if not dname:   # въведените ръчно - без име, затова само изтриване (потребителят, 23.11.2026)
                c_name.text_input(t("Без чертеж ({n} елемента)", n=len(part)),
                                  value=t("Без чертеж (въведени ръчно)"), disabled=True, key=f"drawing_name_{i}_")
            else:
                new_name = c_name.text_input(t("Чертеж {i} ({n} елемента)", i=i + 1, n=len(part)), value=dname,
                                             key=f"drawing_name_{i}_{dname}")
            if dname and c_save.button(t("✏️ Преименувай"), key=f"rename_drawing_{i}", use_container_width=True):
                others = [n for n, _p in groups if n != dname]
                new_name = new_name.strip()
                if not new_name or new_name in others:
                    st.warning(t("Името е празно или вече има такъв чертеж."))
                else:
                    df = st.session_state["edited_df"]
                    df.loc[df["drawing"].map(drawing_name) == dname, "drawing"] = new_name
                    notes = st.session_state.get("drawing_notes", {})
                    if dname in notes:
                        notes[new_name] = notes.pop(dname)
                    for store_key in ("drawing_files", "drawing_places"):
                        saved = st.session_state.get(store_key, {})
                        if drawing_file_key(dname) in saved:
                            saved[drawing_file_key(new_name)] = saved.pop(drawing_file_key(dname))
                    reset_table_editors()
                    save_current_project()
                    st.rerun()
            if st.session_state.get("delete_drawing") == dname:
                c_del.button(t("Отказ"), key=f"cancel_delete_drawing_{i}", use_container_width=True,
                             on_click=lambda: st.session_state.pop("delete_drawing", None))
                st.warning(t("Да се изтрият ли {n} елемента на „{name}“?", n=len(part),
                             name=dname or t("Без чертеж (въведени ръчно)")))
                if st.button(t("🗑 Да, изтрий чертежа") if dname else t("🗑 Да, изтрий таблицата"),
                             key=f"confirm_delete_drawing_{i}", type="primary"):
                    st.session_state["edited_df"] = join_drawing_groups([g for g in groups if g[0] != dname])
                    st.session_state.get("drawing_notes", {}).pop(dname, None)
                    st.session_state.get("drawing_files", {}).pop(drawing_file_key(dname), None)
                    st.session_state.get("drawing_places", {}).pop(drawing_file_key(dname), None)
                    st.session_state.pop("delete_drawing", None)
                    reset_table_editors()
                    save_current_project()
                    st.session_state.pop("excel_bytes", None)
                    st.rerun()
            elif c_del.button(t("🗑 Изтрий"), key=f"delete_drawing_{i}", use_container_width=True):
                st.session_state["delete_drawing"] = dname
                st.rerun()

with tab1:
    st.header(t("1. Избор на начин за въвеждане на елементи"))
    
    input_mode = st.radio(
        t("Изберете режим на работа:"),
        ["🤖 Автоматично разчитане от чертежи", "⌨️ Ръчно въвеждане (Таблица)"],
        format_func=t,
        horizontal=True,
        key="input_mode"
    )

    if input_mode == "🤖 Автоматично разчитане от чертежи":
        st.subheader(t("Качване на чертеж и AI разчитане"))
        uploaded_file = st.file_uploader(t("Изберете чертеж (PDF, PNG, JPG):"), type=["pdf", "png", "jpg", "jpeg"],
                                         key="blueprint_upload")

        if uploaded_file:
            col_img, col_actions = st.columns([1, 1])
            with col_img:
                st.subheader(t("🖼️ Преглед на файла"))
                try:
                    preview_img, n_pages = uploaded_preview(uploaded_file)
                    st.image(preview_img, use_container_width=True,
                             caption=t("Качен чертеж") + (t(" - стр. 1 от {n}; към AI отиват всички {n}", n=n_pages)
                                                          if n_pages > 1 else ""))
                    file_ok = True
                except Exception as e:
                    st.error(t("Грешка при зареждането: {error}", error=e))
                    file_ok = False

            with col_actions:
                st.subheader(t("AI Разчитане"))
                
                selected_model = st.selectbox(
                    t("Избери AI модел за разчитане:"),
                    options=[
                        "gemini-3.1-pro",
                        "gemini-2.5-pro",
                        "gemini-3.8-flash",
                        "gemini-3.6-flash"
                    ],
                    index=0,
                    help=t("Изберете кой модел на Gemini да анализира чертежа."),
                    key="ai_model"
                )
                read_mode = "Като картина"
                if uploaded_file.type == "application/pdf":
                    read_mode = st.radio(
                        t("Как да се разчете чертежът:"), READ_MODES, format_func=t, horizontal=True,
                        key="read_mode",
                        help=t("Автоматично: плотиран PDF (с текст вътре) - като PDF, кóтите се четат от текста; "
                               "сканиран или принтиран PDF (без текст) - като картини на страниците. Изберете "
                               "на ръка, ако автоматичният избор не е подходящ (напр. кóтите са линии, а не текст)."))
                double_check = st.checkbox(
                    t("🔁 Двойна проверка (разчита чертежа два пъти и сравнява)"), value=False, key="double_check",
                    help=t("Разликите между двете разчитания излизат в забележките на AI - там проверете таблицата. "
                           "Отнема двойно време и изразходва двойно от безплатното ограничение на ключа."))

                # Чертежът се добавя в отделна таблица под таблиците на вече разчетените (18.11.2026);
                # повторно разчитане на същия файл - замяна на елементите му или нов чертеж
                drawing = uploaded_file.name
                existing = [name for name, _part in drawing_groups(st.session_state["edited_df"]) if name]
                replace_drawing = False
                if drawing in existing:
                    choice = st.radio(t("Чертеж „{name}“ вече е разчетен в този проект:", name=drawing),
                                      ["Замени елементите му", "Добави като нов чертеж"], format_func=t,
                                      key="drawing_again")
                    replace_drawing = choice == "Замени елементите му"
                    if not replace_drawing:
                        drawing = unique_drawing_name(drawing, existing)
                elif existing:
                    st.caption(t("Елементите ще се добавят като Чертеж {n} под вече разчетените.",
                                 n=len(drawing_groups(st.session_state["edited_df"])) + 1))

                if not api_key:
                    st.warning(t("⚠️ Моля, въведете Gemini API Key в страничното меню."))
                else:
                    if st.button(t("🔍 Разчети чертежа с Vision AI"), type="primary", use_container_width=True,
                                 key="read_blueprint"):
                        # пълните страници за Gemini се рисуват само тук, не при всеки клик
                        processed_img = pdf_bytes = None
                        if file_ok:
                            try:
                                # PDF с текстов слой - направо; иначе страниците като изображения
                                pdf_bytes = pdf_for_gemini(uploaded_file, read_mode)
                                if not pdf_bytes:
                                    processed_img = process_uploaded_file(uploaded_file)
                            except Exception as e:
                                st.error(t("Грешка при зареждането: {error}", error=e))
                        if processed_img or pdf_bytes:
                            with st.spinner(t("Извличане на вертикални кофражни елементи...")):
                                try:
                                    res = analyze_blueprint(processed_img, api_key, model_choice=selected_model,
                                                            notes_language=st.session_state.get("lang", "bg"),
                                                            pdf_bytes=pdf_bytes, double_check=double_check)
                                    if isinstance(res, tuple):
                                        blueprint_data, used_model = res
                                    else:
                                        blueprint_data, used_model = res, selected_model

                                    st.session_state["blueprint_data"] = blueprint_data
                                    st.session_state["used_model"] = used_model
                                    elements_list = blueprint_data.get("elements", [])
                                    # откъде е всеки елемент - само бележка, не колона (потребителят, 20.11.2026)
                                    sources = [SOURCE_NOTE_PREFIX + f"{e.get('name') or '?'}: {e.pop('source')}"
                                               for e in elements_list if isinstance(e, dict) and e.get("source")]
                                    for e in elements_list:
                                        if isinstance(e, dict):
                                            e.pop("source", None)
                                    # местата в плана - за таб 6 (потребителят, 24.11.2026), не колона
                                    st.session_state.setdefault("drawing_places", {})[drawing_file_key(drawing)] = [
                                        {"type": e.get("type"), "name": e.get("name"), "places": e.pop("places", None)}
                                        for e in elements_list if isinstance(e, dict)]

                                    df_ai = columns_to_cm(pd.DataFrame(elements_list))
                                    for col in DATA_COLUMNS:
                                        if col not in df_ai.columns:
                                            df_ai[col] = True if col in CLOSED_END_COLUMNS else None
                                    # затворени краища от Gemini: false - краят опира в друг елемент (отворен);
                                    # true и null (не се вижда) - затворен, както по подразбиране
                                    for col in CLOSED_END_COLUMNS:
                                        df_ai[col] = [str(v).lower() != "false" for v in df_ai[col]]
                                    df_ai["drawing"] = drawing
                                    groups = drawing_groups(st.session_state["edited_df"])
                                    new_part = thickness_to_walls(df_ai)
                                    if replace_drawing:   # на мястото на старите елементи на чертежа
                                        groups = [(n, new_part if n == drawing else part) for n, part in groups]
                                    else:
                                        groups.append((drawing, new_part))
                                    st.session_state["edited_df"] = join_drawing_groups(groups)
                                    reset_table_editors()
                                    save_current_project()   # платеното разчитане не се губи при F5
                                    st.session_state.pop("excel_bytes", None)
                                    st.success(t("✅ Готово! Разчетено с: **{model}**", model=used_model) + " " +
                                               t("Чертеж „{name}“: {n} елемента - записани в проекта.",
                                                 name=drawing, n=len(new_part)) + " " +
                                               (t("Изпратен като PDF (с текста в него).") if pdf_bytes else
                                                t("Изпратен като изображения на страниците.")) +
                                               (" " + t("Качен през File API (голям файл) и изтрит след "
                                                        "разчитането.") if blueprint_data.get("file_api") else ""))
                                    # противоречия и несигурности в чертежа - потребителят проверява таблицата;
                                    # показват се точно над таблица 1 (render_drawing_notes)
                                    notes = list(blueprint_data.get("notes") or [])
                                    if double_check:
                                        notes += double_check_notes(blueprint_data.get("double_check") or [])
                                    st.session_state.setdefault("drawing_notes", {})[drawing] = notes + sources
                                    # самият чертеж - за фона в „3D план на етажа“ (без ново качване в таб 6)
                                    keep_drawing_file(drawing, uploaded_file)
                                except Exception as e:
                                    st.error(t("Грешка при анализа: {error}", error=e))
    else:
        st.subheader(t("⌨️ Ръчно въвеждане и управление в таблицата"))
        st.markdown(t(MANUAL_HELP_BG))

    st.divider()
    st.subheader(t("📏 Стандартна височина на етажа"))
    std_choice = st.radio(
        t("Стандартна височина за всички елементи:"),
        ["270 см", "300 см", "Друга"],
        format_func=t,
        index=0,
        horizontal=True,
        key="std_height_choice_cm"
    )
    if std_choice == "Друга":
        std_height = st.number_input(t("Височина (см):"), min_value=60, max_value=1200, value=DEFAULT_HEIGHT_CM,
                                     step=10, key="std_height_other_cm")
    else:
        std_height = int(std_choice.split()[0])
    st.session_state["std_height_cm"] = std_height
    st.caption(t("Елементите с празна „Височина (см)“ в таблицата се смятат с {h} см. Височината, въведена в "
                 "таблицата, остава с предимство.", h=std_height))
    if st.button(t("↕️ Приложи {h} см към всички редове", h=std_height), key="apply_std_height",
                 help=t("Записва стандартната височина във всички редове на таблицата, включително разчетените от "
                        "чертежа. Незапазените промени в таблицата се губят - първо натиснете „Запази и Изчисли“.")):
        df_all = st.session_state["edited_df"].copy()
        if df_all.empty:
            st.info(t("ℹ️ Таблицата е празна - няма редове за промяна."))
        else:
            df_all["height_cm"] = std_height
            st.session_state["edited_df"] = df_all
            reset_table_editors()  # таблиците се показват наново с новите височини
            st.success(t("✅ Височина {h} см е записана в {n} реда.", h=std_height, n=len(df_all)))

    st.checkbox(t("📦 Редене според складовата наличност"), key="stock_layout_on", on_change=save_current_project,
                help=t("Панелите се редят по алгоритъма. Когато някой панел не стига в склада (таб „Складова "
                       "наличност“), той се заменя с най-малко по-малки налични панели в същия ред, а ако не може - "
                       "елементът се пренарежда по височина (напр. 300 = 120 + 120 + 60). Най-големите елементи "
                       "вземат от склада първи. Отметката се пази в проекта."))
    render_drawing_notes()   # забележките на AI - точно над таблица 1
    st.subheader(t("✏️ Таблица с вертикални кофражни елементи"))
    
    st.markdown("""
        <style>
        [data-testid="stDataEditor"] th div {
            font-size: 11.5px !important;
            white-space: normal !important;
            overflow: visible !important;
        }
        </style>
    """, unsafe_allow_html=True)

    groups = drawing_groups(st.session_state["edited_df"]) or [("", st.session_state["edited_df"])]
    named = any(name for name, _part in groups)
    if named:
        render_drawing_manager(groups)
    with st.form("manual_elements_form"):
        edited_groups = []
        for i, (dname, part) in enumerate(groups):
            if named:   # отделна таблица за всеки чертеж, под заглавие
                title = (t("📄 Чертеж {i}: {name}", i=i + 1, name=dname) if dname
                         else t("📄 Без чертеж (въведени ръчно)"))
                st.markdown(f"#### {title}")
                st.caption(t("{n} елемента", n=len(part)))
            edited = st.data_editor(
                part,
                num_rows="delete",  # нов ред - само с „➕ Добави елемент“, без „+“ под всяка колона
                column_config=element_column_config(),
                column_order=TABLE_COLUMNS,
                hide_index=True,
                use_container_width=True,
                key=f"{TABLE_EDITOR_KEY}_{i}"
            )
            edited_groups.append((dname, edited))

        # „Към кой чертеж?“ - съществуващите таблици, „Без чертеж“ (и когато я няма - създава се) и нова таблица
        # с име (потребителят, 23.11.2026); формата не презарежда при избор, затова името е винаги видимо
        drawing_options = list(range(len(groups)))
        if all(name for name, _part in groups):
            drawing_options.append("manual")
        drawing_options.append("new")
        col_new_type, col_drawing, col_new_name, col_add = st.columns([2, 2, 2, 1], vertical_alignment="bottom")
        target = col_drawing.selectbox(
            t("Към кой чертеж?"), options=drawing_options, index=len(groups) - 1,
            format_func=lambda i: (t("➕ Нова таблица…") if i == "new"
                                   else t("Без чертеж (въведени ръчно)") if i == "manual" or not groups[i][0]
                                   else t("Чертеж {i}: {name}", i=i + 1, name=groups[i][0])),
            key="new_element_drawing")
        new_table_name = col_new_name.text_input(
            t("Име на новата таблица"), placeholder=t("напр. Етаж 2 - ръчно"), key="new_table_name",
            help=t("Само при „➕ Нова таблица…“ в „Към кой чертеж?“."))
        new_type = col_new_type.selectbox(t("Какъв елемент да се добави?"), options=list(TYPE_LABELS), index=None,
                                          format_func=lambda code: t(TYPE_LABELS.get(code, code)),
                                          placeholder=t("Изберете тип елемент"), key="new_element_type")
        new_table_name = (new_table_name or "").strip()
        add_btn = col_add.form_submit_button(t("➕ Добави елемент"), use_container_width=True,
                                             help=t("Записва таблицата и добавя нов ред от избрания тип "
                                                    "(1 бр., затворени краища)."), key="add_element")
        submit_btn = st.form_submit_button(t("💾 Запази и Изчисли"), type="primary", use_container_width=True,
                                           key="save_table")
        if add_btn and new_type is None:
            st.warning(t("Изберете тип елемент и натиснете отново „➕ Добави елемент“."))
        elif add_btn and target == "new" and (not new_table_name
                                              or new_table_name in [name for name, _part in groups]):
            st.warning(t("Напишете име на новата таблица, което го няма в проекта, и натиснете отново "
                         "„➕ Добави елемент“."))
        elif add_btn or submit_btn:
            if add_btn:
                # новият ред - с всички колони на таблицата, иначе празните (дължини, височина ...) изчезват;
                # в края на избрания чертеж, а „Без чертеж“ (когато я няма) и новата таблица - най-отдолу
                if target in ("manual", "new"):
                    edited_groups.append(("" if target == "manual" else new_table_name,
                                          edited_groups[0][1].iloc[0:0]))
                    target = len(edited_groups) - 1
                dname, part = edited_groups[target]
                new_row = pd.DataFrame([{"type": new_type, "name": "", "count": 1, "closed_end_1": True, "closed_end_2": True,
                                         "closed_end_3": True}], columns=part.columns)
                edited_groups[target] = (dname, pd.concat([part, new_row], ignore_index=True))
                st.session_state.pop("new_element_type", None)  # изборът се изчиства за следващия елемент
                if target == len(edited_groups) - 1:   # новата таблица е последна - избрана за следващия елемент
                    st.session_state.pop("new_element_drawing", None)
                st.session_state.pop("new_table_name", None)
            reset_table_editors()  # таблиците се показват наново с новия ред
            st.session_state["edited_df"] = thickness_to_walls(join_drawing_groups(edited_groups), migrate=False)
            save_current_project()
            st.session_state.pop("excel_bytes", None)  # старият Excel вече не отговаря на таблицата
            # Таблицата се разпознава по данните си: без презареждане следващата промяна
            # се прави в старата таблица и при следващия запис се губи (връщат се предишните стойности).
            st.session_state["table_saved"] = True
            st.rerun()
    if st.session_state.pop("table_saved", False):
        st.success(t("✅ Данните са запазени и преизчислени успешно! Можете да проверите резултатите в следващите табове."))
    df_saved = fill_default_height(st.session_state["edited_df"],
                                   st.session_state.get("std_height_cm", DEFAULT_HEIGHT_CM))
    update_stock_plan(df_saved)
    show_stock_layout_notes(df_saved)
    show_stock_warnings(df_saved)

    st.subheader(t("👁 Преглед на елементите"))
    st.caption(t("Прегледът показва записаните данни - обновява се след „Запази и Изчисли“. Полетата се отварят без "
                 "презареждане; отметката „Покажи изгледа отпред“ презарежда страницата, затова първо запишете "
                 "промените в таблицата."))
    df_preview = fill_default_height(st.session_state["edited_df"],
                                     st.session_state.get("std_height_cm", DEFAULT_HEIGHT_CM))
    if df_preview.empty:
        st.info(t("ℹ️ Няма записани елементи за преглед."))
    preview_groups = drawing_groups(df_preview)
    preview_named = any(name for name, _part in preview_groups)
    for i, (dname, part) in enumerate(preview_groups):
        if preview_named:   # по чертежи, както таблиците
            st.markdown("**" + (t("📄 Чертеж {i}: {name}", i=i + 1, name=dname) if dname
                                else t("📄 Без чертеж (въведени ръчно)")) + "**")
        for idx, row in part.iterrows():
            render_element_preview(idx, row)

# Windows не рисува флагчета-емоджи (показва „DE“) - шрифт само с флагчетата, за падащите менюта; без него
# (напр. без интернет) остават двете букви
FLAG_FONT_CSS = """
    <style>
    @font-face {font-family: "Twemoji Country Flags"; font-display: swap; unicode-range: U+1F1E6-1F1FF;
        src: url("https://cdn.jsdelivr.net/npm/country-flag-emoji-polyfill@0.1.8/dist/TwemojiCountryFlags.woff2")
             format("woff2");}
    [data-testid="stSelectbox"] *, [role="listbox"] *, [role="option"], [role="option"] * {
        font-family: "Twemoji Country Flags", "Source Sans", sans-serif !important;}
    </style>
"""

def doc_language_select(key, on_change=None):
    """Падащо меню до бутона на файла: езикът на документа (doc_lang) с флагче, по подразбиране български."""
    st.markdown(FLAG_FONT_CSS, unsafe_allow_html=True)
    return st.selectbox(t("Език на документа:"), list(DOC_LANGUAGES),
                        format_func=lambda code: f"{DOC_FLAGS[code]} {DOC_LANGUAGES[code]}", key=key,
                        on_change=on_change, width=260,
                        help=t("Езикът, на който се генерира файлът (екранът не се сменя)."))

# Табове 2-4: всеки е отделна част (st.fragment) - поле или бутон в таба презарежда само него.
# Таблицата се сменя само в таб 1, а това презарежда цялата страница и всички табове.
@st.fragment
def render_specification_tab(df_calc):
    st.header(t("2. Спецификация на кофражните елементи и панели TEKO"))
    
    if df_calc.empty or len(df_calc) == 0:
        st.info(t("ℹ️ Въведете елементи в Таб 1 и натиснете 'Запази и Изчисли'."))
    else:
        detailed_rows = []
        all_warnings = []
        total_a = 0.0
        project_panels_summary = {}
        project_accessories_summary = {}

        for _, row in df_calc.iterrows():
            cnt = int(_row_float(row, "count", 1))
            h = _row_float(row, "height_cm", 300)
            elem_type = str(row.get("type", "wall"))
            name = str(row.get("name", "Елемент"))

            row_warns = check_element_dimensions(row)
            all_warnings.extend(row_warns)

            elem_label = format_element_label(elem_type, name)
            dim_str, area = element_dims_and_area(elem_type, row)

            total_a += area
            
            h_breakdown_str = format_height_breakdown_text(h, element_layout(elem_type, row))

            panels_dict = get_element_teko_panels(elem_type, row)
            for p_name, p_qty in panels_dict.items():
                project_panels_summary[p_name] = project_panels_summary.get(p_name, 0) + p_qty

            panels_str = ", ".join([f"{t_item(k)} ({v} {t('бр.')})" for k, v in panels_dict.items()])

            acc_dict = get_element_accessories(elem_type, row)
            for acc_name, acc_qty in acc_dict.items():
                project_accessories_summary[acc_name] = project_accessories_summary.get(acc_name, 0) + acc_qty

            detailed_rows.append({
                t("Елемент"): elem_label,
                t("Размери"): t_item(dim_str),
                t("Брой"): cnt,
                t("Площ (m²)"): round(area, 2),
                t("Разпределение по височина"): h_breakdown_str,
                t("Панели TEKO (Вид и брой)"): panels_str
            })

        df_detailed = pd.DataFrame(detailed_rows)
        if not df_detailed.empty:
            df_detailed.index = range(1, len(df_detailed) + 1)

        panels_sum_data = []
        total_panels_weight = 0.0
        for k, v in sorted(project_panels_summary.items()):
            unit_w = get_item_weight(k)
            tot_w = unit_w * v
            total_panels_weight += tot_w
            panels_sum_data.append({
                t("Код на панела / коф. елемент"): t_item(k),
                t("Общ брой (бр.)"): v,
                t("Ед. тегло (kg)"): round(unit_w, 2),
                t("Общо тегло (kg)"): round(tot_w, 2)
            })
        df_panels_sum = pd.DataFrame(panels_sum_data)
        if not df_panels_sum.empty:
            df_panels_sum.index = range(1, len(df_panels_sum) + 1)

        acc_sum_data = []
        total_acc_weight = 0.0
        for k, v in sorted(project_accessories_summary.items()):
            unit_w = get_item_weight(k)
            tot_w = unit_w * v
            total_acc_weight += tot_w
            acc_sum_data.append({
                t("Аксесоар / Окомплектовка"): t_item(k),
                t("Общ брой (бр.)"): v,
                t("Ед. тегло (kg)"): round(unit_w, 2),
                t("Общо тегло (kg)"): round(tot_w, 2)
            })
        df_acc_sum = pd.DataFrame(acc_sum_data)
        if not df_acc_sum.empty:
            df_acc_sum.index = range(1, len(df_acc_sum) + 1)

        total_formwork_weight = total_panels_weight + total_acc_weight

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric(t("📊 ОБЩА КОФРАЖНА ПЛОЩ"), f"{total_a:.2f} m²")
        with col_m2:
            st.metric(t("⚖️ ОБЩО ТЕГЛО НА КОФРАЖА"), f"{total_formwork_weight:.2f} kg ({total_formwork_weight/1000.0:.2f} t)")

        if all_warnings:
            with st.expander(t("⚠️ Предупреждения за нестандартни размери в кофражните елементи"), expanded=True):
                for w_msg in all_warnings:
                    st.markdown(w_msg)
        show_stock_layout_notes(df_calc)
        show_stock_warnings(df_calc)

        st.subheader(t("📋 Спецификация на кофражните елементи и съответните панели"))
        st.dataframe(df_detailed, use_container_width=True)

        st.divider()
        col_p1, col_p2 = st.columns(2)
        
        with col_p1:
            st.subheader(t("📦 Панели TEKO (Общо: {w} kg)", w=f"{total_panels_weight:.2f}"))
            st.dataframe(df_panels_sum, use_container_width=True)

        with col_p2:
            st.subheader(t("Аксесоари и Ъгли (Общо: {w} kg)", w=f"{total_acc_weight:.2f}"))
            st.dataframe(df_acc_sum, use_container_width=True)

        st.divider()
        st.subheader(t("📊 КСС и чертежи в Excel"))
        st.caption(t("Лист „Кол. сметка“ - артикулите в реда на офертата; лист за всеки елемент - изглед отгоре и "
                     "изглед отпред от клетки (1 клетка = 5 см) за редакция; лист с всички панели за копиране."))
        # смяна на езика - готовият файл вече не отговаря, създава се наново
        render_prices_box()
        excel_lang = doc_language_select("doc_lang_excel", on_change=lambda: st.session_state.pop("excel_bytes", None))
        if st.button(t("📊 Създай Excel (КСС и чертежи)"), key="make_excel"):
            with st.spinner(t("Генериране на Excel...")), document_language(excel_lang):
                st.session_state["excel_bytes"] = generate_excel(build_drawing_elements(df_calc),
                                                                 kss_stock(), kss_prices()).getvalue()
        if st.session_state.get("excel_bytes"):
            st.download_button(
                label=t("📥 Изтегли КСС и чертежи (Excel .xlsx)"),
                data=st.session_state["excel_bytes"],
                file_name="Teko_KSS_i_Chertezhi.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

@st.fragment
def render_pdf_tab(df_calc, current):
    st.header(t("3. Генериране на PDF чертежи и спецификации"))
    if df_calc.empty or len(df_calc) == 0:
        st.info(t("ℹ️ Въведете елементи в Таб 1, за да генерирате чертежи."))
    else:
        proj_name_input = st.text_input(t("Наименование на обекта:"), value=current["name"])
        client_name_input = st.text_input(t("Име на клиент / инвеститор:"),
                                          value=current["client"] or "Няма посочен клиент")

        pdf_lang = doc_language_select("doc_lang_pdf")
        if st.button(t("📄 Генерирай PDF Чертежи на обект"), type="primary", key="make_pdf"):
            with st.spinner(t("Генериране на векторни чертежи и PDF документ...")), document_language(pdf_lang):
                pdf_elements = build_drawing_elements(df_calc)

                # общата сметка - сборът от сметките на елементите (същите числа като в таб 2)
                project_full_bom = {}
                for elem in pdf_elements:
                    for code, qty in elem["bom"].items():
                        project_full_bom[code] = project_full_bom.get(code, 0) + qty

                proj_info = {
                    "project": proj_name_input,
                    "client": client_name_input
                }

                pdf_bytes = generate_pdf_drawings(pdf_elements, project_full_bom, proj_info)
                st.success(t("✅ PDF чертежите бяха генерирани успешно!"))
                st.download_button(
                    label=t("📥 Изтегли пълен PDF с чертежи и спецификации"),
                    data=pdf_bytes,
                    file_name="Teko_Drawings_And_Specification.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

@st.fragment
def render_offer_tab(df_calc, current):
    st.header(t("4. Търговска оферта"))
    if df_calc.empty or len(df_calc) == 0:
        st.info(t("ℹ️ Въведете елементи в Таб 1, за да генерирате оферта."))
    else:
        col_o1, col_o2 = st.columns(2)
        with col_o1:
            offer_client = st.text_input(t("Клиент / Инвеститор:"), value=current["client"] or "Строителна Компания ООД")
            offer_project = st.text_input(t("Име на обект:"), value=current["name"])
            offer_date_val = st.date_input(t("Дата на офертата:"), value=current["date"])
        with col_o2:
            # стойностите остават на български - отиват в Word офертата (на български)
            offer_type_sel = st.selectbox(t("Тип на офертата:"),
                                          ["Наем на кофраж (€/m² за месец)", "Покупка на нов кофраж (€/m²)"],
                                          format_func=t, key="offer_type")
            default_price = 18.0 if "наем" in offer_type_sel.lower() else 125.0
            price_m2 = st.number_input(t("Цена на m² (€):"), min_value=0.0, value=default_price, step=0.5)

        offer_lang = doc_language_select("doc_lang_offer")
        if st.button(t("📄 Създай Word оферта"), type="primary", key="make_offer"):
            with document_language(offer_lang):   # таблицата и документът - на езика на офертата
                total_a = sum(element_dims_and_area(str(row.get("type", "wall")), row)[1] for _, row in df_calc.iterrows())
                subtotal_val = total_a * price_m2
                vat_val = subtotal_val * 0.20
                grand_total_val = subtotal_val + vat_val

                offer_table_rows = []
                for _, row in df_calc.iterrows():
                    cnt = int(_row_float(row, "count", 1))
                    elem_type = str(row.get("type", "wall"))
                    name = str(row.get("name", "Елемент"))
                    dim_str, area = element_dims_and_area(elem_type, row)

                    offer_table_rows.append({
                        "Елемент": format_element_label(elem_type, name),
                        "Размери": dim_str,
                        "Брой": cnt,
                        "Площ (m²)": area,
                        "Обща сума (€)": area * price_m2
                    })

                word_stream = generate_word_offer(
                    offer_client, offer_project, offer_date_val, offer_type_sel,
                    price_m2, offer_table_rows, total_a, subtotal_val, vat_val, grand_total_val
                )

                st.success(t("✅ Търговската оферта беше генерирана успешно в Word формат!"))
                st.download_button(
                    label=t("📥 Изтегли оферта (Word .docx)"),
                    data=word_stream,
                    file_name="Teko_Commercial_Offer.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )


@st.fragment
def render_stock_tab(df_calc):
    st.header(t("5. Складова наличност"))
    show_stock_warnings(df_calc)
    if st.session_state.get("stock_error"):
        st.error(t("Архивът в Google не е достъпен ({error}). Наличността се пази само докато страницата е "
                   "отворена.", error=st.session_state["stock_error"]))
    if projects_store.has_archive():
        modified = st.session_state.get("stock_modified")
        # Последната промяна - на отделен ред, видимо над таблицата (потребителят, 20.11.2026)
        col_date, col_reload = st.columns([3, 1], vertical_alignment="center")
        col_date.markdown("🕒 " + (t("Последна промяна на наличността: **{date}**",
                                     date=modified.strftime('%d.%m.%Y %H:%M')) if modified
                                   else t("Наличността още не е записана в архива.")))
        if col_reload.button(t("🔄 Обнови от архива"), key="reload_stock",
                             help=t("Зарежда наличността наново от Google (промените от други компютри) - без F5. "
                                    "Незаписаните промени в таблицата се губят.")):
            reload_stock()
            st.rerun()  # цялата страница - предупрежденията и реденето по склада също
        st.caption(t("Имената, мярката и наличността се редактират в таблицата; ред се добавя с „+“ под таблицата, "
                     "изтрива се с отметка вляво и кошчето. „💾 Запази наличността“ записва в Google (общо за всички "
                     "проекти) и обновява предупрежденията в табовете; предишната наличност остава в лист "
                     "„Наличност - история“. Промяна от друг компютър - с „🔄 Обнови от архива“."))
    else:
        st.caption(t("Имената, мярката и наличността се редактират в таблицата; ред се добавя с „+“ под таблицата, "
                     "изтрива се с отметка вляво и кошчето. „💾 Запази наличността“ обновява предупрежденията в "
                     "табовете. Без архив (няма ключ за Google в secrets) наличността се губи при презареждане."))
    with st.form("stock_form"):
        # Като „1. Оферта – софтуер.xlsx“: Наличност в склада, Нужно за проекта (отвореният проект) и Остават -
        # последните две се смятат и не се редактират; недостигът е в червено.
        # Без разтягане на таблицата: при разтягане Streamlit разпределя ширината и не спазва колоните.
        shown = st.session_state["stock_df"].copy()
        shown["Нужно"] = pd.Series(stock_need(shown, df_calc), index=shown.index, dtype="float")
        shown["Остават"] = pd.to_numeric(shown["Остава"], errors="coerce") - shown["Нужно"].fillna(0)
        red = lambda v: "color: #9C0006; background-color: #FFC7CE" if pd.notna(v) and v < 0 else ""
        # Styler-ът показва числата по своему (260.000000, nan) - затова и форматът: 260, 16963.55, празно
        number = lambda v: "" if pd.isna(v) else f"{v:.10g}"
        styled = shown.style.map(red, subset=["Остават"]).format(number, subset=["Остава", "Нужно", "Остават"])
        edited_stock = st.data_editor(
            styled, num_rows="dynamic", hide_index=True, width="content",
            height=35 * (len(shown) + 2) + 3,
            column_config={"Елемент": st.column_config.TextColumn(t("Елемент"), width=240),
                           "Мярка": st.column_config.TextColumn(t("Мярка"), width=80),
                           "Остава": st.column_config.NumberColumn(t("Наличност в склада"), width=140, min_value=0,
                                                                   format="%g"),
                           "Нужно": st.column_config.NumberColumn(t("Нужно за проекта"), width=140, format="%g"),
                           "Остават": st.column_config.NumberColumn(t("Остават"), width=140, format="%g")},
            column_order=STOCK_COLUMNS + ["Нужно", "Остават"], disabled=["Нужно", "Остават"], key="stock_editor")
        if st.form_submit_button(t("💾 Запази наличността"), type="primary", key="save_stock"):
            store_stock(edited_stock[STOCK_COLUMNS])
            # както в таб 1: таблицата се показва наново от записаните данни, иначе следващата промяна се губи
            st.session_state.pop("stock_editor", None)
            st.rerun()  # цялата страница - предупрежденията в табове 1 и 2 също се обновяват

    st.subheader("Excel")
    stock_lang = doc_language_select("doc_lang_stock")
    with document_language(stock_lang):  # заглавията на файла; имената в склада са данни - както са въведени
        stock_xlsx = stock_to_excel(st.session_state["stock_df"],
                                    stock_need(st.session_state["stock_df"], df_calc)).getvalue()
    st.download_button(t("📤 Изтегли като Excel"), data=stock_xlsx,
                       file_name="Складова_наличност.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       help=t("Записаната наличност (без незаписаните промени в таблицата) и нужното за проекта, "
                              "подредени като „1. Оферта – софтуер.xlsx“."), key="download_stock")
    uploaded = st.file_uploader(t("Excel с наличност („1. Оферта – софтуер.xlsx“ или „1. Наличности.xlsx“ - колони "
                                  "Елемент, Мярка, Наличност в склада):"), type=["xlsx"], key="stock_upload")
    if uploaded is not None and st.button(t("📥 Зареди от Excel"), key="load_stock",
                                          help=t("Заменя цялата таблица с тази от файла и я записва.")):
        try:
            loaded = stock_from_excel(uploaded)
        except Exception as exc:  # noqa: BLE001 - грешен файл
            st.error(t("Файлът не може да се прочете: {error}", error=exc))
        else:
            if loaded.empty:
                st.error(t("Във файла няма редове под „Елемент“."))
            else:
                store_stock(loaded)
                st.session_state.pop("stock_editor", None)
                st.session_state["stock_loaded"] = len(loaded)
                st.rerun()
    if st.session_state.get("stock_loaded"):
        st.success(t("✅ Заредени {n} реда от Excel.", n=st.session_state.pop("stock_loaded")))


# === 3D план на етажа (таб 6, потребителят 22.11.2026) ===
# Елементите на един чертеж се подреждат с мишката в изглед отгоре (приблизително) и се чертаят заедно в 3D -
# отделен PDF. Местата се пазят само докато страницата е отворена (не се записват в архива).
FLOOR_BG_MAX_PX = 2400  # чертежът като фон - най-много толкова пиксела по дългата страна
FLOOR_BG_WIDTH_CM = 3000  # картина без мащаб - приема се толкова широка, докато не се зададе мащаб по кота


def floor_pieces(df_part):
    """
    Елементите на един чертеж за 3D плана - по един за всеки брой. id - от типа, името и размерите
    (остава същото при промяна на други редове в таблицата).
    """
    pieces, seen = [], {}
    for _, row in df_part.iterrows():
        elem_type = str(row.get("type", "wall"))
        layout = element_layout(elem_type, row)
        if layout is None:
            continue
        name = "" if pd.isna(row.get("name")) else str(row.get("name"))
        base = "|".join([elem_type, name] + [str(_row_float(row, col, "")) for col in
                                             ("l1_cm", "l2_cm", "l3_cm", "thickness_cm", "height_cm")])
        seen[base] = seen.get(base, 0) + 1
        plan, boxes = piece_plan(layout), piece_boxes(layout)
        label = format_element_label(elem_type, name)
        cnt = int(_row_float(row, "count", 1))
        for k in range(cnt):
            pieces.append({**plan, "boxes": boxes, "id": f"{base}|{seen[base]}|{k}", "type": elem_type, "name": name,
                           "label": label + (f" ({k + 1})" if cnt > 1 else "")})
    return pieces


def floor_background(file, page):
    """
    Чертежът като фон: сива JPEG картина (data URL и байтовете), размерите в пиксели и точки на PDF на пиксел.
    file: {"name", "type", "data"} (drawing_file) или качен файл.
    """
    import base64
    if not isinstance(file, dict):
        file = {"name": file.name, "type": file.type, "data": file.getvalue()}
    data = file["data"]
    pt_per_px = None
    shapes, labels = [], []
    if file["type"] == "application/pdf":
        with fitz.open(stream=data, filetype="pdf") as doc:
            pg = doc.load_page(page - 1)
            zoom = FLOOR_BG_MAX_PX / max(pg.rect.width, pg.rect.height)
            pix = pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            pt_per_px = 1 / zoom
            try:   # векторен PDF - контурите на бетона и надписите (за местата на елементите)
                shapes, labels = pdf_shapes(pg, pt_per_px)
            except Exception:  # noqa: BLE001 - необичаен PDF: без контури, само Gemini
                shapes, labels = [], []
    else:
        img = Image.open(io.BytesIO(data))
        img.thumbnail((FLOOR_BG_MAX_PX, FLOOR_BG_MAX_PX))
    buf = io.BytesIO()
    img.convert("L").save(buf, format="JPEG", quality=60)
    return {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(), "jpeg": buf.getvalue(),
            "w_px": img.width, "h_px": img.height, "pt_per_px": pt_per_px,
            "cm_per_px": FLOOR_BG_WIDTH_CM / img.width, "shapes": shapes, "labels": labels}


def floor_scale_changed(store, key):
    """Мащаб 1:N на PDF чертежа -> см на пиксел (1 pt = 2,54 / 72 см на хартията)."""
    bg = store["bg"]
    bg["cm_per_px"] = bg["pt_per_px"] * 2.54 / 72 * st.session_state[key]


FLOOR_STANDARD_SCALES = (10, 20, 25, 50, 75, 100, 125, 150, 200, 250, 500, 1000)


def places_pages(places):
    """Страниците с местата от Gemini (за всеки брой - една)."""
    pages = []
    for e in places or []:
        for place in e.get("places") or []:
            try:
                pages.append(int(place.get("page") or 1))
            except (TypeError, ValueError, AttributeError):
                pass
    return pages


def floor_auto_scale(store, scale_key, pieces, places):
    """
    Мащабът по елементите (потребителят, 24.11.2026) - веднъж при зареждане на фона: по контурите от векторния
    PDF, иначе по контурите от Gemini (приблизително). PDF - най-близкият стандартен мащаб (до 8 %).
    """
    bg = store["bg"]
    outlines = gemini_outlines(places, bg["page"], bg["w_px"], bg["h_px"])
    _pos, _how, est = drawing_places(pieces, bg["w_px"], bg["h_px"], bg["cm_per_px"], outlines,
                                     bg["shapes"], bg["labels"])
    if not est:
        return
    if bg["pt_per_px"]:
        n = est / (bg["pt_per_px"] * 2.54 / 72)
        near = min(FLOOR_STANDARD_SCALES, key=lambda sc: abs(sc - n) / sc)
        n = near if abs(near - n) / near <= 0.08 else max(1, round(n))
        st.session_state[scale_key] = n
        floor_scale_changed(store, scale_key)
        bg["auto_scale"] = n
    else:
        bg["cm_per_px"] = est
        bg["auto_scale"] = True


@st.fragment
def render_floor_tab(df_calc, current):
    st.header(t("6. 3D план на етажа"))
    groups = [(name, part) for name, part in drawing_groups(df_calc) if len(part)]
    if not groups:
        st.info(t("ℹ️ Въведете елементи в Таб 1 и натиснете 'Запази и Изчисли'."))
        return
    choice = 0
    if len(groups) > 1:
        choice = st.selectbox(t("Чертеж (етаж):"), range(len(groups)), key="floor_drawing",
                              format_func=lambda i: (t("Чертеж {i}: {name}", i=i + 1, name=groups[i][0])
                                                     if groups[i][0] else t("Без чертеж (въведени ръчно)")))
    drawing, part = groups[choice]
    fkey = hashlib.md5(f"{current['id']}|{drawing}".encode()).hexdigest()[:10]
    store = st.session_state.setdefault("floor_plans", {}).setdefault(fkey, {"positions": {}, "bg": None, "reset": 0})
    pieces = floor_pieces(part)

    places = None   # местата от Gemini - само за разчетения чертеж
    with st.expander(t("🖼️ Чертежът като фон"), expanded=True):
        auto_on = st.checkbox(t("📍 Постави елементите по чертежа"), value=True, key=f"floor_auto_{fkey}",
                              help=t("Местата от разчитането с Gemini (приблизително) и от контурите на бетона във "
                                     "векторен PDF (точно). Елементите, преместени с мишката, остават, където са."))
        # фонът - сам от разчетения в таб 1 чертеж; друг файл - само ако няма или трябва друг
        own = drawing_file(drawing)
        other = st.file_uploader(t("Друг файл за фон (PDF или картина) - само ако не е разчетеният в таб 1:")
                                 if own else t("Чертеж (PDF или картина):"),
                                 type=["pdf", "png", "jpg", "jpeg"], key=f"floor_bg_file_{fkey}")
        file = None
        if store.get("bg_off"):   # скрит с „Скрий фона“
            if st.button(t("🖼️ Покажи фона"), key=f"floor_bg_on_{fkey}"):
                store["bg_off"] = False
                st.rerun(scope="fragment")
        elif other is not None:
            file = {"name": other.name, "type": other.type, "data": other.getvalue()}
        elif own:
            file = own
            places = st.session_state.get("drawing_places", {}).get(drawing_file_key(drawing))
            st.caption(t("Фонът е чертежът от таб 1: „{name}“.", name=own["name"]))
        elif drawing:
            st.caption(t("Файлът на „{name}“ не е зареден (пази се само докато страницата е отворена) - качете го "
                         "тук или в таб 1.", name=drawing))
        if file is not None:
            page = 1
            if file["type"] == "application/pdf":
                with fitz.open(stream=file["data"], filetype="pdf") as doc:
                    n_pages = doc.page_count
                if n_pages > 1:
                    pages = [pg for pg in places_pages(places) if pg <= n_pages]   # страницата с плана
                    page = st.number_input(t("Страница:"), min_value=1, max_value=n_pages,
                                           value=max(set(pages), key=pages.count) if pages else 1, step=1,
                                           key=f"floor_bg_page_{fkey}")
            src = (file["name"], len(file["data"]), page, len(places_pages(places)))
            if store["bg"] is None or store["bg"].get("src") != src:
                store["bg"] = floor_background(file, page)
                store["bg"]["src"], store["bg"]["page"] = src, page
                scale_key = f"floor_bg_scale_{fkey}"
                if store["bg"]["pt_per_px"]:  # PDF - по мащаба 1:N (по подразбиране 1:50)
                    st.session_state.setdefault(scale_key, 50)
                    floor_scale_changed(store, scale_key)
                if auto_on:   # мащабът - по елементите на чертежа
                    floor_auto_scale(store, scale_key, pieces, places)
        if file is None:
            store["bg"] = None
        bg = store["bg"]
        if bg:
            col_scale, col_known, col_op = st.columns(3)
            if bg["pt_per_px"]:
                scale_key = f"floor_bg_scale_{fkey}"
                col_scale.number_input(t("Мащаб на чертежа 1:"), min_value=1, step=1, key=scale_key,
                                       on_change=floor_scale_changed, args=(store, scale_key),
                                       help=t("Мащабът, в който е начертан листът (напр. 1:50). Сканиран лист "
                                              "може да е с друг размер - тогава задайте мащаба по кота."))
            col_known.number_input(t("Известна кота (см):"), min_value=1.0, value=1000.0, step=5.0,
                                   key=f"floor_known_{fkey}",
                                   help=t("За „📏 Мащаб по кота“: кликнете двата края на тази кота върху чертежа."))
            bg["opacity"] = col_op.slider(t("Видимост на фона"), 0.1, 1.0, 0.45, 0.05, key=f"floor_bg_op_{fkey}")
            if st.button(t("🙈 Скрий фона"), key=f"floor_bg_del_{fkey}"):
                store["bg"], store["bg_off"] = None, True
                st.rerun(scope="fragment")
            st.checkbox(t("Фонът в PDF-а (бледо, под елементите)"), value=True, key=f"floor_bg_pdf_{fkey}")
            if bg.get("auto_scale"):
                st.caption(t("📏 Мащабът е определен по елементите на чертежа: 1:{n}.", n=bg["auto_scale"])
                           if bg["pt_per_px"] else t("📏 Мащабът е определен по елементите на чертежа."))
            st.caption(t("Ако елементите не съвпадат по размер с чертежа, натиснете „📏 Мащаб по кота“ в лентата над "
                         "плана и кликнете двата края на известна кота."))

    bg = store["bg"]
    bg_data = None
    if bg:
        bg_data = {"url": bg["url"], "w": bg["w_px"] * bg["cm_per_px"], "h": bg["h_px"] * bg["cm_per_px"],
                   "opacity": bg.get("opacity", 0.45)}
    ids = {p["id"] for p in pieces}
    # местата от чертежа (потребителят, 24.11.2026) - наново при друг фон, мащаб или елементи; преместените с
    # мишката остават
    auto_key = (bg["src"] if bg else None, bg["cm_per_px"] if bg else None, auto_on, tuple(sorted(ids)))
    if store.get("auto_key") != auto_key:
        auto, how = {}, {}
        if bg and auto_on:
            auto, how, _scale = drawing_places(
                pieces, bg["w_px"], bg["h_px"], bg["cm_per_px"],
                gemini_outlines(places, bg["page"], bg["w_px"], bg["h_px"]), bg["shapes"], bg["labels"])
        moved_ids = store.setdefault("moved", set())
        store["positions"] = {pid: pos for pid, pos in store["positions"].items() if pid in moved_ids}
        store["positions"].update({pid: pos for pid, pos in auto.items() if pid not in moved_ids})
        store["how"] = {pid: h for pid, h in how.items() if pid not in moved_ids}
        store["auto_key"] = auto_key
        store["auto_n"] = store.get("auto_n", 0) + 1   # компонентът взима новите места
        store.pop("pdf", None)
    known = {pid: pos for pid, pos in store["positions"].items() if pid in ids}
    # новите елементи - на редове под чертежа (фонът е от y = 0 нагоре), оттам се влачат до мястото си
    store["positions"] = default_positions(pieces, known,
                                           row_width_cm=bg_data["w"] if bg_data else ROW_WIDTH_CM)

    st.caption(t("Влачете елементите с мишката до мястото им (приблизително е достатъчно). Клик върху елемент го "
                 "избира: кръгчето над него го върти под всякакъв ъгъл (през 5°, със Shift - през 1°), „Ъгъл“ - "
                 "точен ъгъл, „↺ 90°“ / „↻ 90°“ (или клавиш R) - на 90°, „⇋ Огледално“ (или M) го обръща. Колелцето "
                 "приближава, влачене на празно място мести изгледа. Местата се пазят, докато страницата е отворена "
                 "(не се записват в архива)."))
    if bg and auto_on:
        how = list(store.get("how", {}).values())
        if how:
            st.caption(t("📍 По чертежа: {n} от {total} елемента ({pdf} по контура в PDF-а, {gemini} по Gemini - "
                         "приблизително). Другите са под чертежа - влачете ги до мястото им.", n=len(how),
                         total=len(pieces), pdf=how.count("pdf"), gemini=how.count("gemini")))
        else:
            st.caption(t("📍 Местата на елементите не са намерени в чертежа (няма места от разчитането и контури в "
                         "PDF-а до имената им) - влачете ги с мишката."))
    # нов ключ при ново поставяне по чертежа - иначе компонентът връща старите места и ги записва като преместени
    ckey = f"floor_{fkey}_{store['reset']}_{store.get('auto_n', 0)}"
    data = {
        "pieces": [{k: p[k] for k in ("id", "label", "poly", "forms", "cx", "cy", "w", "h")} for p in pieces],
        "positions": store["positions"],
        "bg": bg_data,
        "token": f"{ckey}|{bg_data['w'] if bg_data else 0}",
        "texts": {"rotl": t("↺ 90°"), "rotr": t("↻ 90°"), "angle": t("Ъгъл:"), "mir": t("⇋ Огледално"),
                  "fit": t("⤢ Целият план"),
                  "calib": t("📏 Мащаб по кота"),
                  "calib1": t("Кликнете в единия край на известната кота."),
                  "calib2": t("Кликнете в другия край на котата."),
                  "hint": t("Влачете елементите; клик върху елемент го избира."),
                  "selected": t("Избран: {name} - кръгчето го върти.", name="{name}")},
    }
    result = floor_component()(data=data, key=ckey, on_positions_change=lambda: None,
                               on_calib_change=lambda: None)
    moved = getattr(result, "positions", None)
    if moved:
        moved = {pid: pos for pid, pos in moved.items() if pid in ids}
        changed = {pid for pid, pos in moved.items() if store["positions"].get(pid) != pos}
        if changed:
            store.setdefault("moved", set()).update(changed)   # остават при ново поставяне по чертежа
            store["positions"].update(moved)
            store.pop("pdf", None)  # готовият PDF е със старите места
    measured = getattr(result, "calib", None)
    if measured and bg:
        bg["cm_per_px"] *= st.session_state.get(f"floor_known_{fkey}", 1000.0) / measured
        st.rerun(scope="fragment")

    col_reset, col_lang, col_pdf = st.columns([1, 1, 1], vertical_alignment="bottom")
    if col_reset.button(t("↺ Подреди наново"), key=f"floor_reset_{fkey}",
                        help=t("Връща елементите на местата им по чертежа, другите - един до друг под него "
                               "(преместеното с мишката се губи).")):
        store["positions"], store["moved"] = {}, set()
        store.pop("auto_key", None)
        store["reset"] += 1
        store.pop("pdf", None)
        st.rerun(scope="fragment")
    with col_lang:
        floor_lang = doc_language_select("doc_lang_floor")
    if col_pdf.button(t("📄 Генерирай 3D PDF"), type="primary", key="make_floor_pdf", use_container_width=True):
        with st.spinner(t("Чертане на 3D плана...")), document_language(floor_lang):
            doc_pieces = floor_pieces(part)  # имената - на езика на документа
            info = {"project": current["name"], "client": current["client"] or dt("Няма посочен клиент"),
                    "drawing": drawing,
                    "date": current["date"].strftime("%d.%m.%Y") if hasattr(current["date"], "strftime") else ""}
            background = None
            if bg and st.session_state.get(f"floor_bg_pdf_{fkey}", True):
                background = {"image": Image.open(io.BytesIO(bg["jpeg"])), "cm_per_px": bg["cm_per_px"]}
            store["pdf"] = generate_floor_pdf(doc_pieces, store["positions"], info, background)
    if store.get("pdf"):
        st.download_button(t("📥 Изтегли 3D плана (PDF)"), data=store["pdf"],
                           file_name="Teko_3D_Floor_Plan.pdf", mime="application/pdf", use_container_width=True)


df_calc = fill_default_height(st.session_state["edited_df"],
                              st.session_state.get("std_height_cm", DEFAULT_HEIGHT_CM))
update_stock_plan(df_calc)
with tab2:
    render_specification_tab(df_calc)
with tab3:
    render_pdf_tab(df_calc, current)
with tab4:
    render_offer_tab(df_calc, current)
with tab5:
    render_stock_tab(df_calc)
with tab6:
    render_floor_tab(df_calc, current)
