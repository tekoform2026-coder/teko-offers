"""
Проекти: списък, нов, запис, дублиране, изтриване.

Засега без архив - проектите са в речник `store` (в app.py това е st.session_state["projects"])
и се губят при презареждане на страницата. Архивът (Google или Supabase) ще смени само този модул.
Проект: id, name, client, date, created, modified, elements (таблицата с елементите), std_height_cm.
"""
import uuid
from datetime import datetime

import pandas as pd

COPY_SUFFIX = " (копие)"


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
    return pid


def list_projects(store):
    """Проектите, последно променените най-отгоре."""
    return sorted(store.values(), key=lambda p: p["modified"], reverse=True)


def get_project(store, pid):
    return store.get(pid)


def save_project(store, pid, elements=None, std_height_cm=None, now=None):
    """Записва таблицата и височината в проекта; „Последна промяна“ се мени само ако има промяна."""
    project = store[pid]
    changed = False
    if elements is not None:
        old = project["elements"]
        if old is None or not elements.equals(old):
            project["elements"] = elements.copy()
            changed = True
    if std_height_cm is not None and std_height_cm != project["std_height_cm"]:
        project["std_height_cm"] = std_height_cm
        changed = True
    if changed:
        project["modified"] = _now(now)
    return changed


def duplicate_project(store, pid, now=None):
    """Копие на проекта с „(копие)“ в името; таблицата е отделна, не обща с оригинала."""
    src = store[pid]
    return new_project(store, src["name"] + COPY_SUFFIX, src["client"], src["date"],
                       src["std_height_cm"], src["elements"], now=now)


def delete_project(store, pid):
    store.pop(pid, None)


def project_rows(store):
    """Редове за таблицата на страницата „Проекти“ (като в другата програма)."""
    return [{"id": p["id"], "Име": p["name"], "Клиент": p["client"],
             "Дата": pd.Timestamp(p["date"]).strftime("%Y-%m-%d"),
             "Последна промяна": p["modified"].strftime("%d.%m.%Y г.")}
            for p in list_projects(store)]
