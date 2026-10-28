import sqlite3

from backend.database.db import db_session


def get_settings_row(conn: sqlite3.Connection, provider_id: str):
    return conn.execute("SELECT * FROM provider_settings WHERE provider_id = ?", (provider_id,)).fetchone()


def get_provider_config(provider_id: str) -> dict:
    with db_session() as conn:
        row = get_settings_row(conn, provider_id)
        if not row:
            return {}
        from backend.core.utils import loads

        return loads(row["config_json"]) or {}


def is_provider_enabled(provider_id: str) -> bool:
    with db_session() as conn:
        row = get_settings_row(conn, provider_id)
        return bool(row and row["enabled"])
