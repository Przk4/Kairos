# tu_app/debug_state.py
"""
Thread-safe debug state capture for the Kairos debug dashboard.
Uses Django's cache framework (LocMemCache by default) so it works
safely across gunicorn workers — each worker keeps its own copy,
which is fine for a diagnostic dashboard.

Usage:
    from tu_app.debug_state import capture_prompt_flow, get_last_prompt_flow, push_log

    capture_prompt_flow({...})
    data = get_last_prompt_flow()
    push_log("INFO", "Something happened")
    logs = get_logs()
"""
import threading
from datetime import datetime
try:
    from django.core.cache import cache
    _HAS_CACHE = True
except Exception:
    cache = None
    _HAS_CACHE = False

_lock = threading.Lock()

# Cache keys (when Django cache available) — fall back to in-process vars
_CACHE_KEY_PROMPT = 'kairos_debug_prompt_flow'
_CACHE_KEY_LOGS = 'kairos_debug_logs'

# ── In-process storage (used only if Django cache isn't available)
_last_prompt_flow: dict = {}
_logs: list = []          # ring-buffer, max 200 entries


def capture_prompt_flow(data: dict) -> None:
    """Store the latest prompt-flow snapshot."""
    payload = {**data, "captured_at": datetime.now().isoformat()}
    try:
        if _HAS_CACHE and cache is not None:
            cache.set(_CACHE_KEY_PROMPT, payload, None)
            return
    except Exception:
        pass

    # Fallback to in-process storage
    global _last_prompt_flow
    with _lock:
        _last_prompt_flow = payload


def get_last_prompt_flow() -> dict:
    """Return the latest prompt-flow snapshot (or empty dict)."""
    try:
        if _HAS_CACHE and cache is not None:
            val = cache.get(_CACHE_KEY_PROMPT)
            return dict(val) if isinstance(val, dict) else {}
    except Exception:
        pass

    with _lock:
        return dict(_last_prompt_flow)


MAX_LOGS = 200


def push_log(level: str, message: str, extra: str = "") -> None:
    """Append a log entry to the ring buffer."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message,
        "extra": extra,
    }
    try:
        if _HAS_CACHE and cache is not None:
            logs = cache.get(_CACHE_KEY_LOGS) or []
            logs.append(entry)
            if len(logs) > MAX_LOGS:
                logs = logs[-MAX_LOGS:]
            cache.set(_CACHE_KEY_LOGS, logs, None)
            return
    except Exception:
        pass

    global _logs
    with _lock:
        _logs.append(entry)
        if len(_logs) > MAX_LOGS:
            _logs = _logs[-MAX_LOGS:]


def get_logs(limit: int = 100) -> list:
    """Return the most recent *limit* log entries (newest first)."""
    try:
        if _HAS_CACHE and cache is not None:
            logs = cache.get(_CACHE_KEY_LOGS) or []
            return list(reversed(logs[-limit:]))
    except Exception:
        pass

    with _lock:
        return list(reversed(_logs[-limit:]))
