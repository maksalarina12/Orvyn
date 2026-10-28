import sqlite3

from backend.core.utils import dumps, loads, new_id, utcnow_iso
from backend.projects.models import ProjectCreate, ProjectUpdate

_APPLYABLE_FIELDS = ("name", "description", "category", "brief")


def row_to_project(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["tags"] = loads(data.get("tags")) or []
    return data


def list_projects(
    conn: sqlite3.Connection,
    query: str | None = None,
    category: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    sql = [
        """SELECT p.*, (SELECT COUNT(*) FROM assets a WHERE a.project_id = p.id) AS asset_count
           FROM projects p"""
    ]
    params: list = []
    clauses = []
    if query:
        clauses.append("(p.name LIKE ? OR p.description LIKE ? OR p.tags LIKE ?)")
        like = f"%{query}%"
        params += [like, like, like]
    if category:
        clauses.append("p.category = ?")
        params.append(category)
    if clauses:
        sql.append("WHERE " + " AND ".join(clauses))
    sql.append("ORDER BY p.updated_at DESC LIMIT ? OFFSET ?")
    cur = conn.execute(
        " ".join(sql), (*params, min(limit, 500), max(offset, 0))
    )
    return [row_to_project(row) for row in cur.fetchall()]


def get_project(conn: sqlite3.Connection, project_id: str) -> dict | None:
    cur = conn.execute(
        """SELECT p.*, (SELECT COUNT(*) FROM assets a WHERE a.project_id = p.id) AS asset_count
           FROM projects p WHERE p.id = ?""",
        (project_id,),
    )
    row = cur.fetchone()
    return row_to_project(row) if row else None


def create_project(conn: sqlite3.Connection, data: ProjectCreate) -> dict:
    now = utcnow_iso()
    project_id = new_id("prj")
    tags_json = dumps(data.tags)
    conn.execute(
        "INSERT INTO projects (id, name, description, category, brief, tags, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            project_id,
            data.name,
            data.description,
            data.category,
            data.brief,
            tags_json,
            now,
            now,
        ),
    )
    return get_project(conn, project_id)  # type: ignore[return-value]


def update_project(conn: sqlite3.Connection, project_id: str, data: ProjectUpdate) -> dict | None:
    existing = get_project(conn, project_id)
    if not existing:
        return None
    fields: list[str] = []
    params: list = []
    for name in _APPLYABLE_FIELDS:
        value = getattr(data, name)
        if value is not None:
            fields.append(f"{name} = ?")
            params.append(value)
    if data.tags is not None:
        fields.append("tags = ?")
        params.append(dumps(data.tags))
    if fields:
        fields.append("updated_at = ?")
        params.append(utcnow_iso())
        params.append(project_id)
        conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", params)
    return get_project(conn, project_id)


def delete_project(conn: sqlite3.Connection, project_id: str) -> bool:
    existing = get_project(conn, project_id)
    if not existing:
        return False
    conn.execute("UPDATE assets SET project_id = NULL WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return True
