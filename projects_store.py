"""
Проекти: списък, нов, запис, дублиране, изтриване.

Проектите са в речник `store` (в app.py това е st.session_state["projects"]). С архив (Google Sheets,
use_archive) всяка промяна се записва и в таблицата „TEKO Проекти“, а refresh() зарежда общия списък.
Без архив (напр. в тестовете или без ключ в secrets) проектите се губят при презареждане.
Проект: id, name, client, date, created, modified, elements (таблицата с елементите), std_height_cm,
stock_layout (отметката „Редене според складовата наличност“), corrections (корекциите на бройките в таб 3:
{код: [коригиран брой, изчислен брой при корекцията]}; 26.11.2026).

Складовата наличност (таб 6) е обща за всички проекти: load_stock() / save_stock(), в архива - лист „Наличност“;
при всеки запис предишната наличност се добавя в лист „Наличност - история“ (резервно копие).
Единичните цени (за „Кол. сметка“ в Excel) са общи: load_prices() / save_prices(), в архива - лист „Цени“.
"""
import json
import math
import uuid
from datetime import date, datetime

import pandas as pd

COPY_SUFFIX = " (копие)"

# Колоните на таблицата с елементите, които се пазят в архива (като TABLE_COLUMNS в app.py).
# Дебелините на рамената и чертежът са накрая, за да се четат правилно и редовете, записани преди тях.
# drawing - от кой чертеж е елементът (името на файла, разчетен с Gemini; 18.11.2026); празно - без чертеж
ELEMENT_COLUMNS = ["type", "name", "count", "thickness_cm", "l1_cm", "l2_cm", "l3_cm", "height_cm",
                   "closed_end_1", "closed_end_2", "closed_end_3",
                   "thickness1_cm", "thickness2_cm", "thickness3_cm", "drawing"]

_archive = None


def use_archive(archive):
    """Задава архива (GoogleSheetsArchive) за всички следващи промени; None - без архив."""
    global _archive
    _archive = archive


def has_archive():
    return _archive is not None


def refresh(store):
    """Зарежда общия списък от архива (без изтритите); без архив - нищо не прави."""
    if _archive is None:
        return
    fresh = _archive.load()
    store.clear()
    store.update(fresh)


def _now(now):
    return now or datetime.now()


def new_project(store, name, client="", project_date=None, std_height_cm=270, elements=None, now=None,
                stock_layout=False, corrections=None):
    """Създава празен проект и връща неговото id."""
    stamp = _now(now)
    pid = uuid.uuid4().hex
    store[pid] = {
        "id": pid,
        "name": name.strip() or "Нов проект",
        "client": client.strip(),
        "date": project_date or stamp.date(),
        "created": stamp,
        "modified": stamp,
        "elements": None if elements is None else elements.copy(),
        "std_height_cm": std_height_cm,
        "stock_layout": bool(stock_layout),
        "corrections": dict(corrections or {}),
    }
    if _archive is not None:
        _archive.write_project(store[pid], with_elements=True)
    return pid


def list_projects(store):
    """Проектите, последно променените най-отгоре."""
    return sorted(store.values(), key=lambda p: p["modified"], reverse=True)


def get_project(store, pid):
    return store.get(pid)


def save_project(store, pid, elements=None, std_height_cm=None, now=None, stock_layout=None, corrections=None):
    """
    Записва таблицата, височината, редене по склада и корекциите на бройките (таб 3) в проекта;
    „Последна промяна“ се мени само ако има промяна.
    """
    project = store[pid]
    changed = elements_changed = False
    if elements is not None:
        old = project["elements"]
        if old is None or element_rows(elements) != element_rows(old):
            project["elements"] = elements.copy()
            changed = elements_changed = True
    if std_height_cm is not None and std_height_cm != project["std_height_cm"]:
        project["std_height_cm"] = std_height_cm
        changed = True
    if stock_layout is not None and bool(stock_layout) != project.get("stock_layout", False):
        project["stock_layout"] = bool(stock_layout)
        changed = True
    if corrections is not None and dict(corrections) != project.get("corrections", {}):
        project["corrections"] = dict(corrections)
        changed = True
    if changed:
        project["modified"] = _now(now)
        if _archive is not None:
            _archive.write_project(project, with_elements=elements_changed)
    return changed


def rename_project(store, pid, name, client, project_date, now=None):
    """Сменя името, клиента и датата на проекта; „Последна промяна“ се мени само ако има промяна."""
    project = store[pid]
    name = name.strip() or project["name"]
    client = client.strip()
    project_date = project_date or project["date"]
    if (name, client, project_date) == (project["name"], project["client"], project["date"]):
        return False
    project.update(name=name, client=client, date=project_date, modified=_now(now))
    if _archive is not None:
        _archive.write_project(project, with_elements=False)
    return True


def duplicate_project(store, pid, now=None):
    """Копие на проекта с „(копие)“ в името; таблицата е отделна, не обща с оригинала."""
    src = store[pid]
    return new_project(store, src["name"] + COPY_SUFFIX, src["client"], src["date"],
                       src["std_height_cm"], src["elements"], now=now,
                       stock_layout=src.get("stock_layout", False), corrections=src.get("corrections"))


def delete_project(store, pid):
    """Изтриване с кошче: в архива проектът се отбелязва „Изтрит“ и остава в таблицата."""
    project = store.pop(pid, None)
    if project is not None and _archive is not None:
        _archive.mark_deleted(pid)


def load_stock():
    """Складовата наличност от архива: (таблица Елемент / Мярка / Остава, последна промяна); без архив
    или празен лист - (None, None)."""
    if _archive is None:
        return None, None
    return _archive.load_stock()


def save_stock(stock_df, now=None):
    """Записва складовата наличност в архива (целия лист наново); връща времето на записа."""
    stamp = _now(now)
    if _archive is not None:
        _archive.write_stock(stock_rows(stock_df), stamp)
    return stamp


def load_prices():
    """Единичните цени от архива: (таблица Елемент / Ед. цена, последна промяна); без архив или празен лист -
    (None, None)."""
    if _archive is None:
        return None, None
    return _archive.load_prices()


def save_prices(prices_df, now=None):
    """Записва единичните цени в архива (целия лист наново); връща времето на записа."""
    stamp = _now(now)
    if _archive is not None:
        rows = [[_cell(rec.get(col)) for col in PRICE_COLUMNS] for rec in prices_df.to_dict("records")]
        _archive.write_prices([r for r in rows if str(r[0]).strip()], stamp)
    return stamp


def project_rows(store):
    """Редове за таблицата на страницата „Проекти“ (като в другата програма)."""
    return [{"id": p["id"], "Име": p["name"], "Клиент": p["client"],
             "Дата": pd.Timestamp(p["date"]).strftime("%Y-%m-%d"),
             "Последна промяна": p["modified"].strftime("%d.%m.%Y г.")}
            for p in list_projects(store)]


# ==========================================
# Стойности за архива
# ==========================================
def _cell(value):
    """Стойност от таблицата с елементите -> клетка: празно, число, отметка (bool) или текст."""
    if value is None or (isinstance(value, float) and math.isnan(value)) or value is pd.NA:
        return ""
    if isinstance(value, (bool,)) or type(value).__name__ == "bool_":
        return bool(value)
    if isinstance(value, (int, float)) or hasattr(value, "item"):
        number = float(value)
        if math.isnan(number):
            return ""
        return int(number) if number == int(number) else number
    return str(value)


def element_rows(elements):
    """Таблицата с елементите -> редове от клетки (само ELEMENT_COLUMNS); служи и за сравнение."""
    if elements is None:
        return []
    return [[_cell(rec.get(col)) for col in ELEMENT_COLUMNS] for rec in elements.to_dict("records")]


def stock_rows(stock_df):
    """Таблицата с наличността -> редове [Елемент, Мярка, Остава]; празните редове (без име) се пропускат."""
    rows = []
    for rec in stock_df.to_dict("records"):
        row = [_cell(rec.get(col)) for col in STOCK_COLUMNS]
        if str(row[0]).strip():
            rows.append(row)
    return rows


def _elements_from_rows(rows):
    """Редове от архива -> таблица с елементите; празните клетки са празни (None)."""
    if not rows:
        return None
    records = [{col: (None if value == "" else value) for col, value in zip(ELEMENT_COLUMNS, row)}
               for row in rows]
    return pd.DataFrame(records, columns=ELEMENT_COLUMNS)


def _parse_corrections(value):
    """Колоната „Корекции“ (JSON): {код: [брой, изчислен]}; празна или повредена - без корекции."""
    try:
        data = json.loads(value) if str(value).strip() else {}
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    result = {}
    for code, pair in data.items():
        try:
            qty, calc = pair
            result[str(code)] = [int(qty), int(calc)]
        except (TypeError, ValueError):
            continue
    return result


def _parse_date(value):
    if isinstance(value, (int, float)):   # дата като число на Google (дни от 30.12.1899)
        return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=value)).date()
    return date.fromisoformat(str(value)[:10])


def _parse_datetime(value):
    if isinstance(value, (int, float)):
        return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=value)).to_pydatetime()
    return datetime.fromisoformat(str(value))


# ==========================================
# Архив в Google Sheets
# ==========================================
PROJECTS_SHEET = "Проекти"
ELEMENTS_SHEET = "Елементи"
PROJECT_HEADER = ["id", "Име", "Клиент", "Дата", "Създаден", "Последна промяна",
                  "Стандартна височина", "Изтрит", "Редене по склада", "Корекции"]
ELEMENT_HEADER = ["project_id", "Ред №"] + ELEMENT_COLUMNS
DELETED_MARK = "да"
STOCK_LAYOUT_MARK = "да"   # „Редене по склада“ - отметката е включена
STOCK_SHEET = "Наличност"
STOCK_COLUMNS = ["Елемент", "Мярка", "Остава"]
# „Последна промяна“ е само на първия ред с данни
STOCK_HEADER = ["Ред №"] + STOCK_COLUMNS + ["Последна промяна"]
# Резервно копие (потребителят, 20.11.2026): предишната наличност при всеки запис, с времето на замяната
STOCK_HISTORY_SHEET = "Наличност - история"
STOCK_HISTORY_HEADER = ["Заменена на"] + STOCK_HEADER
# Единичните цени (потребителят, 20.11.2026) - от „💶 Цени от Excel“ в таб 3, не в кода
PRICES_SHEET = "Цени"
PRICE_COLUMNS = ["Елемент", "Ед. цена"]
PRICES_HEADER = ["Ред №"] + PRICE_COLUMNS + ["Последна промяна"]


class GoogleSheetsArchive:
    """
    Таблица „TEKO Проекти“ с пет листа: „Проекти“ (един ред = проект), „Елементи“
    (един ред = елемент, с project_id), „Наличност“ (складовата наличност, обща за всички проекти),
    „Наличност - история“ (предишните наличности - резервно копие при всеки запис) и „Цени“ (единичните цени
    за „Кол. сметка“ в Excel).
    Листовете и заглавията се създават при първото пускане.
    spreadsheet е gspread.Spreadsheet (или същият интерфейс в тестовете).
    """

    def __init__(self, spreadsheet):
        self.projects = self._sheet(spreadsheet, PROJECTS_SHEET, PROJECT_HEADER)
        self.elements = self._sheet(spreadsheet, ELEMENTS_SHEET, ELEMENT_HEADER)
        self.stock = self._sheet(spreadsheet, STOCK_SHEET, STOCK_HEADER)
        self.stock_history = self._sheet(spreadsheet, STOCK_HISTORY_SHEET, STOCK_HISTORY_HEADER)
        self.prices = self._sheet(spreadsheet, PRICES_SHEET, PRICES_HEADER)

    @staticmethod
    def _sheet(spreadsheet, title, header):
        titles = [ws.title for ws in spreadsheet.worksheets()]
        if title in titles:
            ws = spreadsheet.worksheet(title)
        else:
            ws = spreadsheet.add_worksheet(title=title, rows=100, cols=len(header))
        # нова колона в заглавието (напр. „Редене по склада“ в стария лист „Проекти“) - листът се разширява
        if getattr(ws, "col_count", len(header)) < len(header):
            ws.add_cols(len(header) - ws.col_count)
        if ws.row_values(1)[:len(header)] != header:
            ws.update(values=[header], range_name="A1", value_input_option="RAW")
        return ws

    @staticmethod
    def _values(ws):
        return ws.get_all_values(value_render_option="UNFORMATTED_VALUE")[1:]

    def load(self):
        """Всички проекти без изтритите: {id: проект}."""
        by_project = {}
        for row in self._values(self.elements):
            row = list(row) + [""] * (len(ELEMENT_HEADER) - len(row))
            by_project.setdefault(row[0], []).append(row)
        store = {}
        for row in self._values(self.projects):
            row = list(row) + [""] * (len(PROJECT_HEADER) - len(row))
            pid, name, client, day, created, modified, height, deleted, by_stock, corrections = \
                row[:len(PROJECT_HEADER)]
            if not pid or str(deleted).strip().lower() == DELETED_MARK:
                continue
            rows = sorted(by_project.get(pid, []), key=lambda r: r[1])
            store[pid] = {
                "id": pid, "name": str(name), "client": str(client),
                "date": _parse_date(day), "created": _parse_datetime(created),
                "modified": _parse_datetime(modified),
                "elements": _elements_from_rows([r[2:] for r in rows]),
                "std_height_cm": int(height) if height != "" else 270,
                "stock_layout": str(by_stock).strip().lower() == STOCK_LAYOUT_MARK,
                "corrections": _parse_corrections(corrections),
            }
        return store

    def _project_row_number(self, pid):
        ids = self.projects.col_values(1)
        return ids.index(pid) + 1 if pid in ids else None

    def write_project(self, project, with_elements=True):
        """Записва реда на проекта (нов или съществуващ) и при нужда - елементите му наново."""
        values = [project["id"], project["name"], project["client"],
                  pd.Timestamp(project["date"]).strftime("%Y-%m-%d"),
                  project["created"].isoformat(timespec="seconds"),
                  project["modified"].isoformat(timespec="seconds"),
                  project["std_height_cm"], "", STOCK_LAYOUT_MARK if project.get("stock_layout") else "",
                  json.dumps(project["corrections"], ensure_ascii=False) if project.get("corrections") else ""]
        number = self._project_row_number(project["id"])
        if number is None:
            self.projects.append_rows([values], value_input_option="RAW")
        else:
            self.projects.update(values=[values], range_name=f"A{number}", value_input_option="RAW")
        if with_elements:
            self._write_elements(project["id"], element_rows(project["elements"]))

    def _write_elements(self, pid, rows):
        """Старите редове на проекта се трият (те са един до друг), новите се добавят в края."""
        ids = self.elements.col_values(1)
        numbers = [i + 1 for i, value in enumerate(ids) if i > 0 and value == pid]
        # отзад напред, за да не се местят номерата на още неизтритите
        blocks = []
        for n in numbers:
            if blocks and n == blocks[-1][1] + 1:
                blocks[-1][1] = n
            else:
                blocks.append([n, n])
        for start, end in reversed(blocks):
            self.elements.delete_rows(start, end)
        if rows:
            self.elements.append_rows([[pid, i + 1] + row for i, row in enumerate(rows)],
                                      value_input_option="RAW")

    def mark_deleted(self, pid):
        number = self._project_row_number(pid)
        if number is not None:
            column = chr(ord("A") + PROJECT_HEADER.index("Изтрит"))
            self.projects.update(values=[[DELETED_MARK]], range_name=f"{column}{number}",
                                 value_input_option="RAW")


    def load_stock(self):
        rows = [list(r) + [""] * (len(STOCK_HEADER) - len(r)) for r in self._values(self.stock)]
        rows = sorted((r for r in rows if str(r[1]).strip()), key=lambda r: r[0])
        if not rows:
            return None, None
        stock_df = pd.DataFrame([{col: (None if value == "" else value) for col, value in zip(STOCK_COLUMNS, r[1:4])}
                                 for r in rows], columns=STOCK_COLUMNS)
        stock_df["Остава"] = pd.to_numeric(stock_df["Остава"], errors="coerce")
        stock_df[["Елемент", "Мярка"]] = stock_df[["Елемент", "Мярка"]].astype(object)
        modified = _parse_datetime(rows[0][4]) if rows[0][4] != "" else None
        return stock_df, modified

    def write_stock(self, rows, modified):
        """Старите редове отиват в „Наличност - история“ и се трият, новите се добавят (с „Последна промяна“
        на първия)."""
        old = [list(r) + [""] * (len(STOCK_HEADER) - len(r)) for r in self._values(self.stock)]
        old = [r[:len(STOCK_HEADER)] for r in old if str(r[1]).strip()]
        if old:
            stamp = modified.isoformat(timespec="seconds")
            self.stock_history.append_rows([[stamp] + r for r in old], value_input_option="RAW")
        count = len(self.stock.col_values(1))
        if count > 1:
            self.stock.delete_rows(2, count)
        values = [[i + 1] + row + [modified.isoformat(timespec="seconds") if i == 0 else ""]
                  for i, row in enumerate(rows)]
        if values:
            self.stock.append_rows(values, value_input_option="RAW")

    def load_prices(self):
        rows = [list(r) + [""] * (len(PRICES_HEADER) - len(r)) for r in self._values(self.prices)]
        rows = sorted((r for r in rows if str(r[1]).strip()), key=lambda r: r[0])
        if not rows:
            return None, None
        prices_df = pd.DataFrame([{"Елемент": str(r[1]), "Ед. цена": r[2]} for r in rows], columns=PRICE_COLUMNS)
        prices_df["Ед. цена"] = pd.to_numeric(prices_df["Ед. цена"], errors="coerce")
        modified = _parse_datetime(rows[0][3]) if rows[0][3] != "" else None
        return prices_df, modified

    def write_prices(self, rows, modified):
        """Старите редове се трият, новите се добавят (с „Последна промяна“ на първия)."""
        count = len(self.prices.col_values(1))
        if count > 1:
            self.prices.delete_rows(2, count)
        values = [[i + 1] + row + [modified.isoformat(timespec="seconds") if i == 0 else ""]
                  for i, row in enumerate(rows)]
        if values:
            self.prices.append_rows(values, value_input_option="RAW")


def connect_google_sheets(service_account_info, sheet_id):
    """Архив от secrets: ключът на service account (речник) и ID-то на таблицата."""
    import gspread
    client = gspread.service_account_from_dict(dict(service_account_info))
    return GoogleSheetsArchive(client.open_by_key(sheet_id))
