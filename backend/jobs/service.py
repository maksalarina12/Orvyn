import threading
import time
from pathlib import Path
from typing import Any

from backend.assets import service as asset_service
from backend.backends.base import make_job_output_dir
from backend.backends.gradio_space import GradioSpaceProvider, JobCancelledError
from backend.core import config
from backend.core.security import sanitize_filename
from backend.core.utils import dumps, loads, new_id, utcnow_iso
from backend.database.db import db_session


def row_to_job(row) -> dict:
    data = dict(row)
    data["params"] = loads(data.pop("params_json")) or {}
    data["result_asset_ids"] = loads(data.pop("result_asset_ids")) or []
    return data


def create_job(
    conn,
    provider_id: str,
    mode: str,
    prompt: str,
    negative_prompt: str | None,
    params: dict,
    max_attempts: int = 2,
    project_id: str | None = None,
) -> dict:
    job_id = new_id("job")
    conn.execute(
        "INSERT INTO generation_jobs (id, project_id, provider_id, mode, prompt, negative_prompt, params_json,"
        " status, attempts, max_attempts, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (job_id, project_id, provider_id, mode, prompt, negative_prompt, dumps(params), "queued", 0, max_attempts, utcnow_iso()),
    )
    return row_to_job(conn.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,)).fetchone())


def get_job(conn, job_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,)).fetchone()
    return row_to_job(row) if row else None


def list_jobs(conn, limit: int = 50, offset: int = 0, project_id: str | None = None) -> list[dict]:
    sql = "SELECT * FROM generation_jobs"
    params: list = []
    if project_id:
        sql += " WHERE project_id = ?"
        params.append(project_id)
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    return [row_to_job(row) for row in conn.execute(sql, (*params, min(limit, 200), max(offset, 0))).fetchall()]


def _set_job_status(conn, job_id: str, status: str, **extra) -> None:
    assignments = ["status = ?"]
    params: list = [status]
    for key, value in extra.items():
        assignments.append(f"{key} = ?")
        params.append(value)
    params.append(job_id)
    conn.execute(f"UPDATE generation_jobs SET {', '.join(assignments)} WHERE id = ?", params)


def request_cancel(job_id: str) -> dict | None:
    with db_session() as conn:
        job = get_job(conn, job_id)
        if not job:
            return None
        if job["status"] in ("queued", "running"):
            _set_job_status(
                conn,
                job_id,
                "cancelled",
                error="cancelled by user",
                finished_at=utcnow_iso(),
            )
        return get_job(conn, job_id)


def recover_stale_jobs() -> dict:
    """Dipanggil saat startup: job 'running' dari proses sebelumnya sudah pasti mati.

    Jujur dan aman: coba requeue bila masih ada jatah attempt, selain itu
    tandai failed dengan pesan yang menjelaskan penyebabnya.
    """
    requeued: list[str] = []
    failed: list[str] = []
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM generation_jobs WHERE status = 'running'").fetchall()
        for row in rows:
            job = row_to_job(row)
            if job["attempts"] < job["max_attempts"]:
                _set_job_status(
                    conn,
                    job["id"],
                    "queued",
                    error=(
                        f"Backend dimatikan saat job berjalan (attempt {job['attempts']});"
                        " di-queue ulang setelah restart."
                    ),
                )
                requeued.append(job["id"])
            else:
                _set_job_status(
                    conn,
                    job["id"],
                    "failed",
                    error=(
                        f"Backend dimatikan saat job berjalan (attempt {job['attempts']}/"
                        f"{job['max_attempts']}); tidak ada sisa attempt."
                    ),
                    finished_at=utcnow_iso(),
                )
                failed.append(job["id"])
    return {"requeued": requeued, "failed": failed}


class Engine:
    """Bounded generation queue. Concurrency is fixed at 1 on this hardware."""

    def __init__(self, poll_interval: float = 0.5):
        self.poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start_background(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="orvyn-generation-engine", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_pending()
            except Exception:
                time.sleep(1.0)
            time.sleep(self.poll_interval)

    def run_pending(self) -> dict | None:
        """Process at most one queued job. Public so tests can drive it directly."""
        from backend.backends import registry

        registry.ensure_registered()
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM generation_jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            job = row_to_job(row) if row else None
        if not job:
            return None
        with db_session() as conn:
            fresh = get_job(conn, job["id"])
            if not fresh or fresh["status"] != "queued":
                return None
            _set_job_status(
                conn,
                job["id"],
                "running",
                attempts=fresh["attempts"] + 1,
                started_at=fresh["started_at"] or utcnow_iso(),
            )
            job = get_job(conn, job["id"])

        try:
            self._execute(job)
        except JobCancelledError as exc:
            with db_session() as conn:
                _set_job_status(conn, job["id"], "cancelled", error=str(exc), finished_at=utcnow_iso())
        except Exception as exc:
            with db_session() as conn:
                current = get_job(conn, job["id"])
                if not current or current["status"] != "running":
                    return None
                upcoming_attempt = current["attempts"] + 1
                retryable = current["max_attempts"]
                if current["attempts"] < retryable:
                    _set_job_status(
                        conn,
                        job["id"],
                        "queued",
                        error=f"Attempt {current['attempts']} failed: {exc}",
                    )
                else:
                    _set_job_status(
                        conn,
                        job["id"],
                        "failed",
                        error=f"Attempt {current['attempts']} failed: {exc}",
                        finished_at=utcnow_iso(),
                    )
        with db_session() as conn:
            return get_job(conn, job["id"])

    def _is_cancelled(self, job_id: str) -> bool:
        with db_session() as conn:
            j = get_job(conn, job_id)
            return bool(j and j["status"] == "cancelled")

    def _execute(self, job: dict) -> None:
        from backend.backends import registry

        provider = registry.get_provider(job["provider_id"])
        if not provider:
            raise RuntimeError(f"Provider {job['provider_id']} tidak terdaftar")
        validation = provider.validate_params(job["params"])
        if validation:
            raise RuntimeError("Parameter tidak valid: " + "; ".join(validation))

        out_dir = make_job_output_dir(self._project_slug(job["project_id"]), job["id"])
        outputs = provider.generate(
            mode=job["mode"],
            prompt=job["prompt"],
            negative_prompt=job["negative_prompt"],
            params=job["params"],
            out_dir_path=out_dir,
            on_progress=self._progress_hook(job["id"]),
        )

        result_asset_ids: list[str] = []
        with db_session() as conn:
            j = get_job(conn, job["id"])
            if j and j["status"] == "cancelled":
                raise JobCancelledError("cancelled by user")
            for path, mime in outputs:
                dims = _read_dims(Path(path))
                asset = register_generated_asset(
                    conn,
                    path=Path(path),
                    mime=mime,
                    project_id=job["project_id"],
                    job=job,
                    width=dims[0] if dims else None,
                    height=dims[1] if dims else None,
                )
                result_asset_ids.append(asset["id"])
            if j and j["status"] == "cancelled":
                raise JobCancelledError("cancelled by user")
            _set_job_status(conn, job["id"], "completed", result_asset_ids=dumps(result_asset_ids), finished_at=utcnow_iso())

    def _progress_hook(self, job_id: str):
        def hook():
            if self._is_cancelled(job_id):
                raise JobCancelledError("cancelled by user")
        return hook

    def _project_slug(self, project_id: str | None) -> str:
        with db_session() as conn:
            if project_id:
                row = conn.execute("SELECT id, name FROM projects WHERE id = ?", (project_id,)).fetchone()
                if row:
                    return sanitize_filename(str(row["name"]).lower().replace(" ", "-"))[:40] or project_id
            return "unassigned"


_GLOBAL_ENGINE: Engine | None = None


def get_engine() -> Engine:
    global _GLOBAL_ENGINE
    if _GLOBAL_ENGINE is None:
        _GLOBAL_ENGINE = Engine()
    return _GLOBAL_ENGINE


def _read_dims(path: Path):
    from backend.assets.models import read_image_dimensions

    try:
        return read_image_dimensions(path)
    except Exception:
        return None


def register_generated_asset(conn, path: Path, mime: str, project_id, job: dict, width, height) -> dict:
    rel_dir = path.parent.relative_to(config.DATA_DIR)
    rel = f"{rel_dir / path.name}"
    now = utcnow_iso()
    asset_id = new_id("ast")
    conn.execute(
        "INSERT INTO assets (id, project_id, path, filename, file_type, mime_type, width, height, file_size,"
        " source, prompt, negative_prompt, model_name, model_version, seed, backend, params_json, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            asset_id,
            project_id,
            rel,
            path.name,
            "video" if mime.startswith("video/") else "image",
            mime,
            width,
            height,
            path.stat().st_size,
            "generation",
            job["prompt"],
            job["negative_prompt"],
            job["provider_id"],
            None,
            job["params"].get("seed"),
            job["provider_id"],
            dumps(job["params"]),
            now,
            now,
        ),
    )
    return asset_service.get_asset(conn, asset_id)  # type: ignore[return-value]
