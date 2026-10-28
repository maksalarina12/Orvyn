from concurrent.futures import ThreadPoolExecutor
import threading
import time
from typing import Any

from backend.backends.aihorde import AIHordeProvider
from backend.backends.base import GenerationProvider
from backend.backends.cloudflare import CloudflareProvider
from backend.backends.google_ai_studio import GoogleAIStudioProvider
from backend.backends.gradio_space import (
    GradioKontextProvider,
    GradioSpaceProvider,
    GradioSpaceVideoProvider,
    LTXVideoProvider,
)
from backend.backends.pollinations import PollinationsProvider
from backend.backends.provider_settings import get_provider_config, get_settings_row, is_provider_enabled
from backend.backends.siliconflow import SiliconFlowProvider
from backend.core.utils import dumps, loads, new_id, utcnow_iso
from backend.database.db import db_session


def set_provider_enabled(provider_id: str, enabled: bool, config_update: dict | None = None) -> dict:
    with db_session() as conn:
        row = get_settings_row(conn, provider_id)
        if row:
            settings = dict(loads(row["config_json"]) or {})
            if config_update:
                settings.update(config_update)
            conn.execute(
                "UPDATE provider_settings SET enabled = ?, config_json = ?, enabled_confirmed_at = ?, updated_at = ?"
                " WHERE provider_id = ?",
                (
                    int(enabled),
                    dumps(settings),
                    utcnow_iso() if enabled else row["enabled_confirmed_at"],
                    utcnow_iso(),
                    provider_id,
                ),
            )
        else:
            if enabled:
                provider = get_provider(provider_id)
                if provider is None:
                    raise ValueError("Provider not registered")
                if provider.is_external and provider.requires_config and not config_update:
                    raise ValueError("External provider requires config (e.g. space_url) before it can be enabled")
            conn.execute(
                "INSERT INTO provider_settings (provider_id, enabled, config_json, updated_at) VALUES (?, ?, ?, ?)",
                (provider_id, int(enabled), dumps(config_update or {}), utcnow_iso()),
            )
    invalidate_health(provider_id)
    return describe_provider_status(provider_id, force_health=True)


REGISTRY: dict[str, GenerationProvider] = {}
_INSTANCES: dict[str, GenerationProvider] = {}

_HEALTH_TTL_SEC = 300.0
_health_cache: dict[str, tuple[float, dict]] = {}
_health_refreshing: set[str] = set()


def _probe_health(provider: GenerationProvider) -> dict:
    import os

    t0 = time.monotonic()
    health = provider.health()
    dur = time.monotonic() - t0
    if os.environ.get("ORVYN_HEALTH_DEBUG"):
        print(f"[health] {provider.provider_id}: {dur:.2f}s ok={health.get('ok')}", flush=True)
    _health_cache[provider.provider_id] = (time.monotonic(), health)
    return health


def _refresh_health_background(provider: GenerationProvider) -> None:
    provider_id = provider.provider_id
    if provider_id in _health_refreshing:
        return
    _health_refreshing.add(provider_id)

    def run() -> None:
        try:
            _probe_health(provider)
        except Exception:
            pass
        finally:
            _health_refreshing.discard(provider_id)

    threading.Thread(target=run, daemon=True, name=f"health-{provider_id}").start()


def _fresh_health(provider: GenerationProvider, force: bool = False) -> dict:
    cached = _health_cache.get(provider.provider_id)
    if not force and cached:
        if (time.monotonic() - cached[0]) < _HEALTH_TTL_SEC:
            return cached[1]
        _refresh_health_background(provider)
        return cached[1]
    return _probe_health(provider)


def invalidate_health(provider_id: str | None = None) -> None:
    if provider_id is None:
        _health_cache.clear()
    else:
        _health_cache.pop(provider_id, None)


def register_provider(provider: GenerationProvider) -> None:
    REGISTRY[provider.provider_id] = provider


def get_provider(provider_id: str) -> GenerationProvider | None:
    return REGISTRY.get(provider_id)


def _redact_config(provider: GenerationProvider, config: dict | None) -> dict:
    secrets = {
        field.get("key")
        for field in (provider.capabilities().get("config_schema") or [])
        if field.get("secret")
    }
    secrets.add("hf_token")
    return {
        key: ("<set>" if key in secrets and value else value)
        for key, value in (config or {}).items()
    }


def describe_provider_status(provider_id: str, force_health: bool = False) -> dict:
    provider = get_provider(provider_id)
    if not provider:
        return {"provider_id": provider_id, "unknown": True}
    config_data = get_provider_config(provider_id)
    status: dict[str, Any] = {
        "provider_id": provider_id,
        "display_name": provider.display_name,
        "is_external": provider.is_external,
        "enabled": is_provider_enabled(provider_id),
        "configured": True,
        "capabilities": provider.capabilities(),
        "config_redacted": _redact_config(provider, config_data),
    }
    if status["enabled"]:
        status["health"] = _fresh_health(provider, force=force_health)
    else:
        status["health"] = {"ok": False, "types": ["disabled"], "reason": "Provider is disabled by default. Enable it explicitly (this may send prompts to a third-party service)."}
    return status


def list_provider_status(force_health: bool = False) -> list[dict]:
    provider_ids = list(REGISTRY)
    with ThreadPoolExecutor(max_workers=8) as pool:
        if force_health:
            futures = [pool.submit(describe_provider_status, pid, True) for pid in provider_ids]
        else:
            futures = [pool.submit(describe_provider_status, pid) for pid in provider_ids]
        return [f.result() for f in futures]


_FALLBACK_PRIORITY: tuple[str, ...] = (
    "pollinations",
    "ai_horde",
    "hf_space",
    "hf_space_kontext",
    "hf_space_video",
    "hf_space_video_ltx",
    "siliconflow",
    "cloudflare",
    "google_ai_studio",
)


def fallback_provider_id(mode: str, exclude: set[str] | None = None) -> str | None:
    """Pick an enabled, healthy provider that supports this mode.

    Only providers the user explicitly enabled are eligible; health is checked
    in parallel so a failing provider is not chosen blindly.
    """
    ensure_registered()
    excluded = set(exclude or ())
    order = list(REGISTRY)

    def rank(provider_id: str) -> tuple[int, int]:
        try:
            return (_FALLBACK_PRIORITY.index(provider_id), order.index(provider_id))
        except ValueError:
            return (len(_FALLBACK_PRIORITY), order.index(provider_id))

    candidates: list[GenerationProvider] = []
    for provider_id in sorted(order, key=rank):
        if provider_id in excluded:
            continue
        provider = REGISTRY[provider_id]
        if mode not in (provider.capabilities().get("modes") or []):
            continue
        if not is_provider_enabled(provider_id):
            continue
        candidates.append(provider)
    if not candidates:
        return None
    with ThreadPoolExecutor(max_workers=min(4, len(candidates))) as pool:
        healths = list(pool.map(_fresh_health, candidates))
    for provider, health in zip(candidates, healths):
        if health.get("ok"):
            return provider.provider_id
    return None


# Built-in providers ----------------------------------------------------------


_builtins_registered = False


def ensure_registered() -> None:
    global _builtins_registered
    if _builtins_registered:
        return
    register_provider(GradioSpaceProvider())
    register_provider(GradioKontextProvider())
    register_provider(GradioSpaceVideoProvider())
    register_provider(LTXVideoProvider())
    register_provider(PollinationsProvider())
    register_provider(AIHordeProvider())
    register_provider(CloudflareProvider())
    register_provider(GoogleAIStudioProvider())
    register_provider(SiliconFlowProvider())
    _builtins_registered = True
