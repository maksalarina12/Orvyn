from pathlib import Path

from backend.core import config


class PathValidationError(Exception):
    pass


def sanitize_filename(name: str) -> str:
    name = Path(name).name.strip()
    allowed = [c for c in name if c.isalnum() or c in "-_."]
    clean = "".join(allowed).strip(".-")
    if not clean:
        clean = "unnamed"
    return clean[:120]


def validate_relative_path(rel: str, base: Path | None = None) -> Path:
    base = base or (config.DATA_DIR)
    candidate = base / rel
    resolved_base = base.resolve()
    try:
        resolved = candidate.resolve()
    except (ValueError, OSError) as exc:
        raise PathValidationError(f"Invalid path: {exc}") from exc
    if resolved_base != resolved and resolved_base not in resolved.parents:
        raise PathValidationError("Path escapes data directory")
    if not resolved.exists():
        raise PathValidationError("File does not exist")
    return resolved


def is_safe_relative(rel: str, base: Path | None = None) -> bool:
    try:
        validate_relative_path(rel, base)
        return True
    except PathValidationError:
        return False
