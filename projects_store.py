"""
Проекти: списък, нов, запис, дублиране, изтриване.

Проектите са в речник `store` (в app.py това е st.session_state["projects"]). С архив (Google Sheets,
use_archive) всяка промяна се записва и в таблицата „TEKO Проекти“, а refresh() зарежда общия списък.
Без архив (напр. в тестовете или без ключ в secrets) проектите се губят при презареждане.
Проект: id, name, client, date, created, modified, elements (таблицата с елементите), std_height_cm.
"""
import math
import uuid
from datetime import date, datetime

import pandas as pd

COPY_SUFFIX = " (копие)"

# Колоните на таблицата с елементите, които се пазят в архива (като TABLE_COLUMNS в app.py)
ELEMENT_COLUMNS = ["type", "name", "count", "thickness_cm", "l1_cm", "l2_cm", "l3_cm", "height_cm",
                   "closed_end_1", "closed_end_2", "closed_end_3"]

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


def new_project(store, name, client="", project_date=None, std_height_cm=270, elements=None, now=None):
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
    }
    if _archive is not None:
        _archive.write_project(store[pid], with_elements=True)
    return pid


def list_projects(store):
    """Проектите, последно променените най-отгоре."""
    return sorted(store.values(), key=lambda p: p["modified"], reverse=True)


def get_project(store, pid):
    return store.get(pid)


def save_project(store, pid, elements=None, std_height_cm=None, now=None):
    """Записва таблицата и височината в проекта; „Последна промяна“ се мени само ако има промяна."""
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
    if changed:
        project["modified"] = _now(now)
        if _archive is not None:
            _archive.write_project(project, with_elements=elements_changed)
    return changed


def duplicate_project(store, pid, now=None):
    """Копие на проекта с „(копие)“ в името; таблицата е отделна, не обща с оригинала."""
    src = store[pid]
    return new_project(store, src["name"] + COPY_SUFFIX, src["client"], src["date"],
                       src["std_height_cm"], src["elements"], now=now)


def delete_project(store, pid):
    """Изтриване с кошче: в архива проектът се отбелязва „Изтрит“ и остава в таблицата."""
    project = store.pop(pid, None)
    if project is not None and _archive is not None:
        _archive.mark_deleted(pid)


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


def _elements_from_rows(rows):
    """Редове от архива -> таблица с елементите; празните клетки са празни (None)."""
    if not rows:
        return None
    records = [{col: (None if value == "" else value) for col, value in zip(ELEMENT_COLUMNS, row)}
               for row in rows]
    return pd.DataFrame(records, columns=ELEMENT_COLUMNS)


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
                  "Стандартна височина", "Изтрит"]
ELEMENT_HEADER = ["project_id", "Ред №"] + ELEMENT_COLUMNS
DELETED_MARK = "да"


class GoogleSheetsArchive:
    """
    Таблица „TEKO Проекти“ с два листа: „Проекти“ (един ред = проект) и „Елементи“
    (един ред = елемент, с project_id). Листовете и заглавията се създават при първото пускане.
    spreadsheet е gspread.Spreadsheet (или същият интерфейс в тестовете).
    """

    def __init__(self, spreadsheet):
        self.projects = self._sheet(spreadsheet, PROJECTS_SHEET, PROJECT_HEADER)
        self.elements = self._sheet(spreadsheet, ELEMENTS_SHEET, ELEMENT_HEADER)

    @staticmethod
    def _sheet(spreadsheet, title, header):
        titles = [ws.title for ws in spreadsheet.worksheets()]
        if title in titles:
            ws = spreadsheet.worksheet(title)
        else:
            ws = spreadsheet.add_worksheet(title=title, rows=100, cols=len(header))
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
            pid, name, client, day, created, modified, height, deleted = row[:len(PROJECT_HEADER)]
            if not pid or str(deleted).strip().lower() == DELETED_MARK:
                continue
            rows = sorted(by_project.get(pid, []), key=lambda r: r[1])
            store[pid] = {
                "id": pid, "name": str(name), "client": str(client),
                "date": _parse_date(day), "created": _parse_datetime(created),
                "modified": _parse_datetime(modified),
                "elements": _elements_from_rows([r[2:] for r in rows]),
                "std_height_cm": int(height) if height != "" else 270,
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
                  project["std_height_cm"], ""]
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


def connect_google_sheets(service_account_info, sheet_id):
    """Архив от secrets: ключът на service account (речник) и ID-то на таблицата."""
    import gspread
    client = gspread.service_account_from_dict(dict(service_account_info))
    return GoogleSheetsArchive(client.open_by_key(sheet_id))
