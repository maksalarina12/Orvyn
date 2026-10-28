import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from backend.core import config

SCHEMA_VERSION = 8

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'general',
    brief TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    path TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    file_size INTEGER NOT NULL,
    source TEXT NOT NULL DEFAULT 'upload',
    prompt TEXT,
    negative_prompt TEXT,
    model_name TEXT,
    model_version TEXT,
    seed INTEGER,
    backend TEXT,
    params_json TEXT,
    revision_of TEXT,
    notes TEXT NOT NULL DEFAULT '',
    is_favorite INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id);
CREATE INDEX IF NOT EXISTS idx_assets_created ON assets(created_at);

CREATE TABLE IF NOT EXISTS generation_jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    provider_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    prompt TEXT NOT NULL,
    negative_prompt TEXT,
    params_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 2,
    error TEXT,
    result_asset_ids TEXT,
    original_provider_id TEXT,
    provider_chain_json TEXT NOT NULL DEFAULT '[]',
    allow_fallback INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS provider_settings (
    provider_id TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL DEFAULT 0,
    config_json TEXT NOT NULL DEFAULT '{}',
    enabled_confirmed_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS creation_plans (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    title TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'general',
    status TEXT NOT NULL DEFAULT 'draft',
    brief_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS creation_plan_items (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    angle_id TEXT NOT NULL,
    angle_label TEXT NOT NULL,
    title TEXT NOT NULL,
    prompt TEXT NOT NULL,
    negative_prompt TEXT,
    params_json TEXT NOT NULL,
    job_id TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES creation_plans(id)
);

CREATE INDEX IF NOT EXISTS idx_plan_items_plan ON creation_plan_items(plan_id);

CREATE TABLE IF NOT EXISTS storyboards (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    title TEXT NOT NULL DEFAULT '',
    aspect TEXT NOT NULL DEFAULT '16:9',
    fps INTEGER NOT NULL DEFAULT 24,
    transition TEXT NOT NULL DEFAULT 'cut',
    transition_sec REAL NOT NULL DEFAULT 0.5,
    audio_asset_id TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    output_asset_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS storyboard_scenes (
    id TEXT PRIMARY KEY,
    storyboard_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    asset_id TEXT NOT NULL,
    duration_sec REAL NOT NULL DEFAULT 2.0,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (storyboard_id) REFERENCES storyboards(id),
    FOREIGN KEY (asset_id) REFERENCES assets(id)
);

CREATE INDEX IF NOT EXISTS idx_scenes_storyboard ON storyboard_scenes(storyboard_id);

CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS campaign_assets (
    campaign_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    added_at TEXT NOT NULL,
    PRIMARY KEY (campaign_id, asset_id),
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id),
    FOREIGN KEY (asset_id) REFERENCES assets(id)
);

CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS workflow_steps (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    kind TEXT NOT NULL,
    ref_id TEXT,
    title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    note TEXT NOT NULL DEFAULT '',
    result_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
);

CREATE INDEX IF NOT EXISTS idx_steps_workflow ON workflow_steps(workflow_id);
"""



def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or config.DB_PATH
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_session(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        with conn:  # commits on success, rolls back on exception
            yield conn
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    config.ensure_data_dirs()
    with db_session(db_path) as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )


_STORYBOARD_MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("transition", "TEXT NOT NULL DEFAULT 'cut'"),
    ("transition_sec", "REAL NOT NULL DEFAULT 0.5"),
    ("audio_asset_id", "TEXT"),
)

_JOB_MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("original_provider_id", "TEXT"),
    ("provider_chain_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("allow_fallback", "INTEGER NOT NULL DEFAULT 1"),
)


def _add_missing_columns(conn: sqlite3.Connection, table: str, migrations) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, ddl in migrations:
        if name not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive column migrations for databases created before v8."""
    _add_missing_columns(conn, "storyboards", _STORYBOARD_MIGRATIONS)
    _add_missing_columns(conn, "generation_jobs", _JOB_MIGRATIONS)
    conn.execute(
        "UPDATE generation_jobs SET original_provider_id = provider_id WHERE original_provider_id IS NULL"
    )
    conn.execute(
        "UPDATE generation_jobs SET provider_chain_json = '["' || provider_id || '"]'"
        " WHERE provider_chain_json = '[]'"
    )


_CONNECTIONS_READONLY = "SELECT name FROM sqlite_master WHERE type='table'"


def db_alive() -> bool:
    try:
        with db_session() as conn:
            conn.execute(_CONNECTIONS_READONLY).fetchone()
        return True
    except sqlite3.Error:
        return False
